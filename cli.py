#!/usr/bin/env python3
"""CLI для постинга вакансий на свои Facebook-страницы.

Примеры:
    # проверить, что все токены валидны
    python cli.py check

    # опубликовать сразу на все страницы
    python cli.py post --text "Ищем повара. Детали: ..." --link https://...

    # запланировать на конкретное время (нативно в Facebook)
    python cli.py post --text "..." --at "2026-06-25 09:00"

    # повторять каждые пн и чт в 10:00 (локальный планировщик)
    python cli.py recurring --text "..." --days mon,thu --hour 10
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


def cmd_post(args):
    poster = _build(args)
    scheduled = _to_unix(args.at) if args.at else None
    results = poster.post_to_all(
        args.text, link=args.link, image_url=args.image,
        scheduled_time=scheduled)
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
    sp.add_argument("--image", default=None, help="URL картинки")
    sp.add_argument("--at", default=None, help='время: "YYYY-MM-DD HH:MM"')
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
