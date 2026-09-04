"""Ventana principal: sidebar agrupada + vistas + tema Direccion B
aplicado globalmente. La logica de cada vista (registry, runner,
scheduler, vault) es exactamente la misma de antes -- este archivo solo
cambia COMO se presenta."""
from __future__ import annotations

import ctypes
import sys
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPropertyAnimation
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QMainWindow,
    QStackedWidget,
    QWidget,
)

from app.resources.tokens import construir_qss
from core.config import DESCRIPCION_APP, NOMBRE_APP

_RUTA_ICONO = Path(__file__).resolve().parent.parent / "resources" / "app_icon.ico"
from app.widgets.sidebar import CLAVES, Sidebar
from app.windows.automations_view import AutomationsView
from app.windows.assistant_view import AssistantView
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
        self.assistant_view = AssistantView(on_automatizacion_creada=self._al_grabar_automatizacion)
        self._animacion_pagina: QPropertyAnimation | None = None
        self._pagina_animada: QWidget | None = None

        # Las paginas se apilan en el orden de Sidebar.CLAVES, no en el
        # orden en que se escriban aqui: es lo que garantiza que el boton
        # N de la sidebar y la pagina N del stack sean siempre la misma
        # vista. Agregar una entrada a la sidebar sin su pagina revienta
        # al arrancar (KeyError) en vez de mostrar la vista equivocada.
        self.scheduler_view = SchedulerView(scheduler)
        paginas_por_clave = {
            "panel": self.dashboard,
            "automatizaciones": self.automations_view,
            "grabadora": self.recorder_view,
            "programador": self.scheduler_view,
            "asistente": self.assistant_view,
            "registros": LogsView(),
            "boveda": VaultView(),
            "wiki": WikiView(),
        }
        self.paginas = QStackedWidget()
        for clave in CLAVES:
            self.paginas.addWidget(paginas_por_clave[clave])

        contenedor = QWidget()
        contenedor.setObjectName("fondoApp")
        layout = QHBoxLayout(contenedor)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.sidebar)
        layout.addWidget(self.paginas, stretch=1)
        self.setCentralWidget(contenedor)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._activar_titulo_oscuro()

    def _activar_titulo_oscuro(self) -> None:
        """Pide a Windows un title bar oscuro; no reemplaza controles nativos."""
        if sys.platform != "win32":
            return
        try:
            valor = ctypes.c_int(1)
            for atributo in (20, 19):  # Windows 10 reciente / compilaciones anteriores
                resultado = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    int(self.winId()), atributo, ctypes.byref(valor), ctypes.sizeof(valor)
                )
                if resultado == 0:
                    break
        except (AttributeError, OSError):
            pass

    def _cambiar_vista(self, indice: int) -> None:
        if indice < 0 or indice >= self.paginas.count() or indice == self.paginas.currentIndex():
            return
        if self._animacion_pagina is not None:
            self._animacion_pagina.stop()
        if self._pagina_animada is not None:
            self._pagina_animada.setGraphicsEffect(None)

        self.paginas.setCurrentIndex(indice)
        pagina = self.paginas.currentWidget()
        efecto = QGraphicsOpacityEffect(pagina)
        pagina.setGraphicsEffect(efecto)
        animacion = QPropertyAnimation(efecto, b"opacity", self)
        animacion.setDuration(190)
        animacion.setStartValue(0.08)
        animacion.setEndValue(1.0)
        animacion.setEasingCurve(QEasingCurve.Type.OutCubic)
        animacion.finished.connect(lambda: pagina.setGraphicsEffect(None))
        self._pagina_animada = pagina
        self._animacion_pagina = animacion
        animacion.start()

    def closeEvent(self, event) -> None:
        self.recorder_view._detener_listener_f5()
        super().closeEvent(event)

    def _al_grabar_automatizacion(self, nombre: str) -> None:
        self.automations_view.refrescar(seleccionar=nombre)
        self.assistant_view.refrescar_contexto()
        self.dashboard.refrescar()
        # salta a Automatizaciones para revisar/editar el codigo generado
        self.sidebar.establecer_vista("automatizaciones")
