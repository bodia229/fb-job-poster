"""Локальный планировщик для повторяющихся напоминаний (APScheduler).

Нативное планирование Facebook (scheduled_publish_time) хорошо для разовых
постов. А если нужно «поднимать вакансию каждые N дней, пока она открыта» —
для этого здесь cron-планировщик, который сам вызывает публикацию.
"""
from __future__ import annotations

from apscheduler.schedulers.blocking import BlockingScheduler

from .poster import Poster


def run_recurring(poster: Poster, message: str, *, link: str | None = None,
                  image_url: str | None = None,
                  day_of_week: str = "mon,thu", hour: int = 10,
                  minute: int = 0) -> None:
    """Запускать публикацию по расписанию (по умолчанию пн и чт в 10:00).

    Останавливается по Ctrl+C. Держать процесс запущенным
    (systemd / screen / nohup на сервере или Деке).
    """
    sched = BlockingScheduler()

    @sched.scheduled_job("cron", day_of_week=day_of_week, hour=hour, minute=minute)
    def _job():
        results = poster.post_to_all(message, link=link, image_url=image_url)
        for r in results:
            status = "OK" if r.ok else "FAIL"
            print(f"[{status}] {r.page}: {r.detail}", flush=True)

    print(f"Планировщик запущен: {day_of_week} в {hour:02d}:{minute:02d}. "
          f"Ctrl+C для остановки.", flush=True)
    try:
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        print("\nОстановлено.")
