from __future__ import annotations

import os

from PySide6.QtWidgets import QPlainTextEdit, QStackedLayout, QVBoxLayout, QWidget

from app.widgets.empty_state import EmptyState
from app.widgets.page_header import PageHeader
from core.config import LOGS_DIR


class LogsView(QWidget):
    def __init__(self) -> None:
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        layout.addWidget(
            PageHeader(
                "Registros",
                "El log más reciente de cualquier automatización que haya corrido",
                acciones=[("Abrir carpeta", self._abrir_carpeta), ("Actualizar", self._cargar_ultimo_log)],
            )
        )

        self._contenedor = QWidget()
        self._pila = QStackedLayout(self._contenedor)

        self.texto = QPlainTextEdit(readOnly=True)
        self.texto.setObjectName("consola")
        self._vacio = EmptyState(
            "Sin registros todavía",
            "Aquí vas a ver el log detallado en cuanto corras tu primera automatización.",
        )
        self._pila.addWidget(self.texto)
        self._pila.addWidget(self._vacio)
        layout.addWidget(self._contenedor, stretch=1)

        self._cargar_ultimo_log()

    def _cargar_ultimo_log(self) -> None:
        archivos = sorted(LOGS_DIR.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
        if archivos:
            self._pila.setCurrentWidget(self.texto)
            self.texto.setPlainText(archivos[0].read_text(encoding="utf-8", errors="ignore"))
        else:
            self._pila.setCurrentWidget(self._vacio)

    @staticmethod
    def _abrir_carpeta() -> None:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        os.startfile(str(LOGS_DIR))  # noqa: S606 - abrir con el explorador de Windows
