from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QStackedLayout,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.resources.tokens import DENSIDAD, ESPACIADO
from app.widgets.empty_state import EmptyState
from app.widgets.kpi_card import KpiCard
from app.widgets.page_header import PageHeader
from app.widgets.status_badge import StatusBadge
from engine.registry import listar

_COLUMNAS = ["Automatización", "Categoría", "Disparador", "Próxima ejecución", "Estado"]


class SchedulerView(QWidget):
    def __init__(self, scheduler) -> None:
        super().__init__()
        self.scheduler = scheduler

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(ESPACIADO.md)

        layout.addWidget(
            PageHeader("Programador", "Disparadores activos y cuándo va a correr cada automatización")
        )

        fila_kpis = QHBoxLayout()
        fila_kpis.setSpacing(ESPACIADO.lg)
        self.kpi_programadas = KpiCard("Programadas (cron)", "—")
        self.kpi_manuales = KpiCard("Solo manuales", "—")
        self.kpi_proxima = KpiCard("Próxima ejecución", "—")
        for kpi in (self.kpi_programadas, self.kpi_manuales, self.kpi_proxima):
            fila_kpis.addWidget(kpi)
        layout.addLayout(fila_kpis)

        self._contenedor = QWidget()
        self._pila = QStackedLayout(self._contenedor)

        self.tabla = QTableWidget(0, len(_COLUMNAS))
        self.tabla.setHorizontalHeaderLabels(_COLUMNAS)
        self.tabla.verticalHeader().hide()
        self.tabla.verticalHeader().setDefaultSectionSize(DENSIDAD.alto_fila)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.setShowGrid(False)

        header = self.tabla.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        # Fixed, no ResizeToContents: un cell widget (el badge) no siempre
        # reporta su sizeHint real a tiempo para el calculo automatico de
        # ancho -- resultaba en textos como "Programado" cortados a
        # "Programa". Un ancho fijo generoso evita ese corte.
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.tabla.setColumnWidth(4, 130)

        self._vacio = EmptyState(
            "Sin disparadores todavía",
            "Registra una automatización con un disparador de tipo cron para verla programada aquí.",
        )
        self._pila.addWidget(self.tabla)
        self._pila.addWidget(self._vacio)
        layout.addWidget(self._contenedor, stretch=1)

        self._llenar()

    def _llenar(self) -> None:
        especificaciones = listar()
        self._pila.setCurrentWidget(self._vacio if not especificaciones else self.tabla)

        proximas = dict(self.scheduler.proximas_ejecuciones())

        self.tabla.setRowCount(len(especificaciones))
        n_programadas = 0
        for i, spec in enumerate(especificaciones):
            es_cron = spec.disparador.startswith("cron:")
            n_programadas += es_cron

            self.tabla.setItem(i, 0, QTableWidgetItem(spec.nombre))
            self.tabla.setItem(i, 1, self._item_centrado(spec.categoria))
            self.tabla.setItem(i, 2, QTableWidgetItem(spec.disparador))

            if spec.nombre in proximas:
                texto_proxima = proximas[spec.nombre].strftime("%d %b %H:%M")
            else:
                texto_proxima = "—"
            self.tabla.setItem(i, 3, self._item_centrado(texto_proxima))

            self.tabla.setCellWidget(
                i, 4, self._centrado(StatusBadge("programado" if es_cron else "manual"))
            )

        self.kpi_programadas.actualizar_valor(str(n_programadas))
        self.kpi_manuales.actualizar_valor(str(len(especificaciones) - n_programadas))
        if proximas:
            primera = min(proximas.values())
            self.kpi_proxima.actualizar_valor(primera.strftime("%d %b %H:%M"))
        else:
            self.kpi_proxima.actualizar_valor("Sin programar")

    @staticmethod
    def _item_centrado(texto: str) -> QTableWidgetItem:
        item = QTableWidgetItem(texto)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item

    @staticmethod
    def _centrado(widget: QWidget) -> QWidget:
        envoltorio = QWidget()
        l = QHBoxLayout(envoltorio)
        l.setContentsMargins(0, 0, 0, 0)
        l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l.addWidget(widget)
        return envoltorio
