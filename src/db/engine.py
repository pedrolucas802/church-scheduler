import os
from typing import Optional
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL or not str(DATABASE_URL).startswith("postgresql"):
    raise RuntimeError(
        "DATABASE_URL must be set and must be a PostgreSQL URL, e.g. "
        "'postgresql+psycopg2://user:pass@host:5432/dbname'"
    )

_engine: Optional[Engine] = None

def engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(DATABASE_URL, future=True, pool_pre_ping=True)
    return _engine