from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import DbSession
from app.config import get_settings
from app.schemas.core import ComponentHealth, HealthResponse

router = APIRouter(prefix="/api", tags=["health"])


def _check_db(db) -> ComponentHealth:
    try:
        db.execute(text("SELECT 1"))
        return ComponentHealth(status="ok")
    except Exception as exc:  # noqa: BLE001 — health must report, not raise
        return ComponentHealth(status="down", detail=type(exc).__name__)


def _check_redis() -> ComponentHealth:
    try:
        import redis

        redis.Redis.from_url(get_settings().redis_url, socket_connect_timeout=1, socket_timeout=1).ping()
        return ComponentHealth(status="ok")
    except Exception as exc:  # noqa: BLE001
        return ComponentHealth(status="down", detail=type(exc).__name__)


def _check_object_store() -> ComponentHealth:
    try:
        import urllib3
        from minio import Minio

        s = get_settings()
        http = urllib3.PoolManager(timeout=urllib3.Timeout(connect=1, read=2), retries=False)
        client = Minio(s.minio_endpoint, access_key=s.minio_access_key, secret_key=s.minio_secret_key,
                       secure=s.minio_secure, http_client=http)
        exists = client.bucket_exists(s.minio_bucket)
        return ComponentHealth(status="ok", detail=None if exists else f"bucket '{s.minio_bucket}' not created yet")
    except Exception as exc:  # noqa: BLE001
        return ComponentHealth(status="down", detail=type(exc).__name__)


@router.get("/health", response_model=HealthResponse)
def health(db: DbSession):
    components = {"database": _check_db(db), "redis": _check_redis(), "object_store": _check_object_store()}
    if components["database"].status != "ok":
        overall = "down"
    elif any(c.status != "ok" for c in components.values()):
        overall = "degraded"
    else:
        overall = "ok"
    return HealthResponse(status=overall, components=components)
