"""Lectura/escritura de Excel. pandas para datos, pywin32 cuando se necesita
controlar Excel abierto (macros, formato condicional en vivo, etc)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd


class ExcelActions:
    def __init__(self, logger) -> None:
        self.logger = logger

    def leer(self, ruta: str | Path, hoja: str | int = 0) -> list[dict]:
        df = pd.read_excel(ruta, sheet_name=hoja)
        return df.to_dict(orient="records")

    def escribir(self, ruta: str | Path, filas: list[dict], hoja: str = "Sheet1") -> None:
        pd.DataFrame(filas).to_excel(ruta, sheet_name=hoja, index=False)
        self.logger.info("Excel escrito: %s (%d filas)", ruta, len(filas))

    def com(self):
        """Acceso a Excel via COM (pywin32) para casos que requieren la app abierta."""
        import win32com.client  # import perezoso: solo Windows con Office instalado

        return win32com.client.Dispatch("Excel.Application")
