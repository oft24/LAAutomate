"""Disparador tipo 'cuando se crea un archivo en esta carpeta' (watchdog)."""
from __future__ import annotations

from typing import Callable

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


class _Handler(FileSystemEventHandler):
    def __init__(self, callback: Callable[[], None]) -> None:
        self._callback = callback

    def on_created(self, event) -> None:
        if not event.is_directory:
            self._callback()


def observar_carpeta(ruta: str, callback: Callable[[], None]) -> Observer:
    observer = Observer()
    observer.schedule(_Handler(callback), ruta, recursive=False)
    observer.start()
    return observer
