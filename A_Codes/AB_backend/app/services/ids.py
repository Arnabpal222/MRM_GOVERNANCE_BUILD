from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import InstrumentedAttribute


def next_id(db: Session, column: InstrumentedAttribute, prefix: str, width: int = 4) -> str:
    """Next sequential business ID such as F-0024. Unique constraints guard against races."""
    current = db.scalar(select(func.max(column)).where(column.like(f"{prefix}-%")))
    number = int(current.split("-")[-1]) + 1 if current else 1
    return f"{prefix}-{number:0{width}d}"
