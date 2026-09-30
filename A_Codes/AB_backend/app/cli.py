"""Command-line tasks (run from AB_backend):
    python -m app.cli bootstrap [--dir PATH]      policy settings + users only (B_Inputs/AA_bootstrap)
    python -m app.cli reset [--dir PATH]          clear governance data and load the full seed via the import
                                                  engine (B_Inputs/AC_seed); the audit trail is kept
    python -m app.cli import FILE [FILE ...]      validate and load files as one batch (as System)
    python -m app.cli load-samples [--dir PATH]   Phase-2 sample data (superseded by reset; kept for reference)
"""
import argparse
import sys
from pathlib import Path

from app.config import get_settings
from app.db import SessionLocal
from app.ingestion import engine
from app.ingestion import service as import_service
from app.models import ImportBatch
from app.services import reset_service
from app.services.bootstrap_service import load_bootstrap
from app.services.errors import ServiceError
from app.services.sample_loader import load_samples


def _print_batch(batch_id: str) -> int:
    with SessionLocal() as db:
        b = db.get(ImportBatch, batch_id)
        print(f"Batch {b.batch_id}: {b.status} — {b.successful_records} rows loaded, {b.failed_records} rejected, "
              f"{b.warning_count} warnings")
        for f in b.files:
            print(f"  {f.file_name} [{f.template_id or '—'}] {f.status}: {f.rows_loaded or f.rows_valid} ok, "
                  f"{f.rows_invalid} rejected (new {f.rows_new}, updated {f.rows_update}, unchanged {f.rows_unchanged})")
        if b.error_message:
            print(f"  {b.error_message}", file=sys.stderr)
        for i in import_service.issues(db, batch_id, limit=20):
            if i.severity == "error":
                print(f"  ERROR row {i.row_number} {i.column_name or ''}: {i.message}", file=sys.stderr)
        return 0 if b.status == "Completed" else 1


def main() -> int:
    settings = get_settings()
    settings.job_mode = "inline"  # CLI waits for its own jobs
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    boot = sub.add_parser("bootstrap", help="Load policy settings and users from B_Inputs/AA_bootstrap")
    boot.add_argument("--dir", type=Path, default=settings.bootstrap_dir)
    reset = sub.add_parser("reset", help="Reset governance data to the seed (B_Inputs/AC_seed)")
    reset.add_argument("--dir", type=Path, default=settings.seed_dir)
    imp = sub.add_parser("import", help="Import Excel/CSV files as one batch")
    imp.add_argument("files", nargs="+", type=Path)
    samples = sub.add_parser("load-samples", help="Load Phase-2 sample data")
    samples.add_argument("--dir", type=Path, default=settings.sample_data_dir)
    args = parser.parse_args()

    with SessionLocal() as db:
        try:
            if args.command == "bootstrap":
                counts = load_bootstrap(db, args.dir)
                print(f"Bootstrap loaded: {counts['policy_settings']} policy settings, {counts['users']} users.")
            elif args.command == "reset":
                batch = reset_service.start_reset(db, lambda: SessionLocal(), None, args.dir)
                return _print_batch(batch.batch_id)
            elif args.command == "import":
                uploads = [(p.name, p.read_bytes()) for p in args.files]
                batch = import_service.create_batch(db, None, uploads, source="cli")
                engine.run(lambda: SessionLocal(), batch.batch_id, "load", None)
                return _print_batch(batch.batch_id)
            elif args.command == "load-samples":
                report = load_samples(db, args.dir)
                for file, n in report.loaded.items():
                    print(f"  {file}: {n} loaded, {report.skipped[file]} already present")
                for err in report.errors:
                    print(f"  ERROR {err}", file=sys.stderr)
                return 1 if report.errors else 0
        except ServiceError as exc:
            print(exc.message, file=sys.stderr)
            for err in exc.details:
                print(f"  {err}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
