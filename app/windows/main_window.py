"""Ventana principal: sidebar agrupada + vistas + tema Direccion B
aplicado globalmente. La logica de cada vista (registry, runner,
scheduler, vault) es exactamente la misma de antes -- este archivo solo
cambia COMO se presenta."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QStackedWidget, QWidget

from app.resources.tokens import construir_qss
from core.config import DESCRIPCION_APP, NOMBRE_APP

_RUTA_ICONO = Path(__file__).resolve().parent.parent / "resources" / "app_icon.ico"
from app.widgets.sidebar import Sidebar
from app.windows.automations_view import AutomationsView
from app.windows.dashboard_view import DashboardView
from app.windows.logs_view import LogsView
from app.windows.recorder_view import RecorderView
from app.windows.scheduler_view import SchedulerView
from app.windows.vault_view import VaultView
from app.windows.wiki_view import WikiView


class MainWindow(QMainWindow):
    def __init__(self, scheduler, runner) -> None:
        super().__init__()
        self.setWindowTitle(f"{NOMBRE_APP} - {DESCRIPCION_APP}")
        self.resize(1360, 860)
        if _RUTA_ICONO.exists():
            self.setWindowIcon(QIcon(str(_RUTA_ICONO)))
        self.setStyleSheet(construir_qss())

        self.sidebar = Sidebar()
        self.sidebar.cambiar_vista.connect(self._cambiar_vista)

        self.dashboard = DashboardView(runner, scheduler)
        self.automations_view = AutomationsView(scheduler, on_finalizado=self.dashboard.refrescar)
        self.recorder_view = RecorderView(on_automatizacion_creada=self._al_grabar_automatizacion)

        self.paginas = QStackedWidget()
        self.paginas.addWidget(self.dashboard)
        self.paginas.addWidget(self.automations_view)
        self.paginas.addWidget(self.recorder_view)
        self.paginas.addWidget(SchedulerView(scheduler))
        self.paginas.addWidget(LogsView())
        self.paginas.addWidget(VaultView())
        self.paginas.addWidget(WikiView())

        contenedor = QWidget()
        contenedor.setObjectName("fondoApp")
        layout = QHBoxLayout(contenedor)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.sidebar)
        layout.addWidget(self.paginas, stretch=1)
        self.setCentralWidget(contenedor)

    def _cambiar_vista(self, indice: int) -> None:
        self.paginas.setCurrentIndex(indice)

    def closeEvent(self, event) -> None:
        self.recorder_view._detener_listener_f5()
        super().closeEvent(event)

    def _al_grabar_automatizacion(self, nombre: str) -> None:
        self.automations_view.refrescar(seleccionar=nombre)
        self.dashboard.refrescar()
        self.sidebar.establecer_indice(1)  # salta a Automatizaciones para revisar/editar el codigo generado
