"""Unit/API tests run against in-memory SQLite so they need no running infrastructure.
PostgreSQL-specific behaviour (e.g. the audit immutability trigger) is covered by
tests marked `postgres`, which run only when MRM_TEST_POSTGRES_URL is set."""
import importlib.util
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.db import get_db
from app.main import create_app
from app.models import Base
from app.services.bootstrap_service import load_bootstrap

TODAY = date(2026, 9, 30)
GENERATOR = Path(__file__).resolve().parents[2] / "AD_seed" / "generate_samples.py"


@pytest.fixture(autouse=True)
def fixed_today():
    """All rule tests run on a fixed business date."""
    settings = get_settings()
    previous = settings.today_override
    settings.today_override = TODAY
    yield TODAY
    settings.today_override = previous


@pytest.fixture
def db_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with Session() as session:
        load_bootstrap(session, get_settings().bootstrap_dir)
    yield Session
    engine.dispose()


@pytest.fixture(scope="session")
def sample_dir(tmp_path_factory) -> Path:
    """Sample data generated for the fixed test date, independent of B_Inputs contents."""
    spec = importlib.util.spec_from_file_location("generate_samples", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    out = tmp_path_factory.mktemp("samples")
    module.generate(out, TODAY, generic=60)
    return out


@pytest.fixture
def loaded_session(db_session, sample_dir):
    from app.services.sample_loader import load_samples

    with db_session() as s:
        report = load_samples(s, sample_dir)
    assert report.errors == []
    return db_session


def _client_for(session_factory) -> TestClient:
    app = create_app()

    def _get_db():
        with session_factory() as s:
            yield s

    app.dependency_overrides[get_db] = _get_db
    return TestClient(app)


@pytest.fixture
def client(db_session):
    return _client_for(db_session)


@pytest.fixture
def loaded_client(loaded_session):
    return _client_for(loaded_session)


def login(client: TestClient, user_id: str, role: str) -> dict[str, str]:
    resp = client.post("/api/auth/login", json={"user_id": user_id, "role": role})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


ADMIN = ("U-001", "Admin")
AUDITOR = ("U-041", "Auditor")
EXECUTIVE = ("U-042", "Executive")
VALIDATOR = ("U-014", "Validator")
MRC = ("U-040", "MRC Member")
