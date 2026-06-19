#!/usr/bin/env python3
"""Вход через браузер (Facebook Login / OAuth) и авто-сбор токенов страниц.

Что делает:
  1. Открывает браузер на странице согласия Facebook.
  2. Ты логинишься и жмёшь «Разрешить».
  3. Ловит ответ на http://localhost:8000/, меняет код на долгоживущий
     user-токен, вытягивает токены ВСЕХ твоих страниц и пишет config.json.

Можно запускать как скрипт (python login.py) или вызывать run_login()
из приложения.

Нужен .env рядом:
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
from pathlib import Path

import requests
from dotenv import load_dotenv

GRAPH_VERSION = "v21.0"
REDIRECT_URI = "http://localhost:8000/"
SCOPES = ["pages_show_list", "pages_manage_posts", "pages_read_engagement"]


def app_dir() -> Path:
    """Папка приложения: рядом с .exe в сборке, иначе корень проекта."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


class LoginError(RuntimeError):
    pass


class _Catcher(BaseHTTPRequestHandler):
    """Одноразовый обработчик: ловит ?code=... с редиректа Facebook."""
    code: str | None = None
    error: str | None = None

    def do_GET(self):
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        if "code" in params:
            _Catcher.code = params["code"][0]
            body = "Готово! Можно вернуться в приложение и закрыть вкладку."
        elif "error" in params:
            _Catcher.error = params.get("error_description", ["отказано"])[0]
            body = f"Отказано: {_Catcher.error}"
        else:
            self.send_response(204)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(f"<h2>{body}</h2>".encode("utf-8"))

    def log_message(self, *_):
        pass


def _get_auth_code(app_id: str) -> str:
    auth_url = (
        f"https://www.facebook.com/{GRAPH_VERSION}/dialog/oauth?"
        + urllib.parse.urlencode({
            "client_id": app_id,
            "redirect_uri": REDIRECT_URI,
            "scope": ",".join(SCOPES),
            "response_type": "code",
        })
    )
    # сбрасываем состояние на случай повторного входа
    _Catcher.code = _Catcher.error = None
    server = HTTPServer(("localhost", 8000), _Catcher)
    if not webbrowser.open(auth_url):
        print(f"Открой ссылку вручную:\n{auth_url}")
    while _Catcher.code is None and _Catcher.error is None:
        server.handle_request()
    server.server_close()
    if _Catcher.error:
        raise LoginError(f"вход отклонён: {_Catcher.error}")
    return _Catcher.code


def _exchange_for_long_lived(code: str, app_id: str, app_secret: str) -> str:
    base = f"https://graph.facebook.com/{GRAPH_VERSION}"
    r = requests.get(f"{base}/oauth/access_token", params={
        "client_id": app_id, "client_secret": app_secret,
        "redirect_uri": REDIRECT_URI, "code": code,
    }, timeout=30).json()
    if "error" in r:
        raise LoginError(r["error"].get("message", "обмен кода не удался"))
    short = r["access_token"]
    r = requests.get(f"{base}/oauth/access_token", params={
        "grant_type": "fb_exchange_token", "client_id": app_id,
        "client_secret": app_secret, "fb_exchange_token": short,
    }, timeout=30).json()
    if "error" in r:
        raise LoginError(r["error"].get("message", "обмен на долгий токен не удался"))
    return r["access_token"]


def _fetch_pages(user_token: str) -> list[dict]:
    base = f"https://graph.facebook.com/{GRAPH_VERSION}"
    url = f"{base}/me/accounts"
    params: dict | None = {"access_token": user_token,
                           "fields": "id,name,access_token", "limit": 100}
    pages: list[dict] = []
    while url:
        r = requests.get(url, params=params, timeout=30).json()
        if "error" in r:
            raise LoginError(r["error"].get("message", "не удалось получить страницы"))
        for p in r.get("data", []):
            pages.append({"name": p["name"], "page_id": p["id"],
                          "access_token": p["access_token"]})
        url = r.get("paging", {}).get("next")
        params = None
    return pages


def run_login(config_out: str | Path | None = None) -> dict:
    """Выполнить вход и сохранить config.json. Возвращает {ok, count|error}."""
    load_dotenv(app_dir() / ".env")
    app_id = os.getenv("FB_APP_ID")
    app_secret = os.getenv("FB_APP_SECRET")
    if not app_id or not app_secret:
        return {"ok": False, "error": "в .env нет FB_APP_ID / FB_APP_SECRET"}
    out = Path(config_out) if config_out else app_dir() / "config.json"
    try:
        code = _get_auth_code(app_id)
        user_token = _exchange_for_long_lived(code, app_id, app_secret)
        pages = _fetch_pages(user_token)
    except LoginError as e:
        return {"ok": False, "error": str(e)}
    if not pages:
        return {"ok": False,
                "error": "не найдено страниц (проверь, что ты админ и дал права)"}
    config = {"graph_version": GRAPH_VERSION, "pages": pages}
    out.write_text(json.dumps(config, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    return {"ok": True, "count": len(pages),
            "pages": [p["name"] for p in pages]}


def main():
    print("Открываю браузер для входа в Facebook...")
    res = run_login()
    if not res["ok"]:
        print(f"Ошибка: {res['error']}", file=sys.stderr)
        sys.exit(1)
    print(f"\nГотово! Сохранено {res['count']} страниц:")
    for name in res["pages"]:
        print(f"  • {name}")
    print("\nПроверь: python cli.py check")


if __name__ == "__main__":
    main()
