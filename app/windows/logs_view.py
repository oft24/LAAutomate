"""Vista Registros: la lista de archivos de logs/ a la izquierda y el
contenido del elegido a la derecha.

Antes esta vista cargaba SOLO el log mas reciente de logs/, sin forma de
elegir otro: para leer el de una automatizacion que habia fallado por la
mañana habia que salir de la app y abrir la carpeta a mano. La lista se
ordena por fecha (el mas reciente primero, que es lo que uno viene a ver)
y marca en oxido los archivos que traen ERROR, para encontrar el
interesante sin abrirlos uno por uno.
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from app.resources.tokens import COLORES, ESPACIADO
from app.widgets.empty_state import EmptyState
from app.widgets.page_header import PageHeader
from core.config import LOGS_DIR

# Tope de lectura para decidir si un log trae errores y para mostrarlo. Un
# log de una automatizacion que lleva meses corriendo puede pesar decenas
# de MB; cargarlo entero congelaria la vista y de todas formas lo que se
# viene a leer es el final.
MAX_CARACTERES = 400_000


class LogsView(QWidget):
    def __init__(self) -> None:
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        layout.addWidget(
            PageHeader(
                "Registros",
                "Un archivo por automatización y por grabadora — elige cuál quieres leer",
                acciones=[("Abrir carpeta", self._abrir_carpeta), ("Actualizar", self.refrescar)],
            )
        )

        self._contenedor = QWidget()
        self._pila = QStackedLayout(self._contenedor)

        # --- pagina con contenido: lista + consola ---
        pagina = QWidget()
        fila = QHBoxLayout(pagina)
        fila.setContentsMargins(0, 0, 0, 0)
        fila.setSpacing(ESPACIADO.md)

        columna_lista = QVBoxLayout()
        columna_lista.setSpacing(ESPACIADO.sm)
        columna_lista.addWidget(self._subtitulo("Archivos en logs/"))
        self.lista = QListWidget()
        self.lista.setFixedWidth(276)
        self.lista.currentRowChanged.connect(self._al_cambiar_seleccion)
        columna_lista.addWidget(self.lista, stretch=1)
        fila.addLayout(columna_lista)

        columna_texto = QVBoxLayout()
        columna_texto.setSpacing(ESPACIADO.sm)
        self.titulo_archivo = self._subtitulo("")
        columna_texto.addWidget(self.titulo_archivo)
        self.texto = QPlainTextEdit(readOnly=True)
        self.texto.setObjectName("consola")
        columna_texto.addWidget(self.texto, stretch=1)
        fila.addLayout(columna_texto, stretch=1)

        self._vacio = EmptyState(
            "Sin registros todavía",
            "Aquí vas a ver el log detallado en cuanto corras tu primera automatización.",
        )
        self._pila.addWidget(pagina)
        self._pila.addWidget(self._vacio)
        layout.addWidget(self._contenedor, stretch=1)

        self._rutas: list[Path] = []
        self.refrescar()

    @staticmethod
    def _subtitulo(texto: str) -> QLabel:
        etiqueta = QLabel(texto)
        etiqueta.setObjectName("subtituloSeccion")
        return etiqueta

    # ---------------------------------------------------------------- datos

    def refrescar(self) -> None:
        """Relee la carpeta conservando la selección por NOMBRE, no por
        índice: entre dos refrescos puede aparecer un log nuevo y correr
        todas las filas, y el usuario se quedaría leyendo otro archivo sin
        haber tocado nada."""
        seleccionado = self.archivo_seleccionado()

        try:
            self._rutas = sorted(
                LOGS_DIR.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True
            )
        except OSError:
            self._rutas = []

        if not self._rutas:
            self._pila.setCurrentWidget(self._vacio)
            return
        self._pila.setCurrentIndex(0)

        self.lista.blockSignals(True)
        self.lista.clear()
        for ruta in self._rutas:
            self.lista.addItem(self._item(ruta))
        self.lista.blockSignals(False)

        indice = 0
        if seleccionado is not None:
            nombres = [r.name for r in self._rutas]
            if seleccionado.name in nombres:
                indice = nombres.index(seleccionado.name)
        self.lista.setCurrentRow(indice)
        self._al_cambiar_seleccion(indice)

    def archivo_seleccionado(self) -> Path | None:
        fila = self.lista.currentRow()
        if 0 <= fila < len(self._rutas):
            return self._rutas[fila]
        return None

    def _item(self, ruta: Path) -> QListWidgetItem:
        try:
            info = ruta.stat()
            momento = datetime.fromtimestamp(info.st_mtime).strftime("%d/%m %H:%M")
            tamano = self._tamano_legible(info.st_size)
        except OSError:
            momento, tamano = "—", "—"

        item = QListWidgetItem(f"{ruta.name}\n{momento} · {tamano}")
        item.setToolTip(str(ruta))
        if self._tiene_errores(ruta):
            # Se MARCA el archivo, no se filtra: un log sin errores sigue
            # siendo el que alguien viene a leer para confirmar que sí
            # corrió. El color solo dice dónde mirar primero.
            item.setForeground(QColor(COLORES.oxido))
            fuente = item.font()
            fuente.setWeight(QFont.Weight.DemiBold)
            item.setFont(fuente)
        return item

    @staticmethod
    def _tamano_legible(bytes_: int) -> str:
        if bytes_ < 1024:
            return f"{bytes_} B"
        if bytes_ < 1024 * 1024:
            return f"{bytes_ / 1024:.0f} KB"
        return f"{bytes_ / (1024 * 1024):.1f} MB"

    @staticmethod
    def _tiene_errores(ruta: Path) -> bool:
        try:
            with ruta.open("r", encoding="utf-8", errors="ignore") as archivo:
                return any("ERROR" in linea or "CRITICAL" in linea for linea in archivo)
        except OSError:
            return False

    # ------------------------------------------------------------ contenido

    def _al_cambiar_seleccion(self, fila: int) -> None:
        if not (0 <= fila < len(self._rutas)):
            self.titulo_archivo.setText("")
            self.texto.setPlainText("")
            return

        ruta = self._rutas[fila]
        self.titulo_archivo.setText(ruta.name.upper())
        try:
            contenido = ruta.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            self.texto.setPlainText(f"No se pudo leer {ruta}: {type(exc).__name__}: {exc}")
            return

        if len(contenido) > MAX_CARACTERES:
            contenido = "[…recortado: se muestran las últimas líneas…]\n" + contenido[-MAX_CARACTERES:]
        self.texto.setPlainText(contenido)
        barra = self.texto.verticalScrollBar()
        barra.setValue(barra.maximum())

    # Nombre anterior del refresco, conservado porque otras partes de la app
    # (y las pruebas) pueden seguir llamandolo.
    def _cargar_ultimo_log(self) -> None:
        self.refrescar()

    @staticmethod
    def _abrir_carpeta() -> None:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        os.startfile(str(LOGS_DIR))  # noqa: S606 - abrir con el explorador de Windows
