# src/db/init.py
from __future__ import annotations

from src.db.engine import engine
from src.db.schema import metadata


def init_db() -> None:
    """
    Initialize database tables using SQLAlchemy metadata.
    """
    metadata.create_all(engine())