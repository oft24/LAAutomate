"""Historial de ejecuciones en SQLite (para el dashboard de la app)."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
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


def estadisticas_ejecuciones(ahora: datetime | None = None) -> dict:
    """KPIs sobre todo el historial, no sobre las 100 filas visibles.

    SQLite normaliza offsets con julianday. Las fechas heredadas sin zona
    se interpretan como UTC, igual que el historial de la interfaz.
    """
    ahora = ahora or datetime.now(timezone.utc)
    local = ahora.astimezone()
    inicio_hoy = local.replace(hour=0, minute=0, second=0, microsecond=0)
    with _conexion() as conn:
        conn.row_factory = sqlite3.Row
        fila = conn.execute(
            """WITH datos AS (
                SELECT exito, julianday(iniciado_en) AS inicio,
                       julianday(finalizado_en) AS fin FROM ejecuciones
            ) SELECT
                COALESCE(SUM(inicio >= julianday(?) AND inicio <= julianday(?)), 0) AS hoy,
                COUNT(*) AS total_7d,
                COALESCE(SUM(exito = 1), 0) AS exitos_7d,
                AVG(CASE WHEN fin >= inicio THEN (fin-inicio)*86400 END) AS duracion_7d
            FROM datos WHERE inicio >= julianday(?) AND inicio <= julianday(?)""",
            (inicio_hoy.isoformat(), ahora.isoformat(), (ahora - timedelta(days=7)).isoformat(), ahora.isoformat()),
        ).fetchone()
        return dict(fila)
