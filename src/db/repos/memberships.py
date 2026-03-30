from sqlalchemy import select, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.db.engine import engine
from src.db.schema import ministry_memberships


def upsert_membership(ministry_id: int, user_id: int, role: str) -> None:
    role = role.strip().lower()
    if role not in ("admin", "volunteer"):
        raise ValueError("role must be 'admin' or 'volunteer'")

    stmt = (
        pg_insert(ministry_memberships)
        .values(ministry_id=ministry_id, user_id=user_id, role=role)
        .on_conflict_do_update(
            index_elements=[ministry_memberships.c.ministry_id, ministry_memberships.c.user_id],
            set_={"role": role},
        )
    )
    with engine().begin() as conn:
        conn.execute(stmt)

def list_user_ministries(user_id: int):
    stmt = select(
        ministry_memberships.c.ministry_id,
        ministry_memberships.c.role
    ).where(ministry_memberships.c.user_id == user_id)

    with engine().connect() as conn:
        return conn.execute(stmt).fetchall()

def is_ministry_admin(ministry_id: int, user_id: int) -> bool:
    stmt = select(ministry_memberships.c.id).where(
        (ministry_memberships.c.ministry_id == ministry_id)
        & (ministry_memberships.c.user_id == user_id)
        & (ministry_memberships.c.role == "admin")
    ).limit(1)

    with engine().connect() as conn:
        return conn.execute(stmt).fetchone() is not None

def remove_membership(ministry_id: int, user_id: int) -> None:
    with engine().begin() as conn:
        conn.execute(
            delete(ministry_memberships).where(
                (ministry_memberships.c.ministry_id == ministry_id)
                & (ministry_memberships.c.user_id == user_id)
            )
        )