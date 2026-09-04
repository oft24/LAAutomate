"""Tarjeta de KPI: valor grande + etiqueta + delta opcional."""
from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from app.resources.tokens import COLORES, ESPACIADO


class KpiCard(QFrame):
    _COLORES_TONO = {
        "acento": COLORES.acento,
        "cian": COLORES.cian,
        "violeta": COLORES.violeta,
        "ocre": COLORES.ocre,
    }

    def __init__(
        self,
        etiqueta: str,
        valor: str,
        delta: str | None = None,
        positivo: bool = True,
        tono: str = "acento",
    ) -> None:
        super().__init__()
        self.setObjectName("tarjetaKpi")
        self._tono = self._COLORES_TONO.get(tono, COLORES.acento)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(ESPACIADO.lg, ESPACIADO.md, ESPACIADO.lg, ESPACIADO.md)
        layout.setSpacing(4)

        acento = QFrame()
        acento.setFixedHeight(3)
        acento.setStyleSheet(f"background-color: {self._tono}; border-radius: 1px;")
        layout.addWidget(acento)

        self._etiqueta = QLabel(etiqueta)
        self._etiqueta.setObjectName("kpiEtiqueta")
        layout.addWidget(self._etiqueta)

        fila_valor = QVBoxLayout()
        fila_valor.setSpacing(0)
        self._valor = QLabel(valor)
        self._valor.setObjectName("kpiValor")
        self._valor.setStyleSheet(f"color: {self._tono};")
        fila_valor.addWidget(self._valor)
        layout.addLayout(fila_valor)

        if delta:
            self._delta = QLabel(delta)
            self._delta.setObjectName("kpiDelta")
            color = COLORES.musgo if positivo else COLORES.oxido
            self._delta.setStyleSheet(f"color: {color}; font-weight: 600; font-size: 12px;")
            layout.addWidget(self._delta)

    def actualizar_valor(self, valor: str) -> None:
        if valor == self._valor.text():
            return
        self._valor.setText(valor)
