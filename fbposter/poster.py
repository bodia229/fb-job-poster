"""Логика публикации на одну или несколько страниц."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .api import GraphAPI, GraphAPIError


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


@dataclass
class PostResult:
    page: str
    ok: bool
    detail: str


class Poster:
    def __init__(self, pages: list[Page], api: GraphAPI) -> None:
        self.pages = pages
        self.api = api

    def post_to_all(self, message: str, link: str | None = None,
                    image_url: str | None = None,
                    scheduled_time: int | None = None) -> list[PostResult]:
        """Опубликовать/запланировать один и тот же пост на все страницы."""
        results: list[PostResult] = []
        for page in self.pages:
            try:
                if image_url:
                    r = self.api.publish_photo(
                        page.page_id, page.access_token, image_url,
                        message, scheduled_time)
                else:
                    r = self.api.publish_text(
                        page.page_id, page.access_token, message,
                        link, scheduled_time)
                pid = r.get("id") or r.get("post_id", "?")
                results.append(PostResult(page.name, True, str(pid)))
            except GraphAPIError as e:
                results.append(PostResult(page.name, False, str(e)))
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
