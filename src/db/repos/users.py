from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.db.engine import engine
from src.db.schema import users


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def upsert_user_from_kc(userinfo: Dict[str, Any]) -> int:
    """
    Creates/updates local user from Keycloak userinfo.
    Returns local users.id
    """
    now = _now_iso()
    kc_sub = str(userinfo.get("sub") or "").strip()
    if not kc_sub:
        raise RuntimeError("Keycloak userinfo missing 'sub'.")

    username = (userinfo.get("preferred_username") or userinfo.get("email") or "").strip() or None
    email = (userinfo.get("email") or "").strip().lower() or None
    full_name = (userinfo.get("name") or "").strip() or None

    insert_values = dict(
        kc_sub=kc_sub,
        username=username,
        email=email,
        full_name=full_name,
        created_at=now,
        updated_at=now,
    )
    update_values = dict(
        username=username,
        email=email,
        full_name=full_name,
        updated_at=now,
    )

    stmt = (
        pg_insert(users)
        .values(**insert_values)
        .on_conflict_do_update(
            index_elements=[users.c.kc_sub],
            set_=update_values,
        )
        .returning(users.c.id)
    )

    with engine().begin() as conn:
        uid = conn.execute(stmt).scalar_one()
        return int(uid)


def get_user_by_kc_sub(kc_sub: str) -> Optional[dict]:
    stmt = (
        select(
            users.c.id,
            users.c.kc_sub,
            users.c.username,
            users.c.email,
            users.c.full_name,
            users.c.created_at,
            users.c.updated_at,
        )
        .where(users.c.kc_sub == kc_sub)
        .limit(1)
    )

    with engine().connect() as conn:
        row = conn.execute(stmt).fetchone()
        if not row:
            return None
        return dict(row._mapping)


def update_user_profile(kc_sub: str, full_name: str, email: str) -> None:
    """
    Updates the local app profile for a Keycloak-linked user.
    Does NOT update Keycloak itself.
    """
    kc_sub = (kc_sub or "").strip()
    full_name = (full_name or "").strip()
    email = (email or "").strip().lower()

    if not kc_sub:
        raise ValueError("kc_sub is required")
    if not full_name:
        raise ValueError("full_name is required")
    if not email:
        raise ValueError("email is required")

    with engine().begin() as conn:
        existing = conn.execute(
            select(users.c.id).where(users.c.kc_sub == kc_sub).limit(1)
        ).scalar()

        if not existing:
            raise RuntimeError("User not found for kc_sub")

        conn.execute(
            update(users)
            .where(users.c.kc_sub == kc_sub)
            .values(
                full_name=full_name,
                email=email,
                updated_at=_now_iso(),
            )
        )


def list_users():
    stmt = select(
        users.c.id,
        users.c.kc_sub,
        users.c.username,
        users.c.email,
        users.c.full_name,
        users.c.created_at,
        users.c.updated_at,
    ).order_by(users.c.full_name.asc(), users.c.username.asc())

    with engine().connect() as conn:
        return conn.execute(stmt).fetchall()


def get_user_by_username(username: str) -> Optional[dict]:
    stmt = (
        select(
            users.c.id,
            users.c.kc_sub,
            users.c.username,
            users.c.email,
            users.c.full_name,
            users.c.created_at,
            users.c.updated_at,
        )
        .where(users.c.username == username)
        .limit(1)
    )

    with engine().connect() as conn:
        row = conn.execute(stmt).fetchone()
        if not row:
            return None
        return dict(row._mapping)
