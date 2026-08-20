"""Disparador tipo 'cuando se recibe una peticion HTTP' (equivalente al
trigger de HTTP request de Power Automate), servido localmente con FastAPI."""
from __future__ import annotations

import threading
from typing import Callable

import uvicorn
from fastapi import FastAPI, Request

app = FastAPI(title="RPA Webhooks")
_handlers: dict[str, Callable[[dict], None]] = {}


@app.post("/webhook/{nombre}")
async def _recibir(nombre: str, request: Request) -> dict:
    payload = await request.json()
    handler = _handlers.get(nombre)
    if handler:
        handler(payload)
    return {"recibido": handler is not None}


def registrar_webhook(nombre: str, callback: Callable[[dict], None]) -> None:
    _handlers[nombre] = callback


def iniciar_servidor(puerto: int = 8765) -> threading.Thread:
    hilo = threading.Thread(
        target=lambda: uvicorn.run(app, host="127.0.0.1", port=puerto, log_level="warning"),
        daemon=True,
    )
    hilo.start()
    return hilo
