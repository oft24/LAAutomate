"""Historial de ejecuciones en SQLite (para el dashboard de la app)."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager

from core.config import DB_PATH
from engine.automation_base import AutomationResult

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS ejecuciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    automatizacion TEXT NOT NULL,
    exito INTEGER NOT NULL,
    mensaje TEXT,
    iniciado_en TEXT,
    finalizado_en TEXT
);
"""


@contextmanager
def _conexion():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(_ESQUEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def guardar_ejecucion(nombre: str, resultado: AutomationResult) -> None:
    with _conexion() as conn:
        conn.execute(
            "INSERT INTO ejecuciones (automatizacion, exito, mensaje, iniciado_en, finalizado_en) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                nombre,
                int(resultado.success),
                resultado.message,
                resultado.started_at.isoformat() if resultado.started_at else None,
                resultado.finished_at.isoformat() if resultado.finished_at else None,
            ),
        )


def historial(nombre: str | None = None, limite: int = 50) -> list[sqlite3.Row]:
    with _conexion() as conn:
        conn.row_factory = sqlite3.Row
        if nombre:
            cur = conn.execute(
                "SELECT * FROM ejecuciones WHERE automatizacion = ? ORDER BY id DESC LIMIT ?",
                (nombre, limite),
            )
        else:
            cur = conn.execute("SELECT * FROM ejecuciones ORDER BY id DESC LIMIT ?", (limite,))
        return cur.fetchall()
