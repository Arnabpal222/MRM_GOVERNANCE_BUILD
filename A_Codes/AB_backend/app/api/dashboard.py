from fastapi import APIRouter

from app.api.deps import CurrentPrincipal, DbSession
from app.services import dashboard_service

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary")
def summary(db: DbSession, _: CurrentPrincipal):
    """Command Center: tiles, distributions, revalidation timeline and generated insights."""
    return dashboard_service.summary(db)
