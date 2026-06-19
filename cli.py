#!/usr/bin/env python3
"""CLI для постинга вакансий на свои Facebook-страницы.

Примеры:
    # проверить, что все токены валидны
    python cli.py check

    # опубликовать сразу на все страницы
    python cli.py post --text "Ищем повара. Детали: ..." --link https://...

    # запланировать на конкретное время (нативно в Facebook)
    python cli.py post --text "..." --at "2026-06-25 09:00"

    # ТЕСТ без публикации: показать текст и баннер по каждой странице
    python cli.py post --text "Ищем повара {page}" --image banner.jpg --dry-run

    # повторять каждые пн и чт в 10:00 (локальный планировщик)
    python cli.py recurring --text "..." --days mon,thu --hour 10

Подсказка: в тексте можно использовать {page} — подставится имя страницы.
Для теста без токенов запусти dry-run на примере:
    python cli.py --config config.example.json post --text "..." --dry-run
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime

from fbposter import GraphAPI, Poster, load_pages
from fbposter.scheduler import run_recurring

CONFIG = "config.json"


def _build(args) -> Poster:
    pages, version = load_pages(args.config)
    return Poster(pages, GraphAPI(version))


def _to_unix(when: str) -> int:
    dt = datetime.strptime(when, "%Y-%m-%d %H:%M")
    return int(time.mktime(dt.timetuple()))


def cmd_check(args):
    for r in _build(args).verify_tokens():
        print(f"[{'OK' if r.ok else 'FAIL'}] {r.page}: {r.detail}")


def _print_preview(results):
    """Красиво показать, что будет опубликовано (для dry-run)."""
    print("\n=== ПРЕДПРОСМОТР (ничего не опубликовано) ===\n")
    for r in results:
        print(f"┌─ {r.page}")
        banner = r.image_url if r.image_url else "(без баннера, обычный текст)"
        print(f"│  Баннер: {banner}")
        if r.scheduled_time:
            when = time.strftime("%Y-%m-%d %H:%M",
                                 time.localtime(r.scheduled_time))
            print(f"│  Когда:  запланировано на {when}")
        else:
            print("│  Когда:  сразу при запуске")
        print("│  Текст:")
        for line in (r.final_message or "").splitlines() or [""]:
            print(f"│    {line}")
        print("└" + "─" * 40 + "\n")
    print(f"Итого страниц: {len(results)}. Запусти без --dry-run, чтобы "
          f"опубликовать.")


def cmd_post(args):
    poster = _build(args)
    scheduled = _to_unix(args.at) if args.at else None
    results = poster.post_to_all(
        args.text, link=args.link, image_url=args.image,
        scheduled_time=scheduled, vary=not args.no_vary,
        dry_run=args.dry_run,
        delay_range=(args.delay_min, args.delay_max))
    if args.dry_run:
        _print_preview(results)
        return
    failed = 0
    for r in results:
        print(f"[{'OK' if r.ok else 'FAIL'}] {r.page}: {r.detail}")
        failed += 0 if r.ok else 1
    sys.exit(1 if failed else 0)


def cmd_recurring(args):
    poster = _build(args)
    run_recurring(poster, args.text, link=args.link, image_url=args.image,
                  day_of_week=args.days, hour=args.hour, minute=args.minute)


def main():
    p = argparse.ArgumentParser(description="Постинг вакансий на FB-страницы")
    p.add_argument("--config", default=CONFIG, help="путь к config.json")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("check", help="проверить токены страниц")
    sp.set_defaults(func=cmd_check)

    sp = sub.add_parser("post", help="опубликовать/запланировать пост")
    sp.add_argument("--text", required=True)
    sp.add_argument("--link", default=None)
    sp.add_argument("--image", default=None, help="URL картинки (баннер)")
    sp.add_argument("--at", default=None, help='время: "YYYY-MM-DD HH:MM"')
    sp.add_argument("--dry-run", action="store_true",
                    help="не публиковать — только показать текст и баннер")
    sp.add_argument("--no-vary", action="store_true",
                    help="не варьировать текст между страницами")
    sp.add_argument("--delay-min", type=float, default=2.0,
                    help="мин. пауза между страницами, сек")
    sp.add_argument("--delay-max", type=float, default=6.0,
                    help="макс. пауза между страницами, сек")
    sp.set_defaults(func=cmd_post)

    sp = sub.add_parser("recurring", help="повторять по расписанию")
    sp.add_argument("--text", required=True)
    sp.add_argument("--link", default=None)
    sp.add_argument("--image", default=None)
    sp.add_argument("--days", default="mon,thu", help="напр. mon,thu,sat")
    sp.add_argument("--hour", type=int, default=10)
    sp.add_argument("--minute", type=int, default=0)
    sp.set_defaults(func=cmd_recurring)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
