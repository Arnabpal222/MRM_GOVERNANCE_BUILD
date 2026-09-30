"""Background job runner (BRD §45). Long imports never block the request.

The thread executor is the development/single-node implementation; the job functions are
self-contained (they take a session factory and IDs) so they can move to Celery/RQ workers in the
hardening phase without changing callers. Live progress lives in an in-process store for the same reason.
"""
import logging
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from app.config import get_settings

log = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="mrm-job")


def submit(fn: Callable, *args) -> None:
    if get_settings().job_mode == "inline":
        fn(*args)
        return

    def _run():
        try:
            fn(*args)
        except Exception:  # noqa: BLE001 — job functions record their own failure; this is the last resort log
            log.exception("Background job %s failed", getattr(fn, "__name__", fn))

    _executor.submit(_run)


class ProgressStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._data: dict[str, dict] = {}

    def set(self, key: str, **values) -> None:
        with self._lock:
            self._data.setdefault(key, {}).update(values)

    def get(self, key: str) -> dict | None:
        with self._lock:
            return dict(self._data[key]) if key in self._data else None

    def clear(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)


progress = ProgressStore()
