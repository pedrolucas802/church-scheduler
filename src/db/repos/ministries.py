from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.db.engine import engine
from src.db.schema import ministries, ministry_memberships, users


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def ensure_ministry(slug: str, name: str) -> int:
    now = _now_iso()
    slug = (slug or "").strip().lower()
    name = (name or "").strip()

    if not slug:
        raise ValueError("Ministry slug is required")
    if not name:
        raise ValueError("Ministry name is required")

    stmt = (
        pg_insert(ministries)
        .values(
            slug=slug,
            name=name,
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_update(
            index_elements=[ministries.c.slug],
            set_={
                "name": name,
                "updated_at": now,
            },
        )
    )

    with engine().begin() as conn:
        conn.execute(stmt)
        mid = conn.execute(
            select(ministries.c.id).where(ministries.c.slug == slug)
        ).scalar_one()
        return int(mid)


def upsert_ministry(data: dict) -> int:
    """
    Expected payload:
      {
        "id": optional,
        "slug": "...",
        "name": "..."
      }

    Behavior:
      - if id is provided, update that ministry
      - otherwise upsert by slug
    """
    now = _now_iso()
    data = dict(data or {})

    ministry_id = data.get("id")
    slug = (data.get("slug") or "").strip().lower()
    name = (data.get("name") or "").strip()

    if not slug:
        raise ValueError("Ministry slug is required")
    if not name:
        raise ValueError("Ministry name is required")

    with engine().begin() as conn:
        if ministry_id:
            ministry_id = int(ministry_id)

            # if slug changed, keep uniqueness behavior by letting DB enforce unique slug
            conn.execute(
                ministries.update()
                .where(ministries.c.id == ministry_id)
                .values(
                    slug=slug,
                    name=name,
                    updated_at=now,
                )
            )

            mid = conn.execute(
                select(ministries.c.id).where(ministries.c.id == ministry_id)
            ).scalar_one()
            return int(mid)

        stmt = (
            pg_insert(ministries)
            .values(
                slug=slug,
                name=name,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=[ministries.c.slug],
                set_={
                    "name": name,
                    "updated_at": now,
                },
            )
        )
        conn.execute(stmt)

        mid = conn.execute(
            select(ministries.c.id).where(ministries.c.slug == slug)
        ).scalar_one()
        return int(mid)


def list_ministries():
    stmt = (
        select(
            ministries.c.id,
            ministries.c.slug,
            ministries.c.name,
            ministries.c.created_at,
            ministries.c.updated_at,
        )
        .order_by(ministries.c.name.asc())
    )

    with engine().connect() as conn:
        return conn.execute(stmt).fetchall()


def list_ministry_leaders(ministry_id: int):
    """
    Leaders are ministry_memberships with role='admin'
    Returns:
      (user_id, username, email, full_name)
    """
    stmt = (
        select(
            users.c.id.label("user_id"),
            users.c.username,
            users.c.email,
            users.c.full_name,
        )
        .select_from(
            ministry_memberships.join(users, users.c.id == ministry_memberships.c.user_id)
        )
        .where(ministry_memberships.c.ministry_id == int(ministry_id))
        .where(ministry_memberships.c.role == "admin")
        .order_by(users.c.full_name.asc(), users.c.username.asc())
    )

    with engine().connect() as conn:
        return conn.execute(stmt).fetchall()


def set_ministry_leader(ministry_id: int, user_id: int, is_leader: bool) -> None:
    """
    If is_leader=True:
      ensure membership exists with role='admin'
    If is_leader=False:
      remove admin membership for this user in this ministry
    """
    ministry_id = int(ministry_id)
    user_id = int(user_id)

    with engine().begin() as conn:
        if is_leader:
            stmt = (
                pg_insert(ministry_memberships)
                .values(
                    ministry_id=ministry_id,
                    user_id=user_id,
                    role="admin",
                )
                .on_conflict_do_update(
                    index_elements=[
                        ministry_memberships.c.ministry_id,
                        ministry_memberships.c.user_id,
                    ],
                    set_={"role": "admin"},
                )
            )
            conn.execute(stmt)
            return

        conn.execute(
            delete(ministry_memberships)
            .where(ministry_memberships.c.ministry_id == ministry_id)
            .where(ministry_memberships.c.user_id == user_id)
            .where(ministry_memberships.c.role == "admin")
        )