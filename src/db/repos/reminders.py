# src/db/repos/reminders.py
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert


def rebuild_reminders_for_month(ministry_id: int, year: int, month: int) -> None:
    """
    For all assignments in the ministry+month:
      - cancel pending reminder jobs in month
      - create new job at service_time - 24h if user exists
    """
    with engine().begin() as conn:
        pending = conn.execute(
            select(reminder_jobs.c.id, services.c.dt_iso)
            .select_from(
                reminder_jobs
                .join(assignments, assignments.c.id == reminder_jobs.c.assignment_id)
                .join(services, services.c.id == assignments.c.service_id)
            )
            .where(reminder_jobs.c.status == "PENDING")
            .where(services.c.ministry_id == int(ministry_id))
        ).fetchall()

        for rid, dt_iso in pending:
            dt = datetime.fromisoformat(dt_iso)
            if dt.year == year and dt.month == month:
                conn.execute(
                    update(reminder_jobs)
                    .where(reminder_jobs.c.id == rid)
                    .values(status="CANCELLED")
                )

        ass = conn.execute(
            select(assignments.c.id, services.c.dt_iso, assignments.c.user_id)
            .select_from(assignments.join(services, services.c.id == assignments.c.service_id))
            .where(services.c.ministry_id == int(ministry_id))
        ).fetchall()

        now_iso = datetime.utcnow().isoformat()
        for aid, dt_iso, uid in ass:
            dt = datetime.fromisoformat(dt_iso)
            if dt.year != year or dt.month != month:
                continue
            if uid is None:
                continue

            send_at = (dt - timedelta(hours=24)).isoformat()
            conn.execute(
                pg_insert(reminder_jobs).values(
                    assignment_id=int(aid),
                    send_at_iso=send_at,
                    status="PENDING",
                    attempts=0,
                    created_at=now_iso,
                )
            )


def list_reminders(ministry_id: int, status: Optional[str] = None):
    """
    Returns tuples in THIS EXACT ORDER (10 cols):
      (id, status, send_at_iso, attempts, last_error, service_dt, role, name, email, phone)

    phone is not in users; if you want phone, join volunteer_prefs.
    For now: phone is returned as None.
    """
    stmt = (
        select(
            reminder_jobs.c.id,
            reminder_jobs.c.status,
            reminder_jobs.c.send_at_iso,
            reminder_jobs.c.attempts,
            reminder_jobs.c.last_error,
            services.c.dt_iso.label("service_dt"),
            assignments.c.role,
            users.c.full_name,
            users.c.email,
            users.c.username,
        )
        .select_from(
            reminder_jobs
            .join(assignments, assignments.c.id == reminder_jobs.c.assignment_id)
            .join(services, services.c.id == assignments.c.service_id)
            .outerjoin(users, users.c.id == assignments.c.user_id)
        )
        .where(services.c.ministry_id == int(ministry_id))
    )

    if status:
        stmt = stmt.where(reminder_jobs.c.status == status)

    stmt = stmt.order_by(reminder_jobs.c.send_at_iso.asc())

    with engine().connect() as conn:
        rows = conn.execute(stmt).fetchall()

    def _name(full_name, username, email):
        return (full_name or "").strip() or (username or "").strip() or (email or "").strip() or None

    out = []
    for r in rows:
        m = r._mapping
        out.append(
            (
                int(m["id"]),
                m["status"],
                m["send_at_iso"],
                int(m["attempts"] or 0),
                m["last_error"],
                m["service_dt"],
                m["role"],
                _name(m["full_name"], m["username"], m["email"]),
                (m["email"] or None),
                None,  # phone placeholder (join volunteer_prefs if needed)
            )
        )
    return out


def mark_reminder_sent(reminder_id: int) -> None:
    with engine().begin() as conn:
        conn.execute(
            update(reminder_jobs)
            .where(reminder_jobs.c.id == int(reminder_id))
            .values(status="SENT", sent_at=datetime.utcnow().isoformat())
        )


def list_due_reminders_for_email(ministry_id: int, now: Optional[datetime] = None):
    """
    Returns:
      (reminder_id, send_at_iso, service_dt, role, user_id, name, email)
    """
    now = now or datetime.utcnow()
    now_iso = now.isoformat()

    stmt = (
        select(
            reminder_jobs.c.id,
            reminder_jobs.c.send_at_iso,
            services.c.dt_iso.label("service_dt"),
            assignments.c.role,
            users.c.id.label("user_id"),
            users.c.full_name,
            users.c.username,
            users.c.email,
        )
        .select_from(
            reminder_jobs
            .join(assignments, assignments.c.id == reminder_jobs.c.assignment_id)
            .join(services, services.c.id == assignments.c.service_id)
            .join(users, users.c.id == assignments.c.user_id)
        )
        .where(services.c.ministry_id == int(ministry_id))
        .where(reminder_jobs.c.status == "PENDING")
        .where(reminder_jobs.c.send_at_iso <= now_iso)
        .order_by(services.c.dt_iso.asc())
    )

    with engine().connect() as conn:
        rows = conn.execute(stmt).fetchall()

    def _name(full_name, username, email):
        return (full_name or "").strip() or (username or "").strip() or (email or "").strip() or None

    out = []
    for r in rows:
        m = r._mapping
        out.append(
            (
                int(m["id"]),
                m["send_at_iso"],
                m["service_dt"],
                m["role"],
                int(m["user_id"]),
                _name(m["full_name"], m["username"], m["email"]),
                (m["email"] or None),
            )
        )
    return out


def mark_reminders_sent(reminder_ids: list[int]) -> None:
    if not reminder_ids:
        return
    with engine().begin() as conn:
        conn.execute(
            update(reminder_jobs)
            .where(reminder_jobs.c.id.in_(reminder_ids))
            .values(status="SENT", sent_at=datetime.utcnow().isoformat())
        )