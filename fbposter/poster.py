"""Логика публикации на одну или несколько страниц."""
from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass
from pathlib import Path

from .api import GraphAPI, GraphAPIError

# Эмодзи для лёгкой вариации текста между страницами (анти-спам).
_VARY_EMOJI = ["", "✅", "🔥", "📣", "💼", "👉", "⭐", "📌"]


@dataclass
class Page:
    name: str
    page_id: str
    access_token: str


def load_pages(config_path: str | Path) -> tuple[list[Page], str]:
    """Загрузить страницы и версию API из config.json."""
    data = json.loads(Path(config_path).read_text(encoding="utf-8"))
    pages = [Page(p["name"], p["page_id"], p["access_token"]) for p in data["pages"]]
    return pages, data.get("graph_version", "v21.0")


def vary_text(message: str, page_name: str, index: int) -> str:
    """Сделать текст для конкретной страницы чуть уникальным.

    - подставляет имя страницы вместо плейсхолдера {page};
    - добавляет ротируемый эмодзи в конец (разный для каждой страницы).
    Это снижает риск антиспам-фильтра при одинаковых постах на 8 страниц.
    """
    text = message.replace("{page}", page_name)
    emoji = _VARY_EMOJI[index % len(_VARY_EMOJI)]
    return f"{text} {emoji}".rstrip()


@dataclass
class PostResult:
    page: str
    ok: bool
    detail: str
    # заполняется для предпросмотра/отчёта:
    final_message: str | None = None
    image_url: str | None = None
    scheduled_time: int | None = None


class Poster:
    def __init__(self, pages: list[Page], api: GraphAPI) -> None:
        self.pages = pages
        self.api = api

    def post_to_all(self, message: str, *, link: str | None = None,
                    image_url: str | None = None,
                    scheduled_time: int | None = None,
                    vary: bool = True,
                    dry_run: bool = False,
                    delay_range: tuple[float, float] = (2.0, 6.0),
                    ) -> list[PostResult]:
        """Опубликовать/запланировать пост на все страницы.

        vary       — слегка варьировать текст для каждой страницы;
        dry_run    — НИЧЕГО не публиковать, только вернуть предпросмотр;
        delay_range — случайная пауза (сек) между страницами при реальном
                      постинге (анти-спам). В dry_run паузы нет.
        """
        results: list[PostResult] = []
        last = len(self.pages) - 1
        for i, page in enumerate(self.pages):
            text = vary_text(message, page.name, i) if vary else message

            if dry_run:
                results.append(PostResult(
                    page.name, True, "dry-run (не опубликовано)",
                    final_message=text, image_url=image_url,
                    scheduled_time=scheduled_time))
                continue

            try:
                if image_url:
                    r = self.api.publish_photo(
                        page.page_id, page.access_token, image_url,
                        text, scheduled_time)
                else:
                    r = self.api.publish_text(
                        page.page_id, page.access_token, text,
                        link, scheduled_time)
                pid = r.get("id") or r.get("post_id", "?")
                results.append(PostResult(
                    page.name, True, str(pid),
                    final_message=text, image_url=image_url,
                    scheduled_time=scheduled_time))
            except GraphAPIError as e:
                results.append(PostResult(page.name, False, str(e),
                                          final_message=text))

            # пауза между страницами, чтобы не выглядеть как спам-бот
            if i != last:
                time.sleep(random.uniform(*delay_range))
        return results

    def verify_tokens(self) -> list[PostResult]:
        """Проверить, что все токены валидны (полезно перед запуском)."""
        out: list[PostResult] = []
        for page in self.pages:
            try:
                info = self.api.whoami(page.page_id, page.access_token)
                out.append(PostResult(page.name, True, info.get("name", "ok")))
            except GraphAPIError as e:
                out.append(PostResult(page.name, False, str(e)))
        return out
