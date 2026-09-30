"""Batch processing: the same code path validates (dry run, always rolled back) and loads (committed).

Files are processed in template load order inside one transaction, so rows created by an earlier file
(e.g. T02 models) satisfy references in a later file of the same batch (e.g. T04 findings) — in the
preview as well as the load. Every row runs in its own SAVEPOINT: a failing row is rolled back and
reported while the valid rows continue (partial acceptance, BRD §44).

Loading always re-validates; it never trusts an earlier preview. A crashed load rolls back entirely and
can simply be re-run (idempotent upserts).
"""
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import delete
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth.security import Principal
from app.ingestion import checks, fileio
from app.ingestion.adapters import ADAPTERS, POST_PASS
from app.ingestion.registry import get_template
from app.models import ImportBatch, ImportFile, ImportIssue
from app.services.errors import ServiceError
from app.services.policy_access import Policy
from app.storage import get_store
from app.workers.runner import progress


@dataclass
class FileResult:
    status: str
    file_error: str | None = None
    rows_total: int = 0
    rows_valid: int = 0
    rows_invalid: int = 0
    outcomes: dict[str, int] = field(default_factory=lambda: {"new": 0, "updated": 0, "unchanged": 0, "skipped": 0})
    issues: list[checks.Issue] = field(default_factory=list)


def _now() -> datetime:
    return datetime.now(UTC)


def _process_file(db: Session, principal: Principal | None, batch: ImportBatch, f: ImportFile,
                  on_existing: str) -> FileResult:
    template = get_template(f.template_id) if f.template_id else None
    if template is None or not template.available:
        return FileResult("Unmapped", "No import template is assigned to this file. Choose one and validate again.")
    try:
        parsed = fileio.parse(f.file_name, get_store().get(f.storage_key))
    except fileio.FileFormatError as exc:
        return FileResult("Invalid", str(exc))

    result = FileResult("Validated", rows_total=len(parsed.rows))
    header_issues = checks.check_headers(template, parsed.headers)
    result.issues += header_issues
    if any(i.severity == "error" for i in header_issues):
        result.status = "Invalid"
        result.file_error = next(i.message for i in header_issues if i.severity == "error")
        result.rows_invalid = len(parsed.rows)
        return result

    allowed = checks.allowed_values(template, Policy.load(db))
    dupes = checks.duplicate_key_rows(template, parsed.rows)
    adapter = ADAPTERS[template.template_id]
    file_keys = frozenset((r.get(template.key) or "").strip() for r in parsed.rows)
    post = POST_PASS.get(template.template_id)
    deferred: list[tuple[int, dict, dict]] = []
    for idx, raw in enumerate(parsed.rows):
        row_number = idx + 2  # header is row 1
        progress.set(batch.batch_id, current_file=f.file_name, row=row_number, rows_total=len(parsed.rows))
        if idx in dupes:
            result.issues.append(checks.Issue("error", "duplicate_key", f"{template.key} {dupes[idx]} appears more "
                                              f"than once in this file.", template.key, dupes[idx], row_number))
            result.rows_invalid += 1
            continue
        typed, issues = checks.convert_row(db, template, raw, allowed, row_number, file_keys)
        if issues:
            result.issues += issues
            result.rows_invalid += 1
            continue
        savepoint = db.begin_nested()
        try:
            outcome, warnings = adapter(db, principal, typed, batch.batch_id, on_existing)
            db.flush()
            savepoint.commit()
        except ServiceError as exc:
            savepoint.rollback()
            details = exc.details or [{"field": None, "message": exc.message}]
            for d in details:
                col = d.get("field") if d.get("field") in raw else None
                result.issues.append(checks.Issue("error", "rule", d.get("message", exc.message), col,
                                                  raw.get(col) if col else None, row_number))
            result.rows_invalid += 1
            continue
        except SQLAlchemyError as exc:
            savepoint.rollback()
            result.issues.append(checks.Issue("error", "constraint", "The row conflicts with an existing record "
                                              f"({type(exc.orig or exc).__name__}).", None, None, row_number))
            result.rows_invalid += 1
            continue
        result.rows_valid += 1
        result.outcomes[outcome] += 1
        result.issues += [checks.Issue("warning", "notice", w, None, None, row_number) for w in warnings]
        if post and typed.get(post[0]):
            deferred.append((row_number, typed, raw))

    for row_number, typed, raw in deferred:  # e.g. successor links, once every model in the file exists
        column, fn = post
        savepoint = db.begin_nested()
        try:
            fn(db, principal, typed, batch.batch_id)
            db.flush()
            savepoint.commit()
        except (ServiceError, SQLAlchemyError) as exc:
            savepoint.rollback()
            msg = exc.message if isinstance(exc, ServiceError) else type(exc).__name__
            result.issues.append(checks.Issue("error", "rule", f"Row saved, but {column} was not linked: {msg}",
                                              column, raw.get(column), row_number))
    return result


def run(session_factory: Callable[[], Session], batch_id: str, mode: str, principal: Principal | None) -> None:
    """mode: 'validate' (dry run) or 'load'."""
    assert mode in ("validate", "load")
    stage = "validate" if mode == "validate" else "load"
    with session_factory() as db:
        batch = db.get(ImportBatch, batch_id)
        files = sorted(batch.files, key=lambda f: ((get_template(f.template_id).order if f.template_id and
                                                     get_template(f.template_id) else 99), f.import_file_id))
        file_ids = [f.import_file_id for f in files]
        on_existing = (batch.options or {}).get("on_existing", "update")
        progress.set(batch_id, stage=stage, files_total=len(files), files_done=0)

        results: dict[int, FileResult] = {}
        failure: str | None = None
        try:
            for n, f in enumerate(files):
                results[f.import_file_id] = _process_file(db, principal, batch, f, on_existing)
                progress.set(batch_id, files_done=n + 1)
            if mode == "load":
                db.commit()
            else:
                db.rollback()
        except Exception as exc:  # noqa: BLE001 — any crash leaves the database untouched and the batch Failed
            db.rollback()
            failure = f"Processing stopped: {type(exc).__name__}: {exc}"

        _record(db, batch_id, file_ids, results, mode, failure)
    progress.clear(batch_id)


def _record(db: Session, batch_id: str, file_ids: list[int], results: dict[int, FileResult], mode: str,
            failure: str | None) -> None:
    stage = "validate" if mode == "validate" else "load"
    batch = db.get(ImportBatch, batch_id)
    db.execute(delete(ImportIssue).where(ImportIssue.batch_id == batch_id))
    totals = dict(files_ok=0, files_bad=0, rows=0, ok=0, bad=0, warnings=0)
    for fid in file_ids:
        f = db.get(ImportFile, fid)
        r = results.get(fid)
        if r is None:
            f.status = "Failed" if mode == "load" else "Invalid"
            continue
        f.file_error = r.file_error
        f.rows_total, f.rows_valid, f.rows_invalid = r.rows_total, r.rows_valid, r.rows_invalid
        f.rows_new, f.rows_update = r.outcomes["new"], r.outcomes["updated"]
        f.rows_unchanged = r.outcomes["unchanged"] + r.outcomes["skipped"]
        f.error_count = sum(1 for i in r.issues if i.severity == "error")
        f.warning_count = sum(1 for i in r.issues if i.severity == "warning")
        if mode == "load" and not failure:
            f.rows_loaded = r.rows_valid
            if r.status in ("Unmapped", "Invalid"):
                f.status = "Not loaded"
            elif r.rows_invalid == 0:
                f.status = "Loaded"
            else:
                f.status = "Partially loaded" if r.rows_valid else "Failed"
        else:
            f.status = r.status
        good = f.status in ("Validated", "Loaded", "Partially loaded")
        totals["files_ok" if good else "files_bad"] += 1
        totals["rows"] += r.rows_total
        totals["ok"] += r.rows_valid
        totals["bad"] += r.rows_invalid
        totals["warnings"] += f.warning_count
        for i in r.issues:
            db.add(ImportIssue(batch_id=batch_id, import_file_id=fid, stage=stage, severity=i.severity,
                               sheet=f.sheet_name, row_number=i.row, column_name=i.column, error_type=i.error_type,
                               message=i.message, original_value=i.original))
        if r.file_error and not any(i.message == r.file_error for i in r.issues):
            db.add(ImportIssue(batch_id=batch_id, import_file_id=fid, stage=stage, severity="error",
                               error_type="file", message=r.file_error))

    batch.total_files = len(file_ids)
    batch.successful_files, batch.failed_files = totals["files_ok"], totals["files_bad"]
    batch.total_records, batch.warning_count = totals["rows"], totals["warnings"]
    batch.failed_records = totals["bad"]
    batch.error_message = failure
    if mode == "validate":
        batch.validated_at = _now()
        batch.successful_records = 0
        batch.status = "Failed" if failure else ("Ready" if totals["ok"] else "Validation Failed")
    else:
        batch.completed_at = _now()
        batch.successful_records = 0 if failure else totals["ok"]
        if failure:
            batch.status = "Failed"
        elif totals["ok"] == 0:
            batch.status = "Failed"
        elif totals["bad"] or totals["files_bad"]:
            batch.status = "Partially Completed"
        else:
            batch.status = "Completed"
    db.commit()
