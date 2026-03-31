from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from src.reminders.runner import run_reminders_job

_scheduler = None
FORTALEZA_TZ = ZoneInfo("America/Fortaleza")


def start_scheduler():
    global _scheduler

    if _scheduler:
        return  # already running

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
