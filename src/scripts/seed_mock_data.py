from __future__ import annotations

import os
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text

# Ensure `import src...` works even when running this file directly
# File path: /app/src/scripts/seed_mock_data.py
# parents[0]=scripts, parents[1]=src, parents[2]=/app
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.db.init import init_db

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("Missing DATABASE_URL")

engine = create_engine(DATABASE_URL, future=True, pool_pre_ping=True)

NOW = datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _exec(sql: str, params: dict[str, Any] | None = None) -> None:
    with engine.begin() as conn:
        conn.execute(text(sql), params or {})


def _fetchall(sql: str, params: dict[str, Any] | None = None):
    with engine.begin() as conn:
        return conn.execute(text(sql), params or {}).fetchall()


# -----------------------------
# Upserts / inserts (new schema)
# -----------------------------

def upsert_ministry(slug: str, name: str) -> int:
    now = _iso(NOW)
    _exec(
        """
        INSERT INTO ministries (slug, name, created_at, updated_at)
        VALUES (:slug, :name, :created_at, :updated_at)
        ON CONFLICT (slug) DO UPDATE SET
          name = EXCLUDED.name,
          updated_at = EXCLUDED.updated_at
        """,
        {"slug": slug, "name": name, "created_at": now, "updated_at": now},
    )
    row = _fetchall("SELECT id FROM ministries WHERE slug = :slug", {"slug": slug})[0]
    return int(row[0])


def upsert_user(*, kc_sub: str, username: str | None, email: str | None, full_name: str | None) -> int:
    now = _iso(NOW)
    _exec(
        """
        INSERT INTO users (kc_sub, username, email, full_name, created_at, updated_at)
        VALUES (:kc_sub, :username, :email, :full_name, :created_at, :updated_at)
        ON CONFLICT (kc_sub) DO UPDATE SET
          username = COALESCE(EXCLUDED.username, users.username),
          email = COALESCE(EXCLUDED.email, users.email),
          full_name = COALESCE(EXCLUDED.full_name, users.full_name),
          updated_at = EXCLUDED.updated_at
        """,
        {
            "kc_sub": kc_sub,
            "username": username,
            "email": (email.lower().strip() if email else None),
            "full_name": full_name,
            "created_at": now,
            "updated_at": now,
        },
    )
    row = _fetchall("SELECT id FROM users WHERE kc_sub = :kc_sub", {"kc_sub": kc_sub})[0]
    return int(row[0])


def upsert_membership(ministry_id: int, user_id: int, role: str) -> None:
    # role: "admin" | "volunteer"
    _exec(
        """
        INSERT INTO ministry_memberships (ministry_id, user_id, role)
        VALUES (:ministry_id, :user_id, :role)
        ON CONFLICT (ministry_id, user_id) DO UPDATE SET role = EXCLUDED.role
        """,
        {"ministry_id": ministry_id, "user_id": user_id, "role": role},
    )


def upsert_volunteer_prefs(
    *,
    ministry_id: int,
    user_id: int,
    active: int,
    phone: str | None,
    thu_ok: int = 1,
    sun_ok: int = 1,
    can_obs: int = 1,
    can_fixed: int = 1,
    can_mobile: int = 1,
) -> None:
    _exec(
        """
        INSERT INTO volunteer_prefs (
          ministry_id, user_id, active, phone,
          thu_ok, sun_ok, can_obs, can_fixed, can_mobile
        )
        VALUES (
          :ministry_id, :user_id, :active, :phone,
          :thu_ok, :sun_ok, :can_obs, :can_fixed, :can_mobile
        )
        ON CONFLICT (ministry_id, user_id) DO UPDATE SET
          active = EXCLUDED.active,
          phone = EXCLUDED.phone,
          thu_ok = EXCLUDED.thu_ok,
          sun_ok = EXCLUDED.sun_ok,
          can_obs = EXCLUDED.can_obs,
          can_fixed = EXCLUDED.can_fixed,
          can_mobile = EXCLUDED.can_mobile
        """,
        {
            "ministry_id": ministry_id,
            "user_id": user_id,
            "active": int(active),
            "phone": phone,
            "thu_ok": int(thu_ok),
            "sun_ok": int(sun_ok),
            "can_obs": int(can_obs),
            "can_fixed": int(can_fixed),
            "can_mobile": int(can_mobile),
        },
    )


def ensure_service(ministry_id: int, dt_iso: str) -> int:
    _exec(
        """
        INSERT INTO services (ministry_id, dt_iso)
        VALUES (:ministry_id, :dt_iso)
        ON CONFLICT (ministry_id, dt_iso) DO NOTHING
        """,
        {"ministry_id": ministry_id, "dt_iso": dt_iso},
    )
    row = _fetchall(
        "SELECT id FROM services WHERE ministry_id = :mid AND dt_iso = :dt",
        {"mid": ministry_id, "dt": dt_iso},
    )[0]
    return int(row[0])


def upsert_assignment(service_id: int, role: str, user_id: int | None) -> int:
    _exec(
        """
        INSERT INTO assignments (service_id, role, user_id)
        VALUES (:service_id, :role, :user_id)
        ON CONFLICT (service_id, role) DO UPDATE SET user_id = EXCLUDED.user_id
        """,
        {"service_id": service_id, "role": role, "user_id": user_id},
    )
    row = _fetchall(
        "SELECT id FROM assignments WHERE service_id = :sid AND role = :role",
        {"sid": service_id, "role": role},
    )[0]
    return int(row[0])


def create_swap_request(assignment_id: int, requester_user_id: int, reason: str) -> None:
    _exec(
        """
        INSERT INTO swap_requests (
          assignment_id,
          requested_by_user_id,
          replacement_user_id,
          reason,
          status,
          created_at
        )
        VALUES (:aid, :rid, NULL, :reason, 'PENDING', :created_at)
        """,
        {"aid": assignment_id, "rid": requester_user_id, "reason": reason, "created_at": _iso(NOW)},
    )


def create_reminder(assignment_id: int, send_at_iso: str) -> None:
    _exec(
        """
        INSERT INTO reminder_jobs (assignment_id, send_at_iso, status, attempts, created_at)
        VALUES (:aid, :send_at, 'PENDING', 0, :created_at)
        """,
        {"aid": assignment_id, "send_at": send_at_iso, "created_at": _iso(NOW)},
    )


def seed() -> None:
    # Create tables from SQLAlchemy metadata
    init_db()

    # Ministries
    m_stream = upsert_ministry("streaming", "Ministério de Transmissão")
    m_music = upsert_ministry("music", "Ministério de Louvor")
    m_kids = upsert_ministry("kids", "Ministério Infantil")

    # Users
    # Note: we don't have real Keycloak `sub` values in a mock seed.
    # We create stable placeholders. When the real KC user logs in, your app should
    # upsert by real kc_sub and can later be linked/migrated if needed.
    u_admin = upsert_user(
        kc_sub="mock-sub-testadmin",
        username="testadmin",
        email="testadmin@local",
        full_name="Test Admin",
    )
    u_vol = upsert_user(
        kc_sub="mock-sub-testvolunteer",
        username="testvolunteer",
        email="testvolunteer@local",
        full_name="Test Volunteer",
    )
    u_ana = upsert_user(
        kc_sub="mock-sub-analima",
        username="analima",
        email="ana@local",
        full_name="Ana Lima",
    )
    u_pedro = upsert_user(
        kc_sub="mock-sub-pedrosouza",
        username="pedrosouza",
        email="pedro@local",
        full_name="Pedro Souza",
    )
    u_maria = upsert_user(
        kc_sub="mock-sub-mariasilva",
        username="mariasilva",
        email="maria@local",
        full_name="Maria Silva",
    )

    # Memberships: users can participate in N ministries
    upsert_membership(m_stream, u_admin, "admin")
    upsert_membership(m_stream, u_vol, "volunteer")
    upsert_membership(m_stream, u_ana, "volunteer")

    upsert_membership(m_music, u_admin, "admin")
    upsert_membership(m_music, u_pedro, "volunteer")

    upsert_membership(m_kids, u_admin, "admin")
    upsert_membership(m_kids, u_vol, "volunteer")

    # Volunteer prefs per ministry (this is where "pending" lives now)
    upsert_volunteer_prefs(ministry_id=m_stream, user_id=u_admin, active=1, phone="+5585999990001")
    upsert_volunteer_prefs(ministry_id=m_stream, user_id=u_vol, active=1, phone="+5585999990002")
    upsert_volunteer_prefs(ministry_id=m_stream, user_id=u_ana, active=1, phone="+5585999990003")
    upsert_volunteer_prefs(ministry_id=m_stream, user_id=u_pedro, active=1, phone="+5585999990004")
    upsert_volunteer_prefs(ministry_id=m_stream, user_id=u_maria, active=0, phone="+5585999990005")  # pending

    # Services + assignments (next 6 services)
    roles_stream = ["OBS", "Camera Fixa", "Camera Móvel", "Switcher"]
    for i in range(6):
        dt = NOW + timedelta(days=(i * 3))
        dt = dt.replace(hour=19 if i % 2 == 0 else 9, minute=0, second=0, microsecond=0)
        sid = ensure_service(m_stream, _iso(dt))

        picks = [u_admin, u_vol, u_ana, u_pedro]
        random.shuffle(picks)

        for r_idx, role in enumerate(roles_stream):
            uid = picks[r_idx % len(picks)]
            aid = upsert_assignment(sid, role, uid)

            # Reminders 24h before
            send_at = (dt - timedelta(hours=24))
            create_reminder(aid, _iso(send_at))

        # Add a swap request sometimes
        if i in (1, 4):
            arows = _fetchall(
                "SELECT id, user_id FROM assignments WHERE service_id = :sid ORDER BY id ASC",
                {"sid": sid},
            )
            if arows:
                aid, uid = arows[0]
                create_swap_request(int(aid), int(uid or u_vol), "Não vou conseguir nesse dia, pode trocar?")

    print("✅ Seed complete: ministries, users, memberships, prefs, services, assignments, swaps, reminders.")


if __name__ == "__main__":
    seed()