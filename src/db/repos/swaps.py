# src/db/repos/swaps.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert


def create_swap_request(
    assignment_id: int,
    requested_by_user_id: Optional[int],
    replacement_user_id: Optional[int],
    reason: str,
) -> None:
    with engine().begin() as conn:
        conn.execute(
            pg_insert(swap_requests).values(
                assignment_id=int(assignment_id),
                requested_by_user_id=(int(requested_by_user_id) if requested_by_user_id is not None else None),
                replacement_user_id=(int(replacement_user_id) if replacement_user_id is not None else None),
                reason=(reason or None),
                status="PENDING",
                created_at=datetime.utcnow().isoformat(),
            )
        )


def list_swap_requests(status: Optional[str] = None):
    """
    Returns rows:
      (req_id, status, reason, created_at,
       assignment_id, role, dt_iso,
       assigned_to, requested_by,
       replacement_id, replacement_name)

    Uses users table for names.
    """
    u_assigned = users.alias("u_assigned")
    u_req = users.alias("u_req")
    u_rep = users.alias("u_rep")

    stmt = (
        select(
            swap_requests.c.id,
            swap_requests.c.status,
            swap_requests.c.reason,
            swap_requests.c.created_at,
            assignments.c.id.label("assignment_id"),
            assignments.c.role,
            services.c.dt_iso,
            u_assigned.c.full_name.label("assigned_to"),
            u_req.c.full_name.label("requested_by"),
            swap_requests.c.replacement_user_id.label("replacement_id"),
            u_rep.c.full_name.label("replacement_name"),
            # fallbacks for display
            u_assigned.c.username.label("assigned_username"),
            u_assigned.c.email.label("assigned_email"),
            u_req.c.username.label("req_username"),
            u_req.c.email.label("req_email"),
            u_rep.c.username.label("rep_username"),
            u_rep.c.email.label("rep_email"),
        )
        .select_from(
            swap_requests
            .join(assignments, assignments.c.id == swap_requests.c.assignment_id)
            .join(services, services.c.id == assignments.c.service_id)
            .outerjoin(u_assigned, u_assigned.c.id == assignments.c.user_id)
            .outerjoin(u_req, u_req.c.id == swap_requests.c.requested_by_user_id)
            .outerjoin(u_rep, u_rep.c.id == swap_requests.c.replacement_user_id)
        )
        .order_by(swap_requests.c.created_at.desc())
    )

    if status:
        stmt = stmt.where(swap_requests.c.status == status)

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
                m["reason"],
                m["created_at"],
                int(m["assignment_id"]),
                m["role"],
                m["dt_iso"],
                _name(m["assigned_to"], m["assigned_username"], m["assigned_email"]),
                _name(m["requested_by"], m["req_username"], m["req_email"]),
                m["replacement_id"],
                _name(m["replacement_name"], m["rep_username"], m["rep_email"]),
            )
        )
    return out


def resolve_swap_request(req_id: int, status: str, resolved_by: str) -> None:
    with engine().begin() as conn:
        conn.execute(
            update(swap_requests)
            .where(swap_requests.c.id == int(req_id))
            .values(
                status=status,
                resolved_at=datetime.utcnow().isoformat(),
                resolved_by=resolved_by,
            )
        )