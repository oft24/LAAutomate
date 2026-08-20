"""Alertas cuando una automatizacion falla (correo o webhook de Teams/Slack)."""
from __future__ import annotations

import os

import requests


def avisar_teams(mensaje: str) -> None:
    webhook_url = os.getenv("TEAMS_WEBHOOK_URL")
    if not webhook_url:
        return
    requests.post(webhook_url, json={"text": mensaje}, timeout=10)
