# src/db/repos/volunteers.py
from __future__ import annotations

import os
import re
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.db.engine import engine
from src.db.schema import users, volunteer_prefs, ministry_memberships


def _default_ministry_id() -> int:
    raw = (os.getenv("DEFAULT_MINISTRY_ID") or "").strip()
    if raw.isdigit():
        return int(raw)
    return 1


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _as01(v) -> int:
    return 1 if bool(v) else 0


def _slug_username(name: str) -> str:
    base = (name or "").strip().lower()
    base = re.sub(r"[^a-z0-9]+", ".", base).strip(".")
    if not base:
        base = "volunteer"
    # keep it short-ish
    base = base[:18].strip(".") or "volunteer"
    return f"{base}.{uuid.uuid4().hex[:4]}"


def _find_user_id(email: str | None, name: str | None) -> Optional[int]:
    email = (email or "").strip().lower() or None
    name = (name or "").strip() or None

    with engine().connect() as conn:
        if email:
            uid = conn.execute(
                select(users.c.id).where(users.c.email.ilike(email)).limit(1)
            ).scalar()
            if uid:
                return int(uid)

        if name:
            uid = conn.execute(
                select(users.c.id).where(users.c.full_name == name).limit(1)
            ).scalar()
            if uid:
                return int(uid)

    return None


def _ensure_user(email: str | None, name: str) -> int:
    """
    Ensure there is a user row for this volunteer (for local/public signup).
    If Keycloak sync already created users, we'll reuse them by email/name.
    """
    uid = _find_user_id(email=email, name=name)
    if uid:
        return uid

    name = (name or "").strip() or "Volunteer"
    email = (email or "").strip().lower() or None

    new_kc_sub = f"local-{uuid.uuid4().hex}"
    new_username = _slug_username(name)

    with engine().begin() as conn:
        # Try insert; if a unique constraint exists and this conflicts, we'll re-query.
        try:
            conn.execute(
                pg_insert(users).values(
                    kc_sub=new_kc_sub,
                    username=new_username,
                    email=email,
                    full_name=name,
                    created_at=_now_iso(),
                    updated_at=_now_iso(),
                )
            )
        except Exception:
            pass

    uid2 = _find_user_id(email=email, name=name)
    if not uid2:
        raise RuntimeError("Could not create or find user for volunteer.")
    return uid2


def _ensure_membership(ministry_id: int, user_id: int, role: str = "volunteer") -> None:
    """
    Ensure the user belongs to the ministry (so they appear in ministry-scoped lists).
    """
    with engine().begin() as conn:
        stmt = (
            pg_insert(ministry_memberships)
            .values(
                ministry_id=int(ministry_id),
                user_id=int(user_id),
                role=str(role),
            )
            .on_conflict_do_nothing(index_elements=[ministry_memberships.c.ministry_id, ministry_memberships.c.user_id])
        )
        conn.execute(stmt)


# -------------------------------------------------------------------
# LEGACY-COMPATIBLE API (what your Streamlit pages expect)
# -------------------------------------------------------------------

def list_volunteers(active_only: bool = False, ministry_ids: Optional[list[int]] = None):
    """
    Legacy signature used by pages:
      list_volunteers(active_only=False)

    Returns tuples in THIS EXACT ORDER (what your pages assume):
      (id, name, phone, email, active, thu_ok, sun_ok, can_obs, can_fixed, can_mobile)

    Notes:
      - id is users.id
      - phone/prefs come from volunteer_prefs (per ministry)
      - only members (admin/volunteer) are included
    """
    if ministry_ids is None:
        ministry_ids = [_default_ministry_id()]

    stmt = (
        select(
            users.c.id.label("id"),
            users.c.full_name.label("name"),
            volunteer_prefs.c.phone.label("phone"),
            users.c.email.label("email"),
            volunteer_prefs.c.active.label("active"),
            volunteer_prefs.c.thu_ok.label("thu_ok"),
            volunteer_prefs.c.sun_ok.label("sun_ok"),
            volunteer_prefs.c.can_obs.label("can_obs"),
            volunteer_prefs.c.can_fixed.label("can_fixed"),
            volunteer_prefs.c.can_mobile.label("can_mobile"),
        )
        .select_from(
            ministry_memberships
            .join(users, users.c.id == ministry_memberships.c.user_id)
            .outerjoin(
                volunteer_prefs,
                (volunteer_prefs.c.user_id == users.c.id)
                & (volunteer_prefs.c.ministry_id == ministry_memberships.c.ministry_id),
            )
        )
        .where(ministry_memberships.c.ministry_id.in_(ministry_ids))
        .where(ministry_memberships.c.role.in_(["admin", "volunteer"]))
        .order_by(users.c.full_name.asc().nulls_last(), users.c.username.asc().nulls_last())
    )

    if active_only:
        stmt = stmt.where(volunteer_prefs.c.active == 1)

    with engine().connect() as conn:
        rows = conn.execute(stmt).fetchall()

    out = []
    for r in rows:
        m = r._mapping
        out.append(
            (
                int(m["id"]),
                (m["name"] or "").strip() or None,
                (m["phone"] or None),
                (m["email"] or None),
                int(m["active"] if m["active"] is not None else 1),
                int(m["thu_ok"] if m["thu_ok"] is not None else 1),
                int(m["sun_ok"] if m["sun_ok"] is not None else 1),
                int(m["can_obs"] if m["can_obs"] is not None else 1),
                int(m["can_fixed"] if m["can_fixed"] is not None else 1),
                int(m["can_mobile"] if m["can_mobile"] is not None else 1),
            )
        )
    return out


def upsert_volunteer(data: dict, ministry_id: Optional[int] = None) -> None:
    """
    Legacy wrapper used by Volunteers page:
      upsert_volunteer({name,email,phone,active,thu_ok,...})

    In the new model:
      - ensures a user exists
      - ensures membership exists
      - upserts volunteer_prefs for that ministry
    """
    ministry_id = int(ministry_id or _default_ministry_id())
    cleaned = dict(data or {})

    name = (cleaned.get("name") or "").strip()
    if not name:
        raise ValueError("Volunteer name is required")

    email = (cleaned.get("email") or None)
    if email is not None:
        email = str(email).strip().lower() or None

    phone = cleaned.get("phone") or None
    if phone is not None:
        phone = str(phone).strip() or None

    user_id = _ensure_user(email=email, name=name)
    _ensure_membership(ministry_id, user_id, role="volunteer")

    insert_values = dict(
        ministry_id=ministry_id,
        user_id=user_id,
        phone=phone,
        active=_as01(cleaned.get("active", 1)),
        thu_ok=_as01(cleaned.get("thu_ok", 1)),
        sun_ok=_as01(cleaned.get("sun_ok", 1)),
        can_obs=_as01(cleaned.get("can_obs", 1)),
        can_fixed=_as01(cleaned.get("can_fixed", 1)),
        can_mobile=_as01(cleaned.get("can_mobile", 1)),
    )

    update_values = {k: v for k, v in insert_values.items() if k not in ("ministry_id", "user_id")}

    stmt = (
        pg_insert(volunteer_prefs)
        .values(**insert_values)
        .on_conflict_do_update(
            index_elements=[volunteer_prefs.c.ministry_id, volunteer_prefs.c.user_id],
            set_=update_values,
        )
    )

    with engine().begin() as conn:
        conn.execute(stmt)


def set_volunteer_active(user_id: int, active: bool, ministry_id: Optional[int] = None) -> None:
    """
    Legacy wrapper used by Volunteers page:
      set_volunteer_active(user_id, True/False)

    Applies to DEFAULT_MINISTRY_ID unless provided.
    """
    ministry_id = int(ministry_id or _default_ministry_id())
    _ensure_membership(ministry_id, int(user_id), role="volunteer")

    stmt = (
        pg_insert(volunteer_prefs)
        .values(
            ministry_id=ministry_id,
            user_id=int(user_id),
            active=_as01(active),
            thu_ok=1,
            sun_ok=1,
            can_obs=1,
            can_fixed=1,
            can_mobile=1,
        )
        .on_conflict_do_update(
            index_elements=[volunteer_prefs.c.ministry_id, volunteer_prefs.c.user_id],
            set_={"active": _as01(active)},
        )
    )

    with engine().begin() as conn:
        conn.execute(stmt)

def upsert_volunteer_prefs(ministry_id: int, user_id: int, data: dict) -> None:
    """
    New API used by db/__init__.py (and future pages).
    Upserts per-ministry volunteer preferences for an existing user.
    """
    cleaned = dict(data or {})
    ministry_id = int(ministry_id)
    user_id = int(user_id)

    phone = cleaned.get("phone") or None
    if phone is not None:
        phone = str(phone).strip() or None

    insert_values = dict(
        ministry_id=ministry_id,
        user_id=user_id,
        phone=phone,
        active=_as01(cleaned.get("active", 1)),
        thu_ok=_as01(cleaned.get("thu_ok", 1)),
        sun_ok=_as01(cleaned.get("sun_ok", 1)),
        can_obs=_as01(cleaned.get("can_obs", 1)),
        can_fixed=_as01(cleaned.get("can_fixed", 1)),
        can_mobile=_as01(cleaned.get("can_mobile", 1)),
    )

    update_values = {k: v for k, v in insert_values.items() if k not in ("ministry_id", "user_id")}

    stmt = (
        pg_insert(volunteer_prefs)
        .values(**insert_values)
        .on_conflict_do_update(
            index_elements=[volunteer_prefs.c.ministry_id, volunteer_prefs.c.user_id],
            set_=update_values,
        )
    )

    with engine().begin() as conn:
        conn.execute(stmt)


# Back-compat alias (some code imports this name)
def upsert_volunteer_pref(*args, **kwargs):
    return upsert_volunteer_prefs(*args, **kwargs)