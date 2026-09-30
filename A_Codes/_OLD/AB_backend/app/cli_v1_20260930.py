"""Command-line tasks.  Usage (from AB_backend):  python -m app.cli bootstrap [--dir PATH]"""
import argparse
import sys
from pathlib import Path

from app.config import get_settings
from app.db import SessionLocal
from app.services.bootstrap_service import load_bootstrap
from app.services.errors import ServiceError


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    boot = sub.add_parser("bootstrap", help="Load policy settings and users from B_Inputs/AA_bootstrap")
    boot.add_argument("--dir", type=Path, default=get_settings().bootstrap_dir)
    args = parser.parse_args()

    if args.command == "bootstrap":
        with SessionLocal() as db:
            try:
                counts = load_bootstrap(db, args.dir)
            except ServiceError as exc:
                print(exc.message, file=sys.stderr)
                for err in exc.details:
                    print(f"  {err['file']} row {err['row']}: {err['message']}", file=sys.stderr)
                return 1
        print(f"Bootstrap loaded: {counts['policy_settings']} policy settings, {counts['users']} users.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
