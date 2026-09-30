"""Loads Phase-2 sample data (B_Inputs/AB_sample_data) through the business services, so every row
passes the same validation, SoD checks and audit path as an API write. Existing IDs are skipped
(idempotent). The Phase-3 import engine replaces this with preview/partial-acceptance imports."""
import csv
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import Approval, Finding, Model, ModelRelationship, Validation
from app.services import approval_service, finding_service, model_service, user_service, validation_service
from app.services.errors import ServiceError

DATE_FIELDS = {"go_live_date", "last_validation_date", "start_date", "completion_date", "raised_date", "due_date",
               "closed_date", "decision_date", "condition_due_date"}
INT_FIELDS = {"q_materiality", "q_complexity", "q_reliance", "q_regulatory_use"}


@dataclass
class LoadReport:
    loaded: dict[str, int] = field(default_factory=dict)
    skipped: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def _rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        out = []
        for row in csv.DictReader(fh):
            clean = {}
            for k, v in row.items():
                v = (v or "").strip()
                if v == "":
                    clean[k] = None
                elif k in DATE_FIELDS:
                    clean[k] = date.fromisoformat(v)
                elif k in INT_FIELDS:
                    clean[k] = int(v)
                else:
                    clean[k] = v
            out.append(clean)
        return out


def load_samples(db: Session, directory: Path) -> LoadReport:
    report = LoadReport()

    def run(file: str, key: str, exists, create) -> None:
        loaded = skipped = 0
        for i, row in enumerate(_rows(directory / file), start=2):
            if exists(row):
                skipped += 1
                continue
            try:
                create(row)
                loaded += 1
            except ServiceError as exc:
                db.rollback()
                report.errors.append(f"{file} row {i} ({row.get(key)}): {exc.message}")
        report.loaded[file], report.skipped[file] = loaded, skipped

    def create_user(row):
        user_service.upsert_user(db, None, user_id=row["user_id"], full_name=row["full_name"], email=row["email"],
                                 business_line=row.get("business_line"), roles=row["role"].split(";"),
                                 active=(row.get("active") or "Y") == "Y")
        db.commit()

    from app.models import AppUser
    run("T01_users.csv", "user_id", lambda r: db.get(AppUser, r["user_id"]) is not None, create_user)

    successors = []

    def create_model(row):
        legacy = row.pop("legacy_sod_exception", None) == "Y"
        successor = row.pop("successor_model_id", None)
        model_service.create_model(db, None, row, legacy_sod=legacy, reason="Sample data load")
        if successor:
            successors.append((row["model_id"], successor))

    run("T02_models.csv", "model_id", lambda r: db.get(Model, r["model_id"]) is not None, create_model)
    for model_id, successor in successors:
        if db.get(ModelRelationship, (model_id, successor, "successor")) is None:
            try:
                model_service.add_relationship(db, None, model_id, successor, "successor")
            except ServiceError as exc:
                db.rollback()
                report.errors.append(f"T02_models.csv successor {model_id} → {successor}: {exc.message}")

    run("T03_validations.csv", "validation_id", lambda r: db.get(Validation, r["validation_id"]) is not None,
        lambda r: validation_service.create_validation(db, None, {**r, "source": "Import"}))
    run("T04_findings.csv", "finding_id", lambda r: db.get(Finding, r["finding_id"]) is not None,
        lambda r: finding_service.create_finding(db, None, {**r, "source": "Import"}))
    run("T05_approvals.csv", "approval_id", lambda r: db.get(Approval, r["approval_id"]) is not None,
        lambda r: approval_service.create_approval(db, None, r))
    return report
