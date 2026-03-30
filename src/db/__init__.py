from __future__ import annotations

from typing import Optional

from src.db.init import init_db

# ---- Users exports ----
from src.db.repos.users import (
    upsert_user_from_kc,
    get_user_by_kc_sub,
    get_user_by_username,
    update_user_profile,
    list_users,
)

# ---- Ministries exports ----
from src.db.repos.ministries import (
    ensure_ministry,
    upsert_ministry,
    list_ministries,
    list_ministry_leaders,
    set_ministry_leader,
)

# ---- Memberships exports ----
from src.db.repos.memberships import (
    upsert_membership,
    list_user_ministries,
)


# =========================================================
# Volunteers facade
# =========================================================
def list_volunteers(*, active_only: bool = False, ministry_ids: Optional[list[int]] = None):
    from src.db.repos.volunteers import list_volunteers as _list

    if ministry_ids is None:
        mid = int(1)  # default
        mids = [mid]
    else:
        mids = ministry_ids

    return _list(active_only=bool(active_only), ministry_ids=mids)


def upsert_volunteer(data: dict, ministry_id: Optional[int] = None) -> None:
    from src.db.repos.volunteers import upsert_volunteer as _upsert

    mid = int(ministry_id or 1)
    return _upsert(data, ministry_id=mid)


def set_volunteer_active(user_id: int, active: bool, ministry_id: Optional[int] = None) -> None:
    from src.db.repos.volunteers import set_volunteer_active as _set

    mid = int(ministry_id or 1)
    return _set(int(user_id), bool(active), ministry_id=mid)


def upsert_volunteer_prefs(ministry_id: int, user_id: int, data: dict) -> None:
    from src.db.repos.volunteers import upsert_volunteer_prefs as _prefs

    return _prefs(int(ministry_id), int(user_id), data)


# =========================================================
# Schedule facade
# =========================================================
def list_schedule_between(start_iso: str, end_iso: str, ministry_ids: Optional[list[int]] = None):
    from src.db.repos.schedule import list_schedule_between as _list_sched

    return _list_sched(start_iso, end_iso, ministry_ids=ministry_ids)


def ensure_service(dt_iso: str, ministry_id: Optional[int] = None) -> int:
    from src.db.repos.schedule import ensure_service as _ensure_service

    mid = int(ministry_id or 1)
    return _ensure_service(mid, dt_iso)


def upsert_assignment(service_id: int, role: str, user_id: Optional[int]) -> None:
    from src.db.repos.schedule import upsert_assignment as _upsert_assignment

    return _upsert_assignment(int(service_id), str(role), int(user_id) if user_id is not None else None)


def list_services_in_month(year: int, month: int, ministry_id: Optional[int] = None):
    from src.db.repos.schedule import list_services_in_month as _list_services_in_month

    mid = int(ministry_id or 1)
    return _list_services_in_month(mid, int(year), int(month))


def get_assignment_details(assignment_id: int):
    from src.db.repos.schedule import get_assignment_details as _get_assignment_details

    return _get_assignment_details(int(assignment_id))


def set_assignment_volunteer_by_id(assignment_id: int, volunteer_id: Optional[int]) -> None:
    """
    Backward-compatible alias used by older pages.
    In the new model, assignments reference users.
    """
    from src.db.repos.schedule import set_assignment_user_by_id as _set_assignment_user_by_id

    return _set_assignment_user_by_id(
        int(assignment_id),
        int(volunteer_id) if volunteer_id is not None else None,
    )


def set_assignment_user_by_id(assignment_id: int, user_id: Optional[int]) -> None:
    from src.db.repos.schedule import set_assignment_user_by_id as _set_assignment_user_by_id

    return _set_assignment_user_by_id(
        int(assignment_id),
        int(user_id) if user_id is not None else None,
    )


def get_assignments_for_service(service_id: int):
    from src.db.repos.schedule import get_assignments_for_service as _get_assignments_for_service

    return _get_assignments_for_service(int(service_id))


def clear_month_services(year: int, month: int, ministry_id: Optional[int] = None) -> None:
    from src.db.repos.schedule import clear_month_services as _clear_month_services

    mid = int(ministry_id or 1)
    return _clear_month_services(mid, int(year), int(month))


# =========================================================
# Swaps facade
# =========================================================
def create_swap_request(
    assignment_id: int,
    requested_by_volunteer_id: Optional[int],
    replacement_volunteer_id: Optional[int],
    reason: str,
):
    """
    Backward-compatible signature for old pages.
    Under the hood, volunteer_id == user_id in the new model.
    """
    try:
        from src.db.repos.swaps import create_swap_request as _create_swap_request
    except ImportError:
        from src.db.repos.swap_requests import create_swap_request as _create_swap_request

    return _create_swap_request(
        assignment_id=int(assignment_id),
        requested_by_user_id=int(requested_by_volunteer_id) if requested_by_volunteer_id is not None else None,
        replacement_user_id=int(replacement_volunteer_id) if replacement_volunteer_id is not None else None,
        reason=reason,
    )


def list_swap_requests(status: Optional[str] = None):
    try:
        from src.db.repos.swaps import list_swap_requests as _list_swap_requests
    except ImportError:
        from src.db.repos.swap_requests import list_swap_requests as _list_swap_requests

    return _list_swap_requests(status=status)


def resolve_swap_request(req_id: int, status: str, resolved_by_admin: str):
    try:
        from src.db.repos.swaps import resolve_swap_request as _resolve_swap_request
    except ImportError:
        from src.db.repos.swap_requests import resolve_swap_request as _resolve_swap_request

    return _resolve_swap_request(
        int(req_id),
        str(status),
        str(resolved_by_admin),
    )


# =========================================================
# Reminders facade
# =========================================================
def rebuild_reminders_for_month(year: int, month: int, ministry_id: Optional[int] = None):
    from src.db.repos.reminders import rebuild_reminders_for_month as _rebuild_reminders_for_month

    mid = int(ministry_id or 1)
    return _rebuild_reminders_for_month(mid, int(year), int(month))


def list_reminders(status: Optional[str] = None, ministry_id: Optional[int] = None):
    from src.db.repos.reminders import list_reminders as _list_reminders

    mid = int(ministry_id or 1)
    return _list_reminders(status=status, ministry_id=mid)


def mark_reminder_sent(reminder_id: int):
    from src.db.repos.reminders import mark_reminder_sent as _mark_reminder_sent

    return _mark_reminder_sent(int(reminder_id))


def list_due_reminders_for_email(ministry_id: Optional[int] = None):
    from src.db.repos.reminders import list_due_reminders_for_email as _list_due_reminders_for_email

    mid = int(ministry_id or 1)
    return _list_due_reminders_for_email(ministry_id=mid)


def mark_reminders_sent(reminder_ids: list[int]):
    from src.db.repos.reminders import mark_reminders_sent as _mark_reminders_sent

    return _mark_reminders_sent([int(x) for x in reminder_ids])


__all__ = [
    "init_db",

    # users
    "upsert_user_from_kc",
    "get_user_by_kc_sub",
    "get_user_by_username",
    "update_user_profile",
    "list_users",

    # ministries
    "ensure_ministry",
    "upsert_ministry",
    "list_ministries",
    "list_ministry_leaders",
    "set_ministry_leader",

    # memberships
    "upsert_membership",
    "list_user_ministries",

    # volunteers
    "list_volunteers",
    "upsert_volunteer",
    "set_volunteer_active",
    "upsert_volunteer_prefs",

    # schedule
    "list_schedule_between",
    "ensure_service",
    "upsert_assignment",
    "list_services_in_month",
    "get_assignment_details",
    "set_assignment_volunteer_by_id",
    "set_assignment_user_by_id",
    "get_assignments_for_service",
    "clear_month_services",

    # swaps
    "create_swap_request",
    "list_swap_requests",
    "resolve_swap_request",

    # reminders
    "rebuild_reminders_for_month",
    "list_reminders",
    "mark_reminder_sent",
    "list_due_reminders_for_email",
    "mark_reminders_sent",
]