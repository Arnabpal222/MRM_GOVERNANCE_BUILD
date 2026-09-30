"""Unit/API tests run against in-memory SQLite so they need no running infrastructure.
PostgreSQL-specific behaviour (e.g. the audit immutability trigger) is covered by
tests marked `postgres`, which run only when MRM_TEST_POSTGRES_URL is set."""
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


@pytest.fixture
def client(db_session):
    app = create_app()

    def _get_db():
        with db_session() as s:
            yield s

    app.dependency_overrides[get_db] = _get_db
    return TestClient(app)


def login(client: TestClient, user_id: str, role: str) -> dict[str, str]:
    resp = client.post("/api/auth/login", json={"user_id": user_id, "role": role})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


ADMIN = ("U-001", "Admin")
AUDITOR = ("U-041", "Auditor")
EXECUTIVE = ("U-042", "Executive")
VALIDATOR = ("U-014", "Validator")
