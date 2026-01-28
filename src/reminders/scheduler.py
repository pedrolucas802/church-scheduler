from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from src.reminders.runner import run_reminders_job

_scheduler = None


def start_scheduler():
    global _scheduler

    if _scheduler:
        return  # already running

    scheduler = BackgroundScheduler(timezone="America/Fortaleza")

    # Twice a day: 08:00 and 20:00 UTC
    scheduler.add_job(
        run_reminders_job,
        CronTrigger(hour=8, minute=0),
        id="reminders_morning",
        replace_existing=True,
    )

    scheduler.add_job(
        run_reminders_job,
        CronTrigger(hour=20, minute=0),
        id="reminders_evening",
        replace_existing=True,
    )

    scheduler.start()
    _scheduler = scheduler

    print("[SCHEDULER] Reminder scheduler started (08:00 / 20:00 UTC)")