"""Panel principal: 4 KPIs, la pista de ejecuciones (elemento firma), y la
tabla de ultimas ejecuciones. Sigue leyendo exactamente los mismos datos
de siempre -- core.database.historial() y engine.scheduler.Scheduler --
solo cambia como se presentan."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QStackedLayout, QVBoxLayout, QWidget

from app.resources.tokens import COLORES, ESPACIADO, TIPO
from app.widgets.data_table import DataTable, FilaEjecucion
from app.widgets.empty_state import EmptyState
from app.widgets.kpi_card import KpiCard
from app.widgets.page_header import PageHeader
from app.widgets.status_badge import ESTADOS
from app.widgets.step_track import StepTrack
from app.widgets.toast import mostrar_toast
from app.workers import AutomationWorker
from core.config import LOGS_DIR
from core.database import historial
from engine.registry import listar, obtener

REFRESCO_AUTOMATICO_MS = 10_000


class DashboardView(QWidget):
    def __init__(self, runner, scheduler) -> None:
        super().__init__()
        self.runner = runner
        self.scheduler = scheduler
        self._workers: list[AutomationWorker] = []

        layout_raiz = QVBoxLayout(self)
        layout_raiz.setContentsMargins(24, 24, 24, 24)
        layout_raiz.setSpacing(16)

        layout_raiz.addWidget(
            PageHeader(
                "Panel principal",
                "Qué está pasando con tus automatizaciones hoy",
                acciones=[("Ejecutar todo", self._ejecutar_todo)],
            )
        )

        fila_kpis = QHBoxLayout()
        fila_kpis.setSpacing(16)
        self.kpi_hoy = KpiCard("Ejecuciones hoy", "—")
        self.kpi_exito = KpiCard("Tasa de éxito (7 días)", "—")
        self.kpi_duracion = KpiCard("Duración media", "—")
        self.kpi_proxima = KpiCard("Próxima ejecución", "—")
        for kpi in (self.kpi_hoy, self.kpi_exito, self.kpi_duracion, self.kpi_proxima):
            fila_kpis.addWidget(kpi)
        layout_raiz.addLayout(fila_kpis)

        # Subtitulo + leyenda en la MISMA fila: la pista colorea cada nodo
        # por resultado y hasta ahora no habia nada que dijera que
        # significa cada color -- habia que abrir un nodo para deducirlo.
        fila_pista = QHBoxLayout()
        fila_pista.setSpacing(ESPACIADO.md)
        fila_pista.addWidget(self._subtitulo("Pista de ejecuciones recientes"))
        fila_pista.addStretch()
        for estado in ("completado", "con_error", "en_curso"):
            fila_pista.addWidget(self._marca_leyenda(estado))
        layout_raiz.addLayout(fila_pista)

        self.step_track = StepTrack()
        self.step_track.nodo_clickeado.connect(self._al_click_nodo)
        layout_raiz.addWidget(self.step_track)

        layout_raiz.addWidget(self._subtitulo("Últimas ejecuciones"))

        self._contenedor_tabla = QWidget()
        self._pila = QStackedLayout(self._contenedor_tabla)
        self.tabla = DataTable()
        self.tabla.reintentar_solicitado.connect(self._reintentar)
        self._vacio = EmptyState(
            "Todavía no hay ejecuciones",
            "Aquí vas a ver el historial en cuanto corras tu primera automatización — "
            "manual, o cuando le toque a su disparador.",
            "Ir a Automatizaciones",
            self._ir_a_automatizaciones,
        )
        self._pila.addWidget(self.tabla)
        self._pila.addWidget(self._vacio)
        layout_raiz.addWidget(self._contenedor_tabla, stretch=1)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refrescar)
        self._timer.start(REFRESCO_AUTOMATICO_MS)

        self.refrescar()

    @staticmethod
    def _marca_leyenda(estado: str) -> QWidget:
        """Punto + nombre, con los MISMOS colores que StatusBadge -- se
        leen de ESTADOS, no se repiten a mano, para que la leyenda no
        pueda quedar desfasada de los nodos que explica."""
        etiqueta, color, _suave = ESTADOS[estado]

        marca = QWidget()
        fila = QHBoxLayout(marca)
        fila.setContentsMargins(0, 0, 0, 0)
        fila.setSpacing(5)

        punto = QLabel("●")
        punto.setStyleSheet(f"color: {color}; font-size: 9px;")
        fila.addWidget(punto)

        texto = QLabel(etiqueta.lower())
        texto.setStyleSheet(f"color: {COLORES.grafito}; font-size: {TIPO.t_caption}px;")
        fila.addWidget(texto)
        return marca

    @staticmethod
    def _subtitulo(texto: str) -> QLabel:
        etiqueta = QLabel(texto)
        etiqueta.setObjectName("subtituloSeccion")
        return etiqueta

    # ---------- datos ----------

    def refrescar(self) -> None:
        filas_crudas = historial(limite=100)
        filas = [self._a_fila_ejecucion(f) for f in filas_crudas]

        self._pila.setCurrentWidget(self._vacio if not filas else self.tabla)
        self.tabla.establecer_filas(filas)
        self.step_track.establecer_filas(filas)
        self._actualizar_kpis(filas)

    @staticmethod
    def _a_fila_ejecucion(fila) -> FilaEjecucion:
        nombre = fila["automatizacion"]
        return FilaEjecucion(
            automatizacion=nombre,
            exito=bool(fila["exito"]),
            mensaje=fila["mensaje"],
            iniciado_en=fila["iniciado_en"],
            finalizado_en=fila["finalizado_en"],
            ruta_captura=LOGS_DIR / "screenshots" / f"{nombre}_error.png",
            ruta_log=LOGS_DIR / f"{nombre.replace('.', '_')}.log",
        )

    def _actualizar_kpis(self, filas: list[FilaEjecucion]) -> None:
        ahora = datetime.now(timezone.utc)
        hoy = ahora.date()

        def parsear(v: str | None) -> datetime | None:
            if not v:
                return None
            try:
                dt = datetime.fromisoformat(v)
            except ValueError:
                return None
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

        de_hoy = [f for f in filas if (dt := parsear(f.iniciado_en)) and dt.date() == hoy]
        self.kpi_hoy.actualizar_valor(str(len(de_hoy)))

        de_7_dias = [f for f in filas if (dt := parsear(f.iniciado_en)) and (ahora - dt).days < 7]
        if de_7_dias:
            tasa = sum(1 for f in de_7_dias if f.exito) / len(de_7_dias) * 100
            self.kpi_exito.actualizar_valor(f"{tasa:.0f}%")
        else:
            self.kpi_exito.actualizar_valor("—")

        duraciones = []
        for f in filas:
            inicio, fin = parsear(f.iniciado_en), parsear(f.finalizado_en)
            if inicio and fin:
                duraciones.append((fin - inicio).total_seconds())
        if duraciones:
            promedio = sum(duraciones) / len(duraciones)
            self.kpi_duracion.actualizar_valor(f"{promedio:.1f} s")
        else:
            self.kpi_duracion.actualizar_valor("—")

        proximas = self.scheduler.proximas_ejecuciones()
        if proximas:
            nombre, cuando = proximas[0]
            self.kpi_proxima.actualizar_valor(cuando.strftime("%H:%M"))
        else:
            self.kpi_proxima.actualizar_valor("Sin programar")

    # ---------- acciones ----------

    def _al_click_nodo(self, indice: int) -> None:
        self.tabla.mostrar_fila(indice)

    def _ir_a_automatizaciones(self) -> None:
        ventana = self.window()
        if hasattr(ventana, "sidebar"):
            ventana.sidebar.establecer_indice(1)

    def _ejecutar_todo(self) -> None:
        especificaciones = listar()
        if not especificaciones:
            mostrar_toast(self, "No hay automatizaciones registradas para ejecutar.", "error")
            return
        for spec in especificaciones:
            self.scheduler.ejecutar_ahora(spec)
        mostrar_toast(self, f"Ejecución iniciada: {len(especificaciones)} automatización(es).", "info")

    def _reintentar(self, nombre: str) -> None:
        try:
            spec = obtener(nombre)
        except KeyError:
            mostrar_toast(self, f"No encontré la automatización '{nombre}'.", "error")
            return

        worker = AutomationWorker(self.runner, spec)
        worker.finalizado.connect(lambda resultado: self._al_reintentar_terminado(nombre, resultado, worker))
        self._workers.append(worker)
        worker.start()
        mostrar_toast(self, f"Reintentando {nombre}…", "info")

    def _al_reintentar_terminado(self, nombre: str, resultado, worker: AutomationWorker) -> None:
        if worker in self._workers:
            self._workers.remove(worker)
        tipo = "exito" if resultado.success else "error"
        texto = f"{nombre}: completado" if resultado.success else f"{nombre}: falló — {resultado.message}"
        mostrar_toast(self, texto, tipo)
        self.refrescar()
