"""Parsing and validation of policy_setting values by value_type. Pure functions."""
from decimal import Decimal, InvalidOperation

VALUE_TYPES = ("integer", "decimal", "percent", "text", "list", "boolean")


class PolicyValueError(ValueError):
    pass


def parse_policy_value(value: str, value_type: str):
    """Return the typed value, or raise PolicyValueError with a human-readable message."""
    if value_type not in VALUE_TYPES:
        raise PolicyValueError(f"Unknown value type '{value_type}'. Allowed: {', '.join(VALUE_TYPES)}.")
    raw = (value or "").strip()
    if value_type == "text":
        if not raw:
            raise PolicyValueError("A text setting cannot be blank.")
        return raw
    if value_type == "list":
        items = [item.strip() for item in raw.split(";") if item.strip()]
        if not items:
            raise PolicyValueError("A list setting needs at least one item, separated by ';'.")
        return items
    if value_type == "boolean":
        if raw.upper() in ("Y", "TRUE", "YES"):
            return True
        if raw.upper() in ("N", "FALSE", "NO"):
            return False
        raise PolicyValueError(f"'{raw}' is not a yes/no value. Use Y or N.")
    if value_type == "integer":
        try:
            return int(raw)
        except ValueError:
            raise PolicyValueError(f"'{raw}' is not a whole number.") from None
    try:
        number = Decimal(raw)
    except InvalidOperation:
        raise PolicyValueError(f"'{raw}' is not a number.") from None
    if value_type == "percent" and not (0 <= number <= 100):
        raise PolicyValueError(f"{raw} is outside 0–100. Percentages are whole numbers, e.g. 98 means 98%.")
    return number


def normalise_policy_value(value: str, value_type: str) -> str:
    """Canonical text form that is stored in the database."""
    parsed = parse_policy_value(value, value_type)
    if value_type == "list":
        return "; ".join(parsed)
    if value_type == "boolean":
        return "Y" if parsed else "N"
    return str(parsed)
