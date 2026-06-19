#!/usr/bin/env python3
"""Десктопное приложение FB Job Poster.

Открывает нативное окно ОС (без браузера) с интерфейсом постинга.
Внутри поднимается локальный сервер на свободном порту, а pywebview
показывает его в обычном окне приложения.

Запуск из исходников:
    python desktop.py

Сборка в один исполняемый файл — см. README (раздел «Сборка .exe / .app»).
"""
from __future__ import annotations

import socket
import threading
import time

import webview  # pip install pywebview

from webapp.app import app


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _wait_until_up(port: int, timeout: float = 8.0) -> None:
    """Подождать, пока сервер начнёт принимать соединения."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.3):
                return
        except OSError:
            time.sleep(0.05)


def main() -> None:
    port = _free_port()

    def run_server() -> None:
        app.run(host="127.0.0.1", port=port, threaded=True,
                use_reloader=False)

    threading.Thread(target=run_server, daemon=True).start()
    _wait_until_up(port)

    webview.create_window(
        "FB Job Poster",
        f"http://127.0.0.1:{port}",
        width=1180, height=860, min_size=(920, 660),
    )
    webview.start()  # блокирует до закрытия окна


if __name__ == "__main__":
    main()
