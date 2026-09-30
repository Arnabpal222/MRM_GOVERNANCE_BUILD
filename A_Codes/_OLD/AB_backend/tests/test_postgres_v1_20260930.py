"""PostgreSQL integration tests. Run after `alembic upgrade head`, with
MRM_TEST_POSTGRES_URL pointing at the migrated database, e.g.
    MRM_TEST_POSTGRES_URL=postgresql+psycopg://mrm:mrm_dev_password@localhost:5432/mrm pytest -m postgres
"""
import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

URL = os.environ.get("MRM_TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not URL, reason="MRM_TEST_POSTGRES_URL not set")


@pytest.fixture
def conn():
    engine = create_engine(URL)
    with engine.connect() as c:
        trans = c.begin()
        yield c
        trans.rollback()
    engine.dispose()


def test_migration_created_foundation_tables(conn):
    tables = set(conn.scalars(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")))
    assert {"app_user", "user_role", "policy_setting", "audit_event", "alembic_version"} <= tables


@pytest.mark.parametrize("statement", [
    "UPDATE audit_event SET action = 'tampered' WHERE event_id = :id",
    "DELETE FROM audit_event WHERE event_id = :id",
])
def test_audit_event_is_append_only(conn, statement):
    event_id = conn.scalar(text(
        "INSERT INTO audit_event (action, entity, entity_id) VALUES ('create', 'test', 'x') RETURNING event_id"
    ))
    with pytest.raises(DBAPIError, match="append-only"):
        conn.execute(text(statement), {"id": event_id})
