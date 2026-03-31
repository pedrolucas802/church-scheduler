import os
from typing import Optional
from datetime import datetime, timedelta

from sqlalchemy import (
    create_engine,
    MetaData,
    Table,
    Column,
    Integer,
    String,
    Text,
    ForeignKey,
    UniqueConstraint,
    select,
    update,
    delete,
)
from sqlalchemy.engine import Engine
from sqlalchemy.dialects.postgresql import insert as pg_insert


# DATABASE_URL example:
# postgresql+psycopg2://church_admin:church_password@localhost:5432/church_scheduler
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL or not str(DATABASE_URL).startswith("postgresql"):
    raise RuntimeError(
        "DATABASE_URL must be set and must be a PostgreSQL URL, e.g. "
        "'postgresql+psycopg2://user:pass@host:5432/dbname'"
    )

_engine: Optional[Engine] = None
_metadata = MetaData()

# ---------------- Schema ----------------

admin_users = Table(
    "admin_users",
    _metadata,
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
    "volunteers",
    _metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String, nullable=False, unique=True),
    Column("email", String, nullable=True),
    Column("phone", String, nullable=True),
    Column("active", Integer, nullable=False, default=1),
    Column("thu_ok", Integer, nullable=False, default=1),
    Column("sun_ok", Integer, nullable=False, default=1),
    Column("can_obs", Integer, nullable=False, default=1),
    Column("can_fixed", Integer, nullable=False, default=1),
    Column("can_mobile", Integer, nullable=False, default=1),
)

services = Table(
    "services",
    _metadata,
    Column("id", Integer, primary_key=True),
    Column("dt_iso", String, nullable=False, unique=True),
)

assignments = Table(
    "assignments",
    _metadata,
    Column("id", Integer, primary_key=True),
    Column("service_id", Integer, ForeignKey("services.id"), nullable=False),
    Column("role", String, nullable=False),
    Column("volunteer_id", Integer, ForeignKey("volunteers.id"), nullable=True),
    UniqueConstraint("service_id", "role", name="uq_assignments_service_role"),
)

swap_requests = Table(
    "swap_requests",
    _metadata,
    Column("id", Integer, primary_key=True),
    Column("assignment_id", Integer, ForeignKey("assignments.id"), nullable=False),
    Column("requested_by_volunteer_id", Integer, ForeignKey("volunteers.id"), nullable=True),
    Column("replacement_volunteer_id", Integer, ForeignKey("volunteers.id"), nullable=True),
    Column("reason", Text, nullable=True),
    Column("status", String, nullable=False, default="PENDING"),
    Column("created_at", String, nullable=False),
    Column("resolved_at", String, nullable=True),
    Column("resolved_by_admin", String, nullable=True),
)

reminder_jobs = Table(
    "reminder_jobs",
    _metadata,
    Column("id", Integer, primary_key=True),
    Column("assignment_id", Integer, ForeignKey("assignments.id"), nullable=False),
    Column("send_at_iso", String, nullable=False),
    Column("status", String, nullable=False, default="PENDING"),
    Column("attempts", Integer, nullable=False, default=0),
    Column("last_error", Text, nullable=True),
    Column("created_at", String, nullable=False),
    Column("sent_at", String, nullable=True),
)

app_settings = Table(
    "app_settings",
    _metadata,
    Column("key", String, primary_key=True),
    Column("value", Text, nullable=True),
    Column("updated_at", String, nullable=False),
)


# ---------------- Engine helpers ----------------
def engine() -> Engine:
    global _engine
    if _engine is None:
        # pool_pre_ping helps long-running VPS connections
        _engine = create_engine(DATABASE_URL, future=True, pool_pre_ping=True)
    return _engine


def init_db():
    """
    Postgres-only MVP: create tables if missing.
    If you change schema, use migrations (Alembic) or recreate DB.
    """
    _metadata.create_all(engine())


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

    stmt = (
        pg_insert(admin_users)
        .values(**insert_values)
        .on_conflict_do_update(index_elements=[admin_users.c.username], set_=update_values)
    )

    with engine().begin() as conn:
        conn.execute(stmt)
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
    """
    Returns tuples in THIS EXACT ORDER:
      (id, name, email, phone, active, thu_ok, sun_ok, can_obs, can_fixed, can_mobile)
    """
    stmt = select(
        volunteers.c.id,
        volunteers.c.name,
        volunteers.c.email,
        volunteers.c.phone,
        volunteers.c.active,
        volunteers.c.thu_ok,
        volunteers.c.sun_ok,
        volunteers.c.can_obs,
        volunteers.c.can_fixed,
        volunteers.c.can_mobile,
    )
    if active_only:
        stmt = stmt.where(volunteers.c.active == 1)
    stmt = stmt.order_by(volunteers.c.name.asc())

    with engine().connect() as conn:
        return conn.execute(stmt).fetchall()


def upsert_volunteer(data: dict):
    cleaned = dict(data)

    for k in ["active", "thu_ok", "sun_ok", "can_obs", "can_fixed", "can_mobile"]:
        if k in cleaned and cleaned[k] is not None:
            cleaned[k] = 1 if bool(cleaned[k]) else 0

    if "email" in cleaned and cleaned["email"]:
        cleaned["email"] = cleaned["email"].strip().lower()

    insert_values = cleaned
    update_values = {k: v for k, v in cleaned.items() if k != "name"}

    stmt = (
        pg_insert(volunteers)
        .values(**insert_values)
        .on_conflict_do_update(index_elements=[volunteers.c.name], set_=update_values)
    )

    with engine().begin() as conn:
        conn.execute(stmt)


def set_volunteer_active(volunteer_id: int, active: bool):
    with engine().begin() as conn:
        conn.execute(
            update(volunteers)
            .where(volunteers.c.id == volunteer_id)
            .values(active=1 if active else 0)
        )


# ---------------- Services & assignments ----------------
def ensure_service(dt_iso: str) -> int:
    stmt = (
        pg_insert(services)
        .values(dt_iso=dt_iso)
        .on_conflict_do_nothing(index_elements=[services.c.dt_iso])
    )
    with engine().begin() as conn:
        conn.execute(stmt)
        sid = conn.execute(select(services.c.id).where(services.c.dt_iso == dt_iso)).scalar_one()
        return int(sid)


def clear_month_services(year: int, month: int):
    """
    Clears services + assignments for the given month.
    IMPORTANT: reminder_jobs references assignments, so delete reminder_jobs first.
    """
    prefix = f"{year:04d}-{month:02d}-"

    with engine().begin() as conn:
        service_ids = [
            r[0]
            for r in conn.execute(
                select(services.c.id).where(services.c.dt_iso.startswith(prefix))
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


def upsert_assignment(service_id: int, role: str, volunteer_id: int | None):
    stmt = (
        pg_insert(assignments)
        .values(service_id=service_id, role=role, volunteer_id=volunteer_id)
        .on_conflict_do_update(
            index_elements=[assignments.c.service_id, assignments.c.role],
            set_={"volunteer_id": volunteer_id},
        )
    )
    with engine().begin() as conn:
        conn.execute(stmt)


def list_schedule_between(start_iso: str, end_iso: str):
    """
    Returns:
      (service_id, dt_iso, assignment_id, role, volunteer_name)
    """
    stmt = (
        select(
            services.c.id,
            services.c.dt_iso,
            assignments.c.id,
            assignments.c.role,
            volunteers.c.name,
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
    stmt = select(services.c.id, services.c.dt_iso).order_by(services.c.dt_iso.asc())

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
      (assignment_id, service_id, dt_iso, role, volunteer_id, volunteer_name)
    """
    stmt = (
        select(
            assignments.c.id,
            assignments.c.service_id,
            services.c.dt_iso,
            assignments.c.role,
            assignments.c.volunteer_id,
            volunteers.c.name,
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
    with engine().begin() as conn:
        conn.execute(
            update(assignments)
            .where(assignments.c.id == assignment_id)
            .values(volunteer_id=volunteer_id)
        )


def get_assignments_for_service(service_id: int):
    """
    Returns list of tuples: (role, volunteer_id, volunteer_name)
    """
    stmt = (
        select(
            assignments.c.role,
            assignments.c.volunteer_id,
            volunteers.c.name,
        )
        .select_from(assignments.outerjoin(volunteers, volunteers.c.id == assignments.c.volunteer_id))
        .where(assignments.c.service_id == service_id)
        .order_by(assignments.c.role.asc())
    )

    with engine().connect() as conn:
        return conn.execute(stmt).fetchall()


# ---------------- Swap requests ----------------
def create_swap_request(
    assignment_id: int,
    requested_by_volunteer_id: int | None,
    replacement_volunteer_id: int | None,
    reason: str,
):
    with engine().begin() as conn:
        conn.execute(
            pg_insert(swap_requests).values(
                assignment_id=assignment_id,
                requested_by_volunteer_id=requested_by_volunteer_id,
                replacement_volunteer_id=replacement_volunteer_id,
                reason=reason or None,
                status="PENDING",
                created_at=datetime.utcnow().isoformat(),
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
                resolved_by_admin=resolved_by_admin,
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
                conn.execute(
                    update(reminder_jobs)
                    .where(reminder_jobs.c.id == rid)
                    .values(status="CANCELLED")
                )

        ass = conn.execute(
            select(assignments.c.id, services.c.dt_iso, assignments.c.volunteer_id)
            .select_from(assignments.join(services, services.c.id == assignments.c.service_id))
        ).fetchall()

        now_iso = datetime.utcnow().isoformat()
        for aid, dt_iso, vid in ass:
            dt = datetime.fromisoformat(dt_iso)
            if dt.year != year or dt.month != month:
                continue
            if vid is None:
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


def list_reminders(status: str | None = None):
    """
    Returns tuples in THIS EXACT ORDER (10 cols):
      (id, status, send_at_iso, attempts, last_error, service_dt, role, name, email, phone)
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
            volunteers.c.name,
            volunteers.c.email,  # IMPORTANT
            volunteers.c.phone,
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


def list_due_reminders_for_whatsapp(now: datetime | None = None):
    """
    Returns:
      (reminder_id, send_at_iso, service_dt, role, volunteer_id, name, phone)
    """
    now = now or datetime.now()
    now_iso = now.isoformat()

    stmt = (
        select(
            reminder_jobs.c.id,
            reminder_jobs.c.send_at_iso,
            services.c.dt_iso.label("service_dt"),
            assignments.c.role,
            volunteers.c.id.label("volunteer_id"),
            volunteers.c.name,
            volunteers.c.phone,
        )
        .select_from(
            reminder_jobs
            .join(assignments, assignments.c.id == reminder_jobs.c.assignment_id)
            .join(services, services.c.id == assignments.c.service_id)
            .join(volunteers, volunteers.c.id == assignments.c.volunteer_id)
        )
        .where(reminder_jobs.c.status == "PENDING")
        .where(reminder_jobs.c.send_at_iso <= now_iso)
        .order_by(services.c.dt_iso.asc())
    )

    with engine().connect() as conn:
        return conn.execute(stmt).fetchall()


def mark_reminders_sent(reminder_ids: list[int]):
    if not reminder_ids:
        return
    with engine().begin() as conn:
        conn.execute(
            update(reminder_jobs)
            .where(reminder_jobs.c.id.in_(reminder_ids))
            .values(status="SENT", sent_at=datetime.utcnow().isoformat())
        )


# ---------------- App settings ----------------
def get_app_setting(key: str, default: str | None = None) -> str | None:
    stmt = select(app_settings.c.value).where(app_settings.c.key == key).limit(1)
    with engine().connect() as conn:
        value = conn.execute(stmt).scalar_one_or_none()
    return default if value is None else str(value)


def get_bool_app_setting(key: str, default: bool = False) -> bool:
    raw = get_app_setting(key)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def set_app_setting(key: str, value: str | None):
    now = datetime.utcnow().isoformat()
    stmt = (
        pg_insert(app_settings)
        .values(key=key, value=value, updated_at=now)
        .on_conflict_do_update(
            index_elements=[app_settings.c.key],
            set_={"value": value, "updated_at": now},
        )
    )
    with engine().begin() as conn:
        conn.execute(stmt)


def list_sent_reminders(limit: int = 50):
    stmt = (
        select(
            reminder_jobs.c.id,
            reminder_jobs.c.sent_at,
            reminder_jobs.c.send_at_iso,
            services.c.dt_iso.label("service_dt"),
            assignments.c.role,
            volunteers.c.name,
            volunteers.c.phone,
            reminder_jobs.c.attempts,
        )
        .select_from(
            reminder_jobs
            .join(assignments, assignments.c.id == reminder_jobs.c.assignment_id)
            .join(services, services.c.id == assignments.c.service_id)
            .outerjoin(volunteers, volunteers.c.id == assignments.c.volunteer_id)
        )
        .where(reminder_jobs.c.status == "SENT")
        .where(reminder_jobs.c.sent_at.is_not(None))
        .order_by(reminder_jobs.c.sent_at.desc())
        .limit(int(limit))
    )

    with engine().connect() as conn:
        return conn.execute(stmt).fetchall()
