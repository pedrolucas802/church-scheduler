# src/db/repos/schedule.py
from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from sqlalchemy import select, delete, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.db.engine import engine
from src.db.schema import services, assignments, users, reminder_jobs, swap_requests


def _default_ministry_id() -> int:
    raw = (os.getenv("DEFAULT_MINISTRY_ID") or "").strip()
    if raw.isdigit():
        return int(raw)
    return 1


def ensure_service(ministry_id: int, dt_iso: str) -> int:
    """
    Ensures a ministry-scoped service exists.
    Returns services.id
    """
    stmt = (
        pg_insert(services)
        .values(ministry_id=int(ministry_id), dt_iso=dt_iso)
        .on_conflict_do_nothing(index_elements=[services.c.ministry_id, services.c.dt_iso])
    )
    with engine().begin() as conn:
        conn.execute(stmt)
        sid = conn.execute(
            select(services.c.id).where(
                (services.c.ministry_id == int(ministry_id)) & (services.c.dt_iso == dt_iso)
            )
        ).scalar_one()
        return int(sid)


def upsert_assignment(service_id: int, role: str, user_id: Optional[int]) -> None:
    """
    Upsert assignment for a service-role pair.
    """
    stmt = (
        pg_insert(assignments)
        .values(service_id=int(service_id), role=str(role), user_id=(int(user_id) if user_id is not None else None))
        .on_conflict_do_update(
            index_elements=[assignments.c.service_id, assignments.c.role],
            set_={"user_id": (int(user_id) if user_id is not None else None)},
        )
    )
    with engine().begin() as conn:
        conn.execute(stmt)


def list_schedule_between(
    start_iso: str,
    end_iso: str,
    ministry_ids: Optional[list[int]] = None,
):
    """
    LEGACY-COMPATIBLE signature for pages:
      list_schedule_between(start_iso, end_iso)

    Also supports:
      list_schedule_between(start_iso, end_iso, ministry_ids=[1,2])

    Returns:
      (service_id, dt_iso, assignment_id, role, volunteer_name)
    """
    stmt = (
        select(
            services.c.id.label("service_id"),
            services.c.dt_iso.label("dt_iso"),
            assignments.c.id.label("assignment_id"),
            assignments.c.role.label("role"),
            users.c.full_name.label("full_name"),
            users.c.username.label("username"),
            users.c.email.label("email"),
        )
        .select_from(
            services
            .outerjoin(assignments, assignments.c.service_id == services.c.id)
            .outerjoin(users, users.c.id == assignments.c.user_id)
        )
    )
    if ministry_ids is not None:
        stmt = stmt.where(services.c.ministry_id.in_(ministry_ids))
    stmt = stmt.where((services.c.dt_iso >= start_iso) & (services.c.dt_iso < end_iso))
    stmt = stmt.order_by(services.c.dt_iso.asc(), assignments.c.role.asc())

    with engine().connect() as conn:
        rows = conn.execute(stmt).fetchall()

    out = []
    for r in rows:
        m = r._mapping
        name = (m["full_name"] or "").strip() or (m["username"] or "").strip() or (m["email"] or "").strip() or None
        out.append(
            (
                int(m["service_id"]),
                m["dt_iso"],
                int(m["assignment_id"]) if m["assignment_id"] is not None else None,
                m["role"],
                name,
            )
        )
    return out


def list_services_in_month(ministry_id: int, year: int, month: int):
    """
    Returns list of (service_id, dt_iso) for a given ministry and month.
    """
    stmt = (
        select(services.c.id, services.c.dt_iso)
        .where(services.c.ministry_id == int(ministry_id))
        .order_by(services.c.dt_iso.asc())
    )

    out = []
    with engine().connect() as conn:
        for sid, dt_iso in conn.execute(stmt).fetchall():
            dt = datetime.fromisoformat(dt_iso)
            if dt.year == year and dt.month == month:
                out.append((int(sid), dt_iso))
    return out


def get_assignment_details(assignment_id: int):
    """
    Returns:
      (assignment_id, service_id, dt_iso, role, user_id, volunteer_name)
    """
    stmt = (
        select(
            assignments.c.id.label("assignment_id"),
            assignments.c.service_id.label("service_id"),
            services.c.dt_iso.label("dt_iso"),
            assignments.c.role.label("role"),
            assignments.c.user_id.label("user_id"),
            users.c.full_name.label("full_name"),
            users.c.username.label("username"),
            users.c.email.label("email"),
        )
        .select_from(
            assignments
            .join(services, services.c.id == assignments.c.service_id)
            .outerjoin(users, users.c.id == assignments.c.user_id)
        )
        .where(assignments.c.id == int(assignment_id))
        .limit(1)
    )
    with engine().connect() as conn:
        row = conn.execute(stmt).fetchone()
        if not row:
            return None
        m = row._mapping
        name = (m["full_name"] or "").strip() or (m["username"] or "").strip() or (m["email"] or "").strip() or None
        return (
            int(m["assignment_id"]),
            int(m["service_id"]),
            m["dt_iso"],
            m["role"],
            m["user_id"],
            name,
        )


def set_assignment_user_by_id(assignment_id: int, user_id: Optional[int]) -> None:
    with engine().begin() as conn:
        conn.execute(
            update(assignments)
            .where(assignments.c.id == int(assignment_id))
            .values(user_id=(int(user_id) if user_id is not None else None))
        )


def get_assignments_for_service(service_id: int):
    """
    Returns list of tuples: (role, user_id, volunteer_name)
    """
    stmt = (
        select(
            assignments.c.role,
            assignments.c.user_id,
            users.c.full_name,
            users.c.username,
            users.c.email,
        )
        .select_from(assignments.outerjoin(users, users.c.id == assignments.c.user_id))
        .where(assignments.c.service_id == int(service_id))
        .order_by(assignments.c.role.asc())
    )

    with engine().connect() as conn:
        rows = conn.execute(stmt).fetchall()

    out = []
    for r in rows:
        m = r._mapping
        name = (m["full_name"] or "").strip() or (m["username"] or "").strip() or (m["email"] or "").strip() or None
        out.append((m["role"], m["user_id"], name))
    return out


def clear_month_services(ministry_id: int, year: int, month: int) -> None:
    """
    Clears services + assignments for the given ministry+month.
    IMPORTANT: reminder_jobs references assignments, so delete reminder_jobs first.
    """
    prefix = f"{year:04d}-{month:02d}-"

    with engine().begin() as conn:
        service_ids = [
            r[0]
            for r in conn.execute(
                select(services.c.id)
                .where(services.c.ministry_id == int(ministry_id))
                .where(services.c.dt_iso.startswith(prefix))
            ).fetchall()
        ]
        if not service_ids:
            return

        assignment_ids = [
            r[0]
            for r in conn.execute(
                select(assignments.c.id).where(assignments.c.service_id.in_(service_ids))
            ).fetchall()
        ]

        if assignment_ids:
            conn.execute(delete(reminder_jobs).where(reminder_jobs.c.assignment_id.in_(assignment_ids)))
            conn.execute(delete(swap_requests).where(swap_requests.c.assignment_id.in_(assignment_ids)))

        conn.execute(delete(assignments).where(assignments.c.service_id.in_(service_ids)))
        conn.execute(delete(services).where(services.c.id.in_(service_ids)))