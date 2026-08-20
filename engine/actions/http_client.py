"""Conector HTTP generico (equivalente a los conectores de API en Power Automate)."""
from __future__ import annotations

import requests


class HttpActions:
    def __init__(self, logger, timeout: int = 30) -> None:
        self.logger = logger
        self.timeout = timeout
        self._session = requests.Session()

    def get(self, url: str, **kwargs) -> requests.Response:
        return self._session.get(url, timeout=self.timeout, **kwargs)

    def post(self, url: str, **kwargs) -> requests.Response:
        return self._session.post(url, timeout=self.timeout, **kwargs)

    def con_token(self, token: str) -> "HttpActions":
        self._session.headers["Authorization"] = f"Bearer {token}"
        return self
