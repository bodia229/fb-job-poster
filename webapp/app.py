#!/usr/bin/env python3
"""Локальный веб-интерфейс для постинга вакансий на Facebook-страницы.

Запуск:
    python -m webapp.app          # из корня проекта
затем открой http://localhost:5000
"""
from __future__ import annotations

import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from fbposter import GraphAPI, Poster, load_pages
from fbposter.poster import _VARY_EMOJI, vary_text

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config.json"

app = Flask(__name__)


def _build_poster() -> Poster:
    pages, version = load_pages(CONFIG)
    return Poster(pages, GraphAPI(version))


def _to_unix(when: str) -> int | None:
    if not when:
        return None
    # принимаем "YYYY-MM-DDTHH:MM" (из <input type=datetime-local>) и с пробелом
    when = when.replace("T", " ")
    dt = datetime.strptime(when, "%Y-%m-%d %H:%M")
    return int(time.mktime(dt.timetuple()))


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def status():
    if not CONFIG.exists():
        return jsonify(connected=False, pages=[], emoji=_VARY_EMOJI)
    pages, _ = load_pages(CONFIG)
    return jsonify(
        connected=True,
        pages=[{"id": p.page_id, "name": p.name} for p in pages],
        emoji=_VARY_EMOJI,
    )


@app.route("/api/preview", methods=["POST"])
def preview():
    """Серверный предпросмотр (как именно уйдёт текст), без публикации."""
    d = request.get_json(force=True)
    if not CONFIG.exists():
        return jsonify(error="Страницы не подключены"), 400
    pages, _ = load_pages(CONFIG)
    selected = set(d.get("pages", []))
    vary = d.get("vary", True)
    out = []
    idx = 0
    for p in pages:
        if selected and p.page_id not in selected:
            continue
        text = vary_text(d.get("text", ""), p.name, idx) if vary else d.get("text", "")
        out.append({"page": p.name, "text": text})
        idx += 1
    return jsonify(items=out)


@app.route("/api/publish", methods=["POST"])
def publish():
    d = request.get_json(force=True)
    if not CONFIG.exists():
        return jsonify(error="Страницы не подключены"), 400
    poster = _build_poster()
    selected = set(d.get("pages", []))
    if selected:
        poster.pages = [p for p in poster.pages if p.page_id in selected]
    if not poster.pages:
        return jsonify(error="Не выбрано ни одной страницы"), 400

    try:
        scheduled = _to_unix(d.get("at", ""))
    except ValueError:
        return jsonify(error="Неверный формат времени"), 400

    results = poster.post_to_all(
        d.get("text", ""),
        link=d.get("link") or None,
        image_url=d.get("image") or None,
        scheduled_time=scheduled,
        vary=d.get("vary", True),
        dry_run=bool(d.get("dry_run")),
        delay_range=(float(d.get("delay_min", 2)), float(d.get("delay_max", 6))),
    )
    return jsonify(results=[{
        "page": r.page, "ok": r.ok, "detail": r.detail,
    } for r in results])


@app.route("/api/login", methods=["POST"])
def login():
    """Запустить вход через браузер (login.py) фоновым процессом."""
    try:
        subprocess.Popen([sys.executable, str(ROOT / "login.py")], cwd=str(ROOT))
        return jsonify(started=True)
    except Exception as e:  # noqa: BLE001
        return jsonify(started=False, error=str(e)), 500


if __name__ == "__main__":
    print("Открой http://localhost:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)
