#!/usr/bin/env python3
"""Сборка десктоп-приложения в один исполняемый файл (PyInstaller).

    pip install pyinstaller
    python build_app.py

Результат появится в папке dist/:
    Windows — dist/FB Job Poster.exe
    macOS   — dist/FB Job Poster.app
    Linux   — dist/FB Job Poster (бинарник)

config.json и .env держи рядом с готовым файлом (они НЕ вшиваются внутрь).
"""
import os

import PyInstaller.__main__

sep = ";" if os.name == "nt" else ":"

PyInstaller.__main__.run([
    "desktop.py",
    "--noconfirm",
    "--clean",
    "--windowed",                 # без чёрного окна консоли
    "--name", "FB Job Poster",
    f"--add-data=webapp/templates{sep}templates",
    f"--add-data=webapp/static{sep}static",
    "--hidden-import=webview",
])
