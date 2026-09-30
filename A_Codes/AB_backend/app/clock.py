from datetime import date

from app.config import get_settings


def today() -> date:
    """Business date used by every rule. Overridable via MRM_TODAY_OVERRIDE for demos and tests."""
    return get_settings().today_override or date.today()
