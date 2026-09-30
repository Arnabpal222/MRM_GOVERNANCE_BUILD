"""Unit/API tests run against in-memory SQLite so they need no running infrastructure.
PostgreSQL-specific behaviour (e.g. the audit immutability trigger) is covered by
tests marked `postgres`, which run only when MRM_TEST_POSTGRES_URL is set."""
import importlib.util
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.db import configure_sqlite, get_db, get_session_factory
from app.main import create_app
from app.models import Base
from app.services.bootstrap_service import load_bootstrap

TODAY = date(2026, 9, 30)
GENERATOR = Path(__file__).resolve().parents[2] / "AD_seed" / "generate_samples.py"


@pytest.fixture(autouse=True)
def test_settings(tmp_path):
    """Fixed business date, local object store, inline jobs and temporary seed folders for every test."""
    settings = get_settings()
    overrides = {"today_override": TODAY, "storage_backend": "local", "local_storage_dir": tmp_path / "store",
                 "job_mode": "inline", "allow_reset": True, "seed_dir": tmp_path / "seed",
                 "demo_files_dir": tmp_path / "demo", "regenerate_seed_on_reset": True}
    previous = {k: getattr(settings, k) for k in overrides}
    for k, v in overrides.items():
        setattr(settings, k, v)
    from app.storage import get_store
    get_store.cache_clear()
    yield settings
    for k, v in previous.items():
        setattr(settings, k, v)
    get_store.cache_clear()


@pytest.fixture
def db_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    configure_sqlite(engine)  # savepoints + foreign keys, as in app.db

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with Session() as session:
        load_bootstrap(session, get_settings().bootstrap_dir)
    yield Session
    engine.dispose()


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def demo_dir(tmp_path_factory) -> Path:
    """Demo upload files (design §10) generated for the fixed test date."""
    out = tmp_path_factory.mktemp("demo")
    seed = _load_module("generate_seed", GENERATOR.parent / "generate_seed.py")
    seed.demo_files(TODAY, seed._policy(seed._policy_rows()), out)
    return out


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
    app.dependency_overrides[get_session_factory] = lambda: session_factory
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


@pytest.fixture(scope="session")
def make_pdf():
    """Valid single-page PDF bytes (same writer as the seed evidence)."""
    return _load_module("generate_seed_pdf", GENERATOR.parent / "generate_seed.py").make_pdf


def make_docx(text: str) -> bytes:
    """Minimal valid DOCX (Office Open XML) with one paragraph."""
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
        z.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
        z.writestr("word/document.xml", f'<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>')
    return buf.getvalue()
