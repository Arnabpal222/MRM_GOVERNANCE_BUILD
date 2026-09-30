"""Object storage for binary content (BRD §50). PostgreSQL holds the metadata; this holds the bytes.

MinioStore is the target; LocalStore is a development fallback with the same key layout.
"""
import io
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Protocol

from app.config import get_settings


class ObjectStore(Protocol):
    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None: ...
    def get(self, key: str) -> bytes: ...
    def exists(self, key: str) -> bool: ...


def _safe_key(key: str) -> str:
    p = PurePosixPath(key)
    if p.is_absolute() or ".." in p.parts or not key.strip():
        raise ValueError(f"Unsafe storage key: {key!r}")
    return str(p)


class LocalStore:
    def __init__(self, root: Path):
        self.root = root

    def _path(self, key: str) -> Path:
        return self.root / _safe_key(key)

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()


class MinioStore:
    def __init__(self):
        from minio import Minio

        s = get_settings()
        self.bucket = s.minio_bucket
        self.client = Minio(s.minio_endpoint, access_key=s.minio_access_key, secret_key=s.minio_secret_key,
                            secure=s.minio_secure)
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        self.client.put_object(self.bucket, _safe_key(key), io.BytesIO(data), len(data), content_type=content_type)

    def get(self, key: str) -> bytes:
        resp = self.client.get_object(self.bucket, _safe_key(key))
        try:
            return resp.read()
        finally:
            resp.close()
            resp.release_conn()

    def exists(self, key: str) -> bool:
        from minio.error import S3Error

        try:
            self.client.stat_object(self.bucket, _safe_key(key))
            return True
        except S3Error:
            return False


@lru_cache
def get_store() -> ObjectStore:
    s = get_settings()
    if s.storage_backend == "local":
        return LocalStore(s.local_storage_dir)
    if s.storage_backend == "minio":
        return MinioStore()
    raise ValueError(f"Unknown storage backend '{s.storage_backend}'. Use 'minio' or 'local'.")
