"""Logging estructurado: consola + archivo por automatizacion en /logs."""
from __future__ import annotations

import logging
from functools import lru_cache

from core.config import LOGS_DIR

_FORMATO = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


@lru_cache(maxsize=None)
def get_logger(nombre: str) -> logging.Logger:
    logger = logging.getLogger(nombre)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    consola = logging.StreamHandler()
    consola.setFormatter(logging.Formatter(_FORMATO))
    logger.addHandler(consola)

    archivo = logging.FileHandler(LOGS_DIR / f"{nombre.replace('.', '_')}.log", encoding="utf-8")
    archivo.setFormatter(logging.Formatter(_FORMATO))
    logger.addHandler(archivo)

    return logger
