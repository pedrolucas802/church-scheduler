import os
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from src.db import get_bool_app_setting, set_app_setting
from src.reminders.runner import run_reminders_job

_scheduler = None
FORTALEZA_TZ = ZoneInfo("America/Fortaleza")
SCHEDULER_SETTING_KEY = "reminder_scheduler_enabled"


def _env_default_enabled() -> bool:
    raw = (os.getenv("REMINDER_SCHEDULER_ENABLED") or "").strip().lower()
    if not raw:
        return False
    return raw not in {"0", "false", "no", "off"}


def scheduler_enabled() -> bool:
    return get_bool_app_setting(SCHEDULER_SETTING_KEY, default=_env_default_enabled())


def set_scheduler_enabled(enabled: bool):
    set_app_setting(SCHEDULER_SETTING_KEY, "true" if enabled else "false")


def scheduler_running() -> bool:
    return bool(_scheduler and getattr(_scheduler, "running", False))


def stop_scheduler():
    global _scheduler

    if not _scheduler:
        return

    _scheduler.shutdown(wait=False)
    _scheduler = None
    print("[SCHEDULER] Reminder scheduler stopped")


def start_scheduler():
    global _scheduler

    if _scheduler:
        return  # already running

    if not scheduler_enabled():
        print("[SCHEDULER] Reminder scheduler disabled by REMINDER_SCHEDULER_ENABLED")
        return

    scheduler = BackgroundScheduler(timezone="America/Fortaleza")

    scheduler.add_job(
        run_reminders_job,
        IntervalTrigger(minutes=5),
        next_run_time=datetime.now(FORTALEZA_TZ),
        id="reminders_polling",
        replace_existing=True,
    )

    scheduler.start()
    _scheduler = scheduler

    print("[SCHEDULER] Reminder scheduler started (every 5 minutes, America/Fortaleza)")


def apply_scheduler_setting():
    if scheduler_enabled():
        start_scheduler()
    else:
        stop_scheduler()
