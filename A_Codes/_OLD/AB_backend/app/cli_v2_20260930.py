"""Command-line tasks (run from AB_backend):
    python -m app.cli bootstrap [--dir PATH]      policy settings + users (B_Inputs/AA_bootstrap)
    python -m app.cli load-samples [--dir PATH]   sample models and history (B_Inputs/AB_sample_data)
"""
import argparse
import sys
from pathlib import Path

from app.config import get_settings
from app.db import SessionLocal
from app.services.bootstrap_service import load_bootstrap
from app.services.errors import ServiceError
from app.services.sample_loader import load_samples


def main() -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    boot = sub.add_parser("bootstrap", help="Load policy settings and users from B_Inputs/AA_bootstrap")
    boot.add_argument("--dir", type=Path, default=settings.bootstrap_dir)
    samples = sub.add_parser("load-samples", help="Load sample models, validations, findings and approvals")
    samples.add_argument("--dir", type=Path, default=settings.sample_data_dir)
    args = parser.parse_args()

    with SessionLocal() as db:
        if args.command == "bootstrap":
            try:
                counts = load_bootstrap(db, args.dir)
            except ServiceError as exc:
                print(exc.message, file=sys.stderr)
                for err in exc.details:
                    print(f"  {err['file']} row {err['row']}: {err['message']}", file=sys.stderr)
                return 1
            print(f"Bootstrap loaded: {counts['policy_settings']} policy settings, {counts['users']} users.")
        elif args.command == "load-samples":
            report = load_samples(db, args.dir)
            for file, n in report.loaded.items():
                print(f"  {file}: {n} loaded, {report.skipped[file]} already present")
            for err in report.errors:
                print(f"  ERROR {err}", file=sys.stderr)
            return 1 if report.errors else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
