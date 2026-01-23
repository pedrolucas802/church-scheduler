import os
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import (
    create_engine, MetaData, Table, Column,
    Integer, String, Text, ForeignKey, UniqueConstraint,
    select, insert, update, delete
)
from sqlalchemy.engine import Engine

# IMPORTANT: pg_insert only works on Postgres.
# For SQLite dev, we fallback to generic insert.
try:
    from sqlalchemy.dialects.postgresql import insert as pg_insert  # type: ignore
except Exception:  # pragma: no cover
    pg_insert = None  # type: ignore


# DATABASE_URL example:
# postgresql+psycopg2://church_admin:church_password@localhost:5432/church_scheduler
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/app.db")

_engine: Optional[Engine] = None
_metadata = MetaData()


# ---------------- Schema ----------------

# --- Admin users (single admin) ---
admin_users = Table(
    "admin_users", _metadata,
    Column("id", Integer, primary_key=True),
    Column("username", String, nullable=False, unique=True),
    Column("password_hash", Text, nullable=False),
    Column("active", Integer, nullable=False, default=1),
    Column("failed_attempts", Integer, nullable=False, default=0),
    Column("locked_until", String, nullable=True),  # ISO string ok for MVP
    Column("created_at", String, nullable=False),
    Column("updated_at", String, nullable=False),
)

volunteers = Table(
    "volunteers", _metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String, nullable=False, unique=True),
    Column("phone", String, nullable=True),
    Column("active", Integer, nullable=False, default=1),
    Column("thu_ok", Integer, nullable=False, default=1),
    Column("sun_ok", Integer, nullable=False, default=1),
    Column("can_obs", Integer, nullable=False, default=1),
    Column("can_fixed", Integer, nullable=False, default=1),
    Column("can_mobile", Integer, nullable=False, default=1),
)

services = Table(
    "services", _metadata,
    Column("id", Integer, primary_key=True),
    Column("dt_iso", String, nullable=False, unique=True),
)

assignments = Table(
    "assignments", _metadata,
    Column("id", Integer, primary_key=True),
    Column("service_id", Integer, ForeignKey("services.id"), nullable=False),
    Column("role", String, nullable=False),
    Column("volunteer_id", Integer, ForeignKey("volunteers.id"), nullable=True),
    UniqueConstraint("service_id", "role", name="uq_assignments_service_role"),
)

swap_requests = Table(
    "swap_requests", _metadata,
    Column("id", Integer, primary_key=True),
    Column("assignment_id", Integer, ForeignKey("assignments.id"), nullable=False),

    # who is requesting the change (cannot attend)
    Column("requested_by_volunteer_id", Integer, ForeignKey("volunteers.id"), nullable=True),

    # who will sub for them (replacement)
    Column("replacement_volunteer_id", Integer, ForeignKey("volunteers.id"), nullable=True),

    Column("reason", Text, nullable=True),
    Column("status", String, nullable=False, default="PENDING"),
    Column("created_at", String, nullable=False),
    Column("resolved_at", String, nullable=True),
    Column("resolved_by_admin", String, nullable=True),
)

reminder_jobs = Table(
    "reminder_jobs", _metadata,
    Column("id", Integer, primary_key=True),
    Column("assignment_id", Integer, ForeignKey("assignments.id"), nullable=False),
    Column("send_at_iso", String, nullable=False),
    Column("status", String, nullable=False, default="PENDING"),
    Column("attempts", Integer, nullable=False, default=0),
    Column("last_error", Text, nullable=True),
    Column("created_at", String, nullable=False),
    Column("sent_at", String, nullable=True),
)


# ---------------- Engine helpers ----------------
def engine() -> Engine:
    global _engine
    if _engine is None:
        # pool_pre_ping helps long-running VPS connections
        _engine = create_engine(DATABASE_URL, future=True, pool_pre_ping=True)
    return _engine


def init_db():
    # Create tables if not exist (good for MVP; later replace with Alembic migrations)
    _metadata.create_all(engine())


# ---------------- Internal helpers (upsert abstraction) ----------------
def _is_postgres() -> bool:
    return str(DATABASE_URL).startswith("postgresql")


def _upsert(table: Table, insert_values: dict, conflict_cols: list[str], update_values: dict):
    """
    Upsert compatible with Postgres (ON CONFLICT) and a best-effort fallback for SQLite.
    """
    if _is_postgres() and pg_insert is not None:
        stmt = pg_insert(table).values(**insert_values).on_conflict_do_update(
            index_elements=[getattr(table.c, c) for c in conflict_cols],
            set_=update_values,
        )
        return stmt

    # SQLite fallback: try update first; if 0 rows updated, insert.
    # NOTE: SQLite "upsert" exists too (since 3.24) but SQLAlchemy dialect usage differs by version.
    # This fallback keeps it simple.
    where_clause = None
    for c in conflict_cols:
        col = getattr(table.c, c)
        val = insert_values.get(c)
        if where_clause is None:
            where_clause = (col == val)
        else:
            where_clause = where_clause & (col == val)

    # we'll return a tuple of ("sqlite_fallback", where_clause, ...)
    return ("sqlite_fallback", table, where_clause, insert_values, update_values)


def _exec_upsert(conn, upsert_stmt):
    if isinstance(upsert_stmt, tuple) and upsert_stmt and upsert_stmt[0] == "sqlite_fallback":
        _, table, where_clause, insert_values, update_values = upsert_stmt
        res = conn.execute(update(table).where(where_clause).values(**update_values))
        if res.rowcount == 0:
            conn.execute(insert(table).values(**insert_values))
        return None
    return conn.execute(upsert_stmt)


# ---------------- Admin ----------------
def upsert_admin_user(username: str, password_hash: str, active: bool = True):
    now = datetime.utcnow().isoformat()

    insert_values = dict(
        username=username,
        password_hash=password_hash,
        active=1 if active else 0,
        failed_attempts=0,
        locked_until=None,
        created_at=now,
        updated_at=now,
    )
    update_values = dict(
        password_hash=password_hash,
        active=1 if active else 0,
        failed_attempts=0,
        locked_until=None,
        updated_at=now,
    )

    stmt = _upsert(
        admin_users,
        insert_values=insert_values,
        conflict_cols=["username"],
        update_values=update_values,
    )

    with engine().begin() as conn:
        _exec_upsert(conn, stmt)
        # return id (portable)
        return conn.execute(select(admin_users.c.id).where(admin_users.c.username == username)).scalar_one()


def get_admin_user(username: str):
    stmt = (
        select(
            admin_users.c.id,
            admin_users.c.username,
            admin_users.c.password_hash,
            admin_users.c.active,
            admin_users.c.failed_attempts,
            admin_users.c.locked_until,
        )
        .where(admin_users.c.username == username)
        .limit(1)
    )
    with engine().connect() as conn:
        return conn.execute(stmt).fetchone()


def admin_record_failed_login(username: str, failed_attempts: int, locked_until_iso: str | None):
    with engine().begin() as conn:
        conn.execute(
            update(admin_users)
            .where(admin_users.c.username == username)
            .values(
                failed_attempts=int(failed_attempts),
                locked_until=locked_until_iso,
                updated_at=datetime.utcnow().isoformat(),
            )
        )


def admin_reset_failures(username: str):
    with engine().begin() as conn:
        conn.execute(
            update(admin_users)
            .where(admin_users.c.username == username)
            .values(
                failed_attempts=0,
                locked_until=None,
                updated_at=datetime.utcnow().isoformat(),
            )
        )


# ---------------- Volunteers ----------------
def list_volunteers(active_only: bool = False):
    stmt = select(
        volunteers.c.id, volunteers.c.name, volunteers.c.phone,
        volunteers.c.active, volunteers.c.thu_ok, volunteers.c.sun_ok,
        volunteers.c.can_obs, volunteers.c.can_fixed, volunteers.c.can_mobile
    )
    if active_only:
        stmt = stmt.where(volunteers.c.active == 1)
    stmt = stmt.order_by(volunteers.c.name.asc())

    with engine().connect() as conn:
        return conn.execute(stmt).fetchall()


def upsert_volunteer(data: dict):
    # enforce ints for bool-like columns
    cleaned = dict(data)
    for k in ["active", "thu_ok", "sun_ok", "can_obs", "can_fixed", "can_mobile"]:
        if k in cleaned and cleaned[k] is not None:
            cleaned[k] = 1 if bool(cleaned[k]) else 0

    stmt = _upsert(
        volunteers,
        insert_values=cleaned,
        conflict_cols=["name"],
        update_values={k: v for k, v in cleaned.items() if k != "name"},
    )

    with engine().begin() as conn:
        _exec_upsert(conn, stmt)


def set_volunteer_active(volunteer_id: int, active: bool):
    with engine().begin() as conn:
        conn.execute(
            update(volunteers)
            .where(volunteers.c.id == volunteer_id)
            .values(active=1 if active else 0)
        )


# ---------------- Services & assignments ----------------
def ensure_service(dt_iso: str) -> int:
    # Upsert service by dt_iso (insert if missing)
    if _is_postgres() and pg_insert is not None:
        stmt = pg_insert(services).values(dt_iso=dt_iso).on_conflict_do_nothing(
            index_elements=[services.c.dt_iso]
        )
        with engine().begin() as conn:
            conn.execute(stmt)
            sid = conn.execute(select(services.c.id).where(services.c.dt_iso == dt_iso)).scalar_one()
            return int(sid)

    # SQLite fallback
    with engine().begin() as conn:
        exists = conn.execute(select(services.c.id).where(services.c.dt_iso == dt_iso)).scalar()
        if exists:
            return int(exists)
        conn.execute(insert(services).values(dt_iso=dt_iso))
        sid = conn.execute(select(services.c.id).where(services.c.dt_iso == dt_iso)).scalar_one()
        return int(sid)


def clear_month_services(year: int, month: int):
    """
    Clears services + assignments for the given month.
    IMPORTANT: reminder_jobs references assignments, so delete reminder_jobs first.
    """
    prefix = f"{year:04d}-{month:02d}-"

    with engine().begin() as conn:
        # 1) Find all service ids for that month
        service_ids = [
            r[0]
            for r in conn.execute(
                select(services.c.id).where(services.c.dt_iso.startswith(prefix))
            ).fetchall()
        ]
        if not service_ids:
            return

        # 2) Find all assignment ids for those services
        assignment_ids = [
            r[0]
            for r in conn.execute(
                select(assignments.c.id).where(assignments.c.service_id.in_(service_ids))
            ).fetchall()
        ]

        # 3) Delete reminder_jobs first (FK constraint)
        if assignment_ids:
            conn.execute(
                delete(reminder_jobs).where(reminder_jobs.c.assignment_id.in_(assignment_ids))
            )

        # 4) Delete swap_requests that point to those assignments (avoid FK issues later)
        if assignment_ids:
            conn.execute(
                delete(swap_requests).where(swap_requests.c.assignment_id.in_(assignment_ids))
            )

        # 5) Delete assignments
        conn.execute(delete(assignments).where(assignments.c.service_id.in_(service_ids)))

        # 6) Delete services
        conn.execute(delete(services).where(services.c.id.in_(service_ids)))


def upsert_assignment(service_id: int, role: str, volunteer_id: int | None):
    insert_values = dict(service_id=service_id, role=role, volunteer_id=volunteer_id)
    update_values = dict(volunteer_id=volunteer_id)

    stmt = _upsert(
        assignments,
        insert_values=insert_values,
        conflict_cols=["service_id", "role"],
        update_values=update_values,
    )

    with engine().begin() as conn:
        _exec_upsert(conn, stmt)


def list_schedule_between(start_iso: str, end_iso: str):
    """
    Returns list of tuples:
      (service_id, dt_iso, assignment_id, role, volunteer_name)
    """
    stmt = (
        select(
            services.c.id,
            services.c.dt_iso,
            assignments.c.id,
            assignments.c.role,
            volunteers.c.name
        )
        .select_from(
            services
            .outerjoin(assignments, assignments.c.service_id == services.c.id)
            .outerjoin(volunteers, volunteers.c.id == assignments.c.volunteer_id)
        )
        .where((services.c.dt_iso >= start_iso) & (services.c.dt_iso < end_iso))
        .order_by(services.c.dt_iso.asc(), assignments.c.role.asc())
    )
    with engine().connect() as conn:
        return conn.execute(stmt).fetchall()


def list_services_in_month(year: int, month: int):
    with engine().connect() as conn:
        rows = conn.execute(select(services.c.id, services.c.dt_iso).order_by(services.c.dt_iso)).fetchall()

    out = []
    for sid, dt_iso in rows:
        dt = datetime.fromisoformat(dt_iso)
        if dt.year == year and dt.month == month:
            out.append((int(sid), dt_iso))
    return out


def get_assignment_details(assignment_id: int):
    """
    Returns one row:
      (assignment_id, service_id, dt_iso, role, volunteer_id, volunteer_name)
    """
    stmt = (
        select(
            assignments.c.id,
            assignments.c.service_id,
            services.c.dt_iso,
            assignments.c.role,
            assignments.c.volunteer_id,
            volunteers.c.name
        )
        .select_from(
            assignments
            .join(services, services.c.id == assignments.c.service_id)
            .outerjoin(volunteers, volunteers.c.id == assignments.c.volunteer_id)
        )
        .where(assignments.c.id == assignment_id)
        .limit(1)
    )
    with engine().connect() as conn:
        return conn.execute(stmt).fetchone()


def set_assignment_volunteer_by_id(assignment_id: int, volunteer_id: int | None):
    """
    Updates an assignment by assignment_id.
    """
    with engine().begin() as conn:
        conn.execute(
            update(assignments)
            .where(assignments.c.id == assignment_id)
            .values(volunteer_id=volunteer_id)
        )


# ---------------- Swap requests ----------------
def create_swap_request(
    assignment_id: int,
    requested_by_volunteer_id: int | None,
    replacement_volunteer_id: int | None,
    reason: str
):
    with engine().begin() as conn:
        conn.execute(
            insert(swap_requests).values(
                assignment_id=assignment_id,
                requested_by_volunteer_id=requested_by_volunteer_id,
                replacement_volunteer_id=replacement_volunteer_id,
                reason=reason or None,
                status="PENDING",
                created_at=datetime.utcnow().isoformat()
            )
        )


def list_swap_requests(status: str | None = None):
    """
    Returns rows:
      (req_id, status, reason, created_at,
       assignment_id, role, dt_iso,
       assigned_to, requested_by,
       replacement_id, replacement_name)
    """
    v_assigned = volunteers.alias("v_assigned")
    v_req = volunteers.alias("v_req")
    v_rep = volunteers.alias("v_rep")

    stmt = (
        select(
            swap_requests.c.id,
            swap_requests.c.status,
            swap_requests.c.reason,
            swap_requests.c.created_at,
            assignments.c.id.label("assignment_id"),
            assignments.c.role,
            services.c.dt_iso,
            v_assigned.c.name.label("assigned_to"),
            v_req.c.name.label("requested_by"),
            swap_requests.c.replacement_volunteer_id.label("replacement_id"),
            v_rep.c.name.label("replacement_name"),
        )
        .select_from(
            swap_requests
            .join(assignments, assignments.c.id == swap_requests.c.assignment_id)
            .join(services, services.c.id == assignments.c.service_id)
            .outerjoin(v_assigned, v_assigned.c.id == assignments.c.volunteer_id)
            .outerjoin(v_req, v_req.c.id == swap_requests.c.requested_by_volunteer_id)
            .outerjoin(v_rep, v_rep.c.id == swap_requests.c.replacement_volunteer_id)
        )
        .order_by(swap_requests.c.created_at.desc())
    )

    if status:
        stmt = stmt.where(swap_requests.c.status == status)

    with engine().connect() as conn:
        return conn.execute(stmt).fetchall()


def resolve_swap_request(req_id: int, status: str, resolved_by_admin: str):
    with engine().begin() as conn:
        conn.execute(
            update(swap_requests)
            .where(swap_requests.c.id == req_id)
            .values(
                status=status,
                resolved_at=datetime.utcnow().isoformat(),
                resolved_by_admin=resolved_by_admin
            )
        )


# ---------------- Reminders ----------------
def rebuild_reminders_for_month(year: int, month: int):
    """
    For all assignments in the month:
      - cancel pending reminder jobs in month
      - create new job at service_time - 24h if volunteer exists
    """
    with engine().begin() as conn:
        # Cancel existing pending reminders for services in that month
        pending = conn.execute(
            select(reminder_jobs.c.id, services.c.dt_iso)
            .select_from(
                reminder_jobs
                .join(assignments, assignments.c.id == reminder_jobs.c.assignment_id)
                .join(services, services.c.id == assignments.c.service_id)
            )
            .where(reminder_jobs.c.status == "PENDING")
        ).fetchall()

        for rid, dt_iso in pending:
            dt = datetime.fromisoformat(dt_iso)
            if dt.year == year and dt.month == month:
                conn.execute(update(reminder_jobs).where(reminder_jobs.c.id == rid).values(status="CANCELLED"))

        # Create fresh ones
        ass = conn.execute(
            select(assignments.c.id, services.c.dt_iso, assignments.c.volunteer_id)
            .select_from(assignments.join(services, services.c.id == assignments.c.service_id))
        ).fetchall()

        now = datetime.utcnow().isoformat()
        for aid, dt_iso, vid in ass:
            dt = datetime.fromisoformat(dt_iso)
            if dt.year != year or dt.month != month:
                continue
            if vid is None:
                continue

            send_at = (dt - timedelta(hours=24)).isoformat()
            conn.execute(
                insert(reminder_jobs).values(
                    assignment_id=int(aid),
                    send_at_iso=send_at,
                    status="PENDING",
                    attempts=0,
                    created_at=now
                )
            )


def list_reminders(status: str | None = None):
    stmt = (
        select(
            reminder_jobs.c.id,
            reminder_jobs.c.status,
            reminder_jobs.c.send_at_iso,
            reminder_jobs.c.attempts,
            reminder_jobs.c.last_error,
            services.c.dt_iso.label("service_dt"),
            assignments.c.role,
            volunteers.c.name,
            volunteers.c.phone
        )
        .select_from(
            reminder_jobs
            .join(assignments, assignments.c.id == reminder_jobs.c.assignment_id)
            .join(services, services.c.id == assignments.c.service_id)
            .outerjoin(volunteers, volunteers.c.id == assignments.c.volunteer_id)
        )
    )

    if status:
        stmt = stmt.where(reminder_jobs.c.status == status)

    stmt = stmt.order_by(reminder_jobs.c.send_at_iso.asc())

    with engine().connect() as conn:
        return conn.execute(stmt).fetchall()


def mark_reminder_sent(reminder_id: int):
    with engine().begin() as conn:
        conn.execute(
            update(reminder_jobs)
            .where(reminder_jobs.c.id == reminder_id)
            .values(status="SENT", sent_at=datetime.utcnow().isoformat())
        )


def get_assignments_for_service(service_id: int):
    """
    Returns list of tuples: (role, volunteer_id, volunteer_name)
    """
    stmt = (
        select(
            assignments.c.role,
            assignments.c.volunteer_id,
            volunteers.c.name
        )
        .select_from(
            assignments.outerjoin(volunteers, volunteers.c.id == assignments.c.volunteer_id)
        )
        .where(assignments.c.service_id == service_id)
        .order_by(assignments.c.role.asc())
    )

    with engine().connect() as conn:
        return conn.execute(stmt).fetchall()