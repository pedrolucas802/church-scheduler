# src/db/schema.py
from sqlalchemy import (
    MetaData,
    Table,
    Column,
    BigInteger,
    Integer,
    String,
    Text,
    ForeignKey,
    UniqueConstraint,
)

metadata = MetaData()

# -------------------------
# Users (Keycloak identity mirror)
# -------------------------
users = Table(
    "users",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column("kc_sub", String, nullable=False, unique=True),  # Keycloak "sub"
    Column("username", String, nullable=True),
    Column("email", String, nullable=True),
    Column("full_name", String, nullable=True),
    Column("created_at", String, nullable=False),
    Column("updated_at", String, nullable=False),
)

# -------------------------
# Ministries
# -------------------------
ministries = Table(
    "ministries",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column("slug", String, nullable=False, unique=True),  # e.g. "worship", "media"
    Column("name", String, nullable=False),
    Column("created_at", String, nullable=False),
    Column("updated_at", String, nullable=False),
)

# -------------------------
# Memberships (user <-> ministry)
# role: "admin" or "volunteer"
# -------------------------
ministry_memberships = Table(
    "ministry_memberships",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column("ministry_id", BigInteger, ForeignKey("ministries.id"), nullable=False),
    Column("user_id", BigInteger, ForeignKey("users.id"), nullable=False),
    Column("role", String, nullable=False),  # "admin" | "volunteer"
    UniqueConstraint("ministry_id", "user_id", name="uq_membership_ministry_user"),
)

# -------------------------
# Volunteer preferences per ministry
# -------------------------
volunteer_prefs = Table(
    "volunteer_prefs",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column("ministry_id", BigInteger, ForeignKey("ministries.id"), nullable=False),
    Column("user_id", BigInteger, ForeignKey("users.id"), nullable=False),

    Column("active", Integer, nullable=False, default=1),
    Column("phone", String, nullable=True),

    Column("thu_ok", Integer, nullable=False, default=1),
    Column("sun_ok", Integer, nullable=False, default=1),
    Column("can_obs", Integer, nullable=False, default=1),
    Column("can_fixed", Integer, nullable=False, default=1),
    Column("can_mobile", Integer, nullable=False, default=1),

    UniqueConstraint("ministry_id", "user_id", name="uq_prefs_ministry_user"),
)

# -------------------------
# Services are now per-ministry
# -------------------------
services = Table(
    "services",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column("ministry_id", BigInteger, ForeignKey("ministries.id"), nullable=False),
    Column("dt_iso", String, nullable=False),
    UniqueConstraint("ministry_id", "dt_iso", name="uq_services_ministry_dt"),
)

# -------------------------
# Assignments reference users
# -------------------------
assignments = Table(
    "assignments",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column("service_id", BigInteger, ForeignKey("services.id"), nullable=False),
    Column("role", String, nullable=False),
    Column("user_id", BigInteger, ForeignKey("users.id"), nullable=True),
    UniqueConstraint("service_id", "role", name="uq_assignments_service_role"),
)

# -------------------------
# Swap requests
# -------------------------
swap_requests = Table(
    "swap_requests",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column("assignment_id", BigInteger, ForeignKey("assignments.id"), nullable=False),
    Column("requested_by_user_id", BigInteger, ForeignKey("users.id"), nullable=True),
    Column("replacement_user_id", BigInteger, ForeignKey("users.id"), nullable=True),
    Column("reason", Text, nullable=True),
    Column("status", String, nullable=False, default="PENDING"),
    Column("created_at", String, nullable=False),
    Column("resolved_at", String, nullable=True),
    Column("resolved_by", String, nullable=True),
)

# -------------------------
# Reminder jobs
# -------------------------
reminder_jobs = Table(
    "reminder_jobs",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column("assignment_id", BigInteger, ForeignKey("assignments.id"), nullable=False),
    Column("send_at_iso", String, nullable=False),
    Column("status", String, nullable=False, default="PENDING"),
    Column("attempts", Integer, nullable=False, default=0),
    Column("last_error", Text, nullable=True),
    Column("created_at", String, nullable=False),
    Column("sent_at", String, nullable=True),
)

__all__ = [
    "metadata",
    "users",
    "ministries",
    "ministry_memberships",
    "volunteer_prefs",
    "services",
    "assignments",
    "swap_requests",
    "reminder_jobs",
]