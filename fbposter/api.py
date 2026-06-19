"""Тонкая обёртка над Facebook Graph API."""
from __future__ import annotations

import requests


class GraphAPIError(RuntimeError):
    """Ошибка, возвращённая Graph API (с человекочитаемым сообщением)."""


class GraphAPI:
    def __init__(self, version: str = "v21.0", timeout: int = 30) -> None:
        self.base = f"https://graph.facebook.com/{version}"
        self.timeout = timeout

    def _call(self, method: str, path: str, token: str, **params):
        params["access_token"] = token
        url = f"{self.base}/{path}"
        resp = requests.request(method, url, data=params, timeout=self.timeout)
        data = resp.json() if resp.content else {}
        if not resp.ok or "error" in data:
            err = data.get("error", {})
            msg = err.get("message", resp.text)
            code = err.get("code", resp.status_code)
            raise GraphAPIError(f"[{code}] {msg}")
        return data

    # --- посты ---------------------------------------------------------
    def publish_text(self, page_id: str, token: str, message: str,
                     link: str | None = None,
                     scheduled_time: int | None = None) -> dict:
        """Опубликовать или запланировать текстовый пост (опц. со ссылкой)."""
        params: dict = {"message": message}
        if link:
            params["link"] = link
        if scheduled_time:
            params["published"] = "false"
            params["scheduled_publish_time"] = scheduled_time
        return self._call("POST", f"{page_id}/feed", token, **params)

    def publish_photo(self, page_id: str, token: str, image_url: str,
                      message: str = "",
                      scheduled_time: int | None = None) -> dict:
        params: dict = {"url": image_url, "caption": message}
        if scheduled_time:
            params["published"] = "false"
            params["scheduled_publish_time"] = scheduled_time
        return self._call("POST", f"{page_id}/photos", token, **params)

    # --- служебное -----------------------------------------------------
    def whoami(self, page_id: str, token: str) -> dict:
        """Проверка токена: вернуть имя и id страницы."""
        return self._call("GET", page_id, token, fields="id,name")

    def list_scheduled(self, page_id: str, token: str) -> dict:
        """Список запланированных (ещё не опубликованных) постов."""
        return self._call("GET", f"{page_id}/scheduled_posts", token)
