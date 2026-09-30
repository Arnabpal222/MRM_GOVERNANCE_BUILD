"""Phase-1 bootstrap: loads policy settings and users from CSV files in B_Inputs/AA_bootstrap.

Idempotent — re-running updates changed rows and writes audit events only for real changes.
The Phase-3 import engine (T12/T01 templates) will supersede this loader.
"""
import csv
from pathlib import Path

from sqlalchemy.orm import Session

from app.services import policy_service, user_service
from app.services.errors import ValidationFailedError

POLICY_FILE = "T12_policy_settings.csv"
USERS_FILE = "T01_users.csv"


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Bootstrap file not found: {path}")
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return [{k.strip(): (v or "").strip() for k, v in row.items()} for row in csv.DictReader(fh)]


def load_bootstrap(db: Session, directory: Path) -> dict[str, int]:
    errors: list[dict] = []
    policies = _read_csv(directory / POLICY_FILE)
    for i, row in enumerate(policies, start=2):
        try:
            policy_service.upsert_setting(
                db, None, key=row["setting_key"], value=row["value"], value_type=row["value_type"],
                category=row.get("category") or None, description=row.get("description") or None,
            )
        except ValidationFailedError as exc:
            errors.append({"file": POLICY_FILE, "row": i, "message": exc.message})

    users = _read_csv(directory / USERS_FILE)
    for i, row in enumerate(users, start=2):
        try:
            user_service.upsert_user(
                db, None, user_id=row["user_id"], full_name=row["full_name"], email=row["email"],
                business_line=row.get("business_line") or None,
                roles=row["role"].split(";"), active=row.get("active", "Y").upper() == "Y",
            )
        except ValidationFailedError as exc:
            errors.append({"file": USERS_FILE, "row": i, "message": exc.message})

    if errors:
        db.rollback()
        raise ValidationFailedError("Bootstrap files contain errors; nothing was loaded.", errors)
    db.commit()
    return {"policy_settings": len(policies), "users": len(users)}
