"""Generic, template-driven row checks (REQ-IMP-02 / design R10), run before the business services.

Order: required columns present → types → allowed values → patterns/lengths → keys unique in file →
references exist. Business rules (SoD, phase requirements, conditional approvals…) are then applied
by the same services the API uses.
"""
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from app.ingestion.registry import TEMPLATES, Template
from app.models import AppUser, Model, Validation
from app.services.policy_access import Policy

FK_MODELS = {"app_user": (AppUser, "User"), "model": (Model, "Model"), "validation": (Validation, "Validation")}


@dataclass
class Issue:
    severity: str  # error | warning
    error_type: str
    message: str
    column: str | None = None
    original: str | None = None
    row: int | None = None


def allowed_values(template: Template, policy: Policy) -> dict[str, list[str]]:
    out = {}
    for c in template.columns:
        if isinstance(c.allowed, str) and c.allowed.startswith("policy:"):
            key = c.allowed.split(":", 1)[1]
            out[c.name] = list(policy.frequency_months) if key == "revalidation_frequencies" else policy.list(key)
        elif c.allowed:
            out[c.name] = list(c.allowed)
    return out


_TEMPLATE_TOKEN = re.compile(r"(?<![A-Za-z0-9])(T\d{2})(?![0-9])", re.IGNORECASE)


def detect_template(file_name: str, headers: list[str]) -> tuple[str | None, str | None]:
    """Filename token (e.g. 'T02_models.xlsx') first, then best header match."""
    m = _TEMPLATE_TOKEN.search(file_name)
    if m:
        tid = m.group(1).upper()
        if any(t.template_id == tid and t.available for t in TEMPLATES):
            return tid, "filename"
    header_set = set(headers)
    best, best_score = None, 0.0
    for t in TEMPLATES:
        if not t.available or not t.required_columns:
            continue
        required = set(t.required_columns)
        if required <= header_set:
            score = len(required) / max(len(header_set), 1)
            if score > best_score:
                best, best_score = t.template_id, score
    return (best, "header") if best else (None, None)


def check_headers(template: Template, headers: list[str]) -> list[Issue]:
    issues = []
    missing = [c for c in template.required_columns if c not in headers]
    if missing:
        issues.append(Issue("error", "missing_columns",
                            f"Required column(s) missing: {', '.join(missing)}. This does not look like a "
                            f"{template.template_id} {template.name} file."))
    known = {c.name for c in template.columns}
    extra = [h for h in headers if h not in known]
    if extra:
        issues.append(Issue("warning", "unknown_columns", f"Column(s) ignored: {', '.join(extra)}."))
    dupes = [h for h, n in Counter(headers).items() if n > 1]
    if dupes:
        issues.append(Issue("error", "duplicate_columns", f"Column(s) appear more than once: {', '.join(dupes)}."))
    return issues


def duplicate_key_rows(template: Template, rows: list[dict[str, str]]) -> dict[int, str]:
    """Row index → key value, for rows whose key appears more than once in the file."""
    counts = Counter((r.get(template.key) or "").strip() for r in rows)
    return {i: r.get(template.key) for i, r in enumerate(rows)
            if (r.get(template.key) or "").strip() and counts[(r.get(template.key) or "").strip()] > 1}


def convert_row(db: Session, template: Template, raw: dict[str, str], allowed: dict[str, list[str]],
                row_number: int, file_keys: frozenset[str] = frozenset()) -> tuple[dict, list[Issue]]:
    issues: list[Issue] = []
    typed: dict = {}

    def err(col: str, etype: str, msg: str) -> None:
        issues.append(Issue("error", etype, msg, col, raw.get(col), row_number))

    for c in template.columns:
        if c.name not in raw:
            continue
        text = (raw.get(c.name) or "").strip()
        if text == "":
            if c.required:
                err(c.name, "required", f"{c.name} is required.")
            typed[c.name] = None
            continue
        value: object = text
        if c.type == "int":
            try:
                value = int(text)
            except ValueError:
                err(c.name, "type", f"'{text}' is not a whole number.")
                continue
        elif c.type == "decimal":
            try:
                value = Decimal(text)
            except InvalidOperation:
                err(c.name, "type", f"'{text}' is not a number.")
                continue
        elif c.type == "date":
            try:
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
                    raise ValueError
                value = date.fromisoformat(text)
            except ValueError:
                err(c.name, "date", f"'{text}' is not a valid date. Use YYYY-MM-DD.")
                continue
        elif c.type == "yn":
            if text.upper() not in ("Y", "N"):
                err(c.name, "allowed", f"'{text}' must be Y or N.")
                continue
            value = text.upper() == "Y"
        elif c.type == "list":
            value = [p.strip() for p in text.split(";") if p.strip()]

        if c.name in allowed:
            candidates = value if isinstance(value, list) else [str(value)]
            bad = [v for v in candidates if v not in allowed[c.name]]
            if bad:
                err(c.name, "allowed", f"'{'; '.join(bad)}' is not allowed for {c.name}. "
                                       f"Allowed: {', '.join(allowed[c.name])}.")
                continue
        if c.pattern and not re.fullmatch(c.pattern, text):
            err(c.name, "format", f"'{text}' does not match the expected format for {c.name} (e.g. {c.example}).")
            continue
        if c.max_length and len(text) > c.max_length:
            err(c.name, "length", f"{c.name} is longer than {c.max_length} characters.")
            continue
        if c.fk and not (c.same_file_ok and text in file_keys):
            orm, label = FK_MODELS[c.fk]
            if db.get(orm, text) is None:
                err(c.name, "reference", f"{label} {text} does not exist.")
                continue
        typed[c.name] = value
    return typed, issues
