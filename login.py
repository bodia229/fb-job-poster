#!/usr/bin/env python3
"""Вход через браузер (Facebook Login / OAuth) и авто-сбор токенов страниц.

Что делает:
  1. Открывает Chrome на странице согласия Facebook.
  2. Ты логинишься и жмёшь «Разрешить».
  3. Скрипт ловит ответ на http://localhost:8000/, меняет код на
     долгоживущий user-токен, вытягивает токены ВСЕХ твоих страниц
     и пишет config.json.

Запуск:
    python login.py

Нужен .env рядом со скриптом:
    FB_APP_ID=...
    FB_APP_SECRET=...
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests
from dotenv import load_dotenv

GRAPH_VERSION = "v21.0"
REDIRECT_URI = "http://localhost:8000/"
SCOPES = ["pages_show_list", "pages_manage_posts", "pages_read_engagement"]
CONFIG_OUT = "config.json"

load_dotenv()
APP_ID = os.getenv("FB_APP_ID")
APP_SECRET = os.getenv("FB_APP_SECRET")


def _fail(msg: str):
    print(f"Ошибка: {msg}", file=sys.stderr)
    sys.exit(1)


class _Catcher(BaseHTTPRequestHandler):
    """Одноразовый обработчик: ловит ?code=... с редиректа Facebook."""
    code: str | None = None
    error: str | None = None

    def do_GET(self):
        qs = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(qs)
        if "code" in params:
            _Catcher.code = params["code"][0]
            body = "Готово! Можно вернуться в терминал и закрыть вкладку."
        elif "error" in params:
            _Catcher.error = params.get("error_description", ["отказано"])[0]
            body = f"Отказано: {_Catcher.error}"
        else:
            # первый «пустой» заход на / — игнорируем
            self.send_response(204)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(f"<h2>{body}</h2>".encode("utf-8"))

    def log_message(self, *_):  # тишина в консоли
        pass


def get_auth_code() -> str:
    auth_url = (
        f"https://www.facebook.com/{GRAPH_VERSION}/dialog/oauth?"
        + urllib.parse.urlencode({
            "client_id": APP_ID,
            "redirect_uri": REDIRECT_URI,
            "scope": ",".join(SCOPES),
            "response_type": "code",
        })
    )
    server = HTTPServer(("localhost", 8000), _Catcher)
    print("Открываю браузер для входа в Facebook...")
    if not webbrowser.open(auth_url):
        print(f"Не удалось открыть браузер. Зайди вручную:\n{auth_url}")
    # ждём, пока придёт code или error
    while _Catcher.code is None and _Catcher.error is None:
        server.handle_request()
    server.server_close()
    if _Catcher.error:
        _fail(f"вход отклонён: {_Catcher.error}")
    return _Catcher.code


def exchange_for_long_lived(code: str) -> str:
    base = f"https://graph.facebook.com/{GRAPH_VERSION}"
    # код -> короткоживущий user-токен
    r = requests.get(f"{base}/oauth/access_token", params={
        "client_id": APP_ID,
        "client_secret": APP_SECRET,
        "redirect_uri": REDIRECT_URI,
        "code": code,
    }, timeout=30).json()
    if "error" in r:
        _fail(r["error"].get("message", "обмен кода не удался"))
    short = r["access_token"]
    # короткоживущий -> долгоживущий user-токен
    r = requests.get(f"{base}/oauth/access_token", params={
        "grant_type": "fb_exchange_token",
        "client_id": APP_ID,
        "client_secret": APP_SECRET,
        "fb_exchange_token": short,
    }, timeout=30).json()
    if "error" in r:
        _fail(r["error"].get("message", "обмен на долгоживущий токен не удался"))
    return r["access_token"]


def fetch_pages(user_token: str) -> list[dict]:
    """Вытянуть все страницы и их page-токены (с пагинацией)."""
    base = f"https://graph.facebook.com/{GRAPH_VERSION}"
    url = f"{base}/me/accounts"
    params = {"access_token": user_token, "fields": "id,name,access_token",
              "limit": 100}
    pages: list[dict] = []
    while url:
        r = requests.get(url, params=params, timeout=30).json()
        if "error" in r:
            _fail(r["error"].get("message", "не удалось получить страницы"))
        for p in r.get("data", []):
            pages.append({
                "name": p["name"],
                "page_id": p["id"],
                "access_token": p["access_token"],
            })
        url = r.get("paging", {}).get("next")
        params = None  # next уже содержит все параметры
    return pages


def main():
    if not APP_ID or not APP_SECRET:
        _fail("в .env нет FB_APP_ID / FB_APP_SECRET")
    code = get_auth_code()
    print("Получаю долгоживущий токен...")
    user_token = exchange_for_long_lived(code)
    print("Собираю токены страниц...")
    pages = fetch_pages(user_token)
    if not pages:
        _fail("не найдено ни одной страницы (проверь, что ты админ и дал права)")
    config = {"graph_version": GRAPH_VERSION, "pages": pages}
    with open(CONFIG_OUT, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    print(f"\nГотово! Сохранено {len(pages)} страниц в {CONFIG_OUT}:")
    for p in pages:
        print(f"  • {p['name']} ({p['page_id']})")
    print("\nПроверь: python cli.py check")


if __name__ == "__main__":
    main()
