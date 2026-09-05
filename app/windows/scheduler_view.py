from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QStackedLayout,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from app.i18n import QTableWidget
from app.i18n import QLabel, QPushButton

from app.resources.tokens import DENSIDAD, ESPACIADO
from app.widgets.empty_state import EmptyState
from app.widgets.kpi_card import KpiCard
from app.widgets.page_header import PageHeader
from app.widgets.status_badge import StatusBadge
from engine.registry import listar

_COLUMNAS = ["Automatización", "Categoría", "Disparador", "Próxima ejecución", "Estado"]

REFRESCO_MS = 60_000


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
        ayuda = QLabel("El horario se guarda en el código: cron:minuto hora día mes día-semana. La app debe estar abierta para ejecutarlo.")
        ayuda.setWordWrap(True)
        layout.addWidget(ayuda)
        editar = QPushButton("Editar disparador en Automatizaciones")
        editar.clicked.connect(self._editar_disparador)
        layout.addWidget(editar, alignment=Qt.AlignmentFlag.AlignLeft)

        fila_kpis = QHBoxLayout()
        fila_kpis.setSpacing(ESPACIADO.lg)
        self.kpi_programadas = KpiCard("Programadas (cron)", "—", tono="acento")
        self.kpi_manuales = KpiCard("Solo manuales", "—", tono="cian")
        self.kpi_proxima = KpiCard("Próxima ejecución", "—", tono="violeta")
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

        # Antes esta tabla se llenaba UNA vez, en el constructor, y nunca
        # mas: una automatizacion grabada (o creada por el Asistente IA)
        # despues de arrancar no aparecia aqui hasta reiniciar la app, y
        # "Proxima ejecucion" se quedaba congelada en la hora que era
        # cuando abriste el programa. Ahora se recalcula al entrar a la
        # vista y cada minuto mientras se esta mirando.
        self._timer = QTimer(self)
        self._timer.setInterval(REFRESCO_MS)
        self._timer.timeout.connect(self.refrescar)

        self._llenar()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.refrescar()
        self._timer.start()

    def hideEvent(self, event) -> None:
        # Parado mientras no se ve: recorrer los jobs cada minuto para una
        # pagina que nadie esta mirando es trabajo tirado.
        self._timer.stop()
        super().hideEvent(event)

    def refrescar(self) -> None:
        self._llenar()

    def _editar_disparador(self) -> None:
        ventana = self.window()
        fila = self.tabla.currentRow()
        if fila >= 0 and hasattr(ventana, "automations_view"):
            ventana.automations_view.refrescar(seleccionar=self.tabla.item(fila, 0).text())
        if hasattr(ventana, "sidebar"):
            ventana.sidebar.establecer_vista("automatizaciones")

    def _llenar(self) -> None:
        especificaciones = listar()
        self._pila.setCurrentWidget(self._vacio if not especificaciones else self.tabla)

        proximas = dict(self.scheduler.proximas_ejecuciones())

        self.tabla.setRowCount(len(especificaciones))
        n_programadas = 0
        n_manuales = 0
        for i, spec in enumerate(especificaciones):
            es_cron = spec.disparador.startswith("cron:")
            n_programadas += es_cron
            n_manuales += spec.disparador == "manual"

            self.tabla.setItem(i, 0, QTableWidgetItem(spec.nombre))
            self.tabla.setItem(i, 1, self._item_centrado(spec.categoria))
            self.tabla.setItem(i, 2, QTableWidgetItem(spec.disparador))

            if spec.nombre in proximas:
                texto_proxima = proximas[spec.nombre].strftime("%d %b %H:%M")
            else:
                texto_proxima = "—"
            self.tabla.setItem(i, 3, self._item_centrado(texto_proxima))

            if spec.disparador.startswith("carpeta:"):
                estado = QLabel("Carpeta")
            elif es_cron and spec.nombre not in proximas:
                estado = QLabel("Sin activar")
            else:
                estado = StatusBadge("programado" if es_cron else "manual")
            self.tabla.setCellWidget(i, 4, self._centrado(estado))

        self.kpi_programadas.actualizar_valor(str(n_programadas))
        self.kpi_manuales.actualizar_valor(str(n_manuales))
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
