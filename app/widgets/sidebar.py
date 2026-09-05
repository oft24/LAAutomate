"""Barra lateral agrupada (Operación / Sistema), con iconos y estado
activo distinguible del hover -- reemplaza el QListWidget plano sin
agrupar ni iconos de la version anterior."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEasingCurve, QParallelAnimationGroup, QPropertyAnimation, QSize, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QToolButton, QVBoxLayout, QWidget
from app.i18n import QLabel, QPushButton, QToolButton

from app.resources.iconos import icono
from app.resources.tokens import COLORES, ESPACIADO
from core.config import NOMBRE_APP

# Iconos SVG de trazo (ver app/resources/iconos.py). Antes eran glifos
# sueltos dentro del propio texto del boton: se veian
# distinto segun la fuente que tuviera cada equipo y no podian tomar el
# color del estado activo por separado del texto.
# Cada item es (clave, icono, etiqueta). La CLAVE es como el resto de la
# app pide "llevame a esta vista": antes se usaba el indice numerico
# (establecer_indice(6) para la Boveda), asi que insertar una vista en
# medio -- como paso al agregar "Asistente IA" -- reordenaba en silencio
# todos los destinos existentes sin que nada fallara de forma visible.
# La clave tambien es lo que MainWindow usa para apilar las paginas en el
# mismo orden: sidebar y QStackedWidget no pueden desalinearse porque
# leen la misma lista.
_GRUPOS: list[tuple[str, list[tuple[str, str, str]]]] = [
    (
        "Operación",
        [
            ("panel", "panel", "Panel principal"),
            ("automatizaciones", "automatizaciones", "Automatizaciones"),
            ("grabadora", "grabadora", "Grabadora"),
            ("programador", "programador", "Programador"),
            ("asistente", "asistente", "Asistente IA"),
        ],
    ),
    (
        "Sistema",
        [
            ("registros", "registros", "Registros"),
            ("boveda", "boveda", "Bóveda de credenciales"),
            ("wiki", "wiki", "Wiki"),
        ],
    ),
]

CLAVES: tuple[str, ...] = tuple(clave for _grupo, items in _GRUPOS for clave, _i, _t in items)

TAMANO_ICONO = 16

ANCHO_EXPANDIDO = 224
ANCHO_COLAPSADO = 72
_RUTA_LOGO = Path(__file__).resolve().parent.parent / "resources" / "app_icon.png"


class Sidebar(QWidget):
    cambiar_vista = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("sidebar")
        self.setMinimumWidth(ANCHO_EXPANDIDO)
        self.setMaximumWidth(ANCHO_EXPANDIDO)
        self._colapsado = False
        self._animacion_ancho: QParallelAnimationGroup | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(ESPACIADO.sm, ESPACIADO.md, ESPACIADO.sm, ESPACIADO.lg)
        layout.setSpacing(2)

        # La marca queda libre; el control de colapso vive en el pie y no
        # compite por los 56 px disponibles cuando el menú está contraído.
        fila_marca = QHBoxLayout()
        fila_marca.setContentsMargins(ESPACIADO.sm, 0, 0, 0)
        fila_marca.setSpacing(ESPACIADO.xs)

        self._logo = QLabel()
        self._logo.setObjectName("marcaIcono")
        self._logo.setFixedSize(28, 28)
        self._logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if _RUTA_LOGO.exists():
            pixmap = QPixmap(str(_RUTA_LOGO)).scaled(
                24,
                24,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._logo.setPixmap(pixmap)
        fila_marca.addWidget(self._logo)

        self._marca = QLabel(NOMBRE_APP)
        self._marca.setObjectName("sidebarMarca")
        fila_marca.addWidget(self._marca)
        fila_marca.addStretch()

        boton_colapsar = QToolButton()
        boton_colapsar.setObjectName("sidebarToggle")
        boton_colapsar.setFixedSize(32, 32)
        boton_colapsar.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        boton_colapsar.setToolTip("Contraer menú")
        boton_colapsar.setAccessibleName("Contraer menú")
        boton_colapsar.setIconSize(QSize(14, 14))
        boton_colapsar.setIcon(icono("chevron_izq", COLORES.grafito, 14))
        boton_colapsar.clicked.connect(self._alternar_colapso)
        self._boton_colapsar = boton_colapsar

        layout.addLayout(fila_marca)
        layout.addSpacing(ESPACIADO.md)

        self._botones: list[QPushButton] = []
        self._items_planos: list[tuple[str, str]] = []
        self._etiquetas_grupo: list[QLabel] = []

        indice = 0
        for grupo, items in _GRUPOS:
            etiqueta_grupo = QLabel(grupo.upper())
            etiqueta_grupo.setObjectName("sidebarGrupo")
            layout.addWidget(etiqueta_grupo)
            self._etiquetas_grupo.append(etiqueta_grupo)

            for _clave, nombre_icono, texto in items:
                boton = QPushButton(self._texto_boton(texto))
                boton.setObjectName("navItem")
                boton.setCheckable(True)
                boton.setFixedHeight(44)
                boton.setFocusPolicy(Qt.FocusPolicy.TabFocus)
                boton.setProperty("compact", False)
                boton.setIconSize(QSize(TAMANO_ICONO, TAMANO_ICONO))
                idx_local = indice
                boton.clicked.connect(lambda _checked=False, i=idx_local: self._seleccionar(i))
                layout.addWidget(boton)
                self._botones.append(boton)
                self._items_planos.append((nombre_icono, texto))
                indice += 1
            layout.addSpacing(ESPACIADO.md)

        layout.addStretch()
        self._fila_control = QHBoxLayout()
        self._fila_control.addStretch()
        self._fila_control.addWidget(boton_colapsar)
        self._fila_control.addStretch()
        layout.addLayout(self._fila_control)
        self._seleccionar(0)

    def _texto_boton(self, texto: str) -> str:
        # colapsada el boton es solo el icono: el texto se va, no se corta
        return "" if self._colapsado else f"  {texto}"

    def _pintar_iconos(self) -> None:
        """El icono toma el color del estado del boton. QSS no puede
        recolorear un QIcon, asi que se vuelve a generar en cada cambio de
        seleccion -- es barato: iconos.icono() esta cacheado por
        (nombre, color, tamano)."""
        for boton, (nombre_icono, _texto) in zip(self._botones, self._items_planos):
            color = COLORES.acento if boton.isChecked() else COLORES.grafito
            boton.setIcon(icono(nombre_icono, color, TAMANO_ICONO))

    def _seleccionar(self, indice: int) -> None:
        for i, boton in enumerate(self._botones):
            boton.setChecked(i == indice)
        self._pintar_iconos()
        self.cambiar_vista.emit(indice)

    def establecer_indice(self, indice: int) -> None:
        self._seleccionar(indice)

    def establecer_vista(self, clave: str) -> None:
        """Navega a una vista por su CLAVE ("boveda", "grabadora"...).

        Es la forma en que el resto de la app debe pedir un salto de
        vista: con indices, agregar una entrada a la sidebar reordenaba
        en silencio todos los destinos existentes."""
        if clave not in CLAVES:
            raise KeyError(f"No existe la vista {clave!r}. Disponibles: {', '.join(CLAVES)}")
        self._seleccionar(CLAVES.index(clave))

    def _alternar_colapso(self) -> None:
        if self._animacion_ancho is not None:
            self._animacion_ancho.stop()
        self._colapsado = not self._colapsado
        destino = ANCHO_COLAPSADO if self._colapsado else ANCHO_EXPANDIDO
        self._boton_colapsar.setIcon(
            icono("chevron_der" if self._colapsado else "chevron_izq", COLORES.grafito, 14)
        )
        self._marca.setVisible(not self._colapsado)
        ayuda = "Expandir menú" if self._colapsado else "Contraer menú"
        self._boton_colapsar.setToolTip(ayuda)
        self._boton_colapsar.setAccessibleName(ayuda)
        for boton, (_nombre_icono, texto) in zip(self._botones, self._items_planos):
            boton.setProperty("compact", self._colapsado)
            boton.style().unpolish(boton)
            boton.style().polish(boton)
            boton.setText(self._texto_boton(texto))
            boton.setToolTip(texto if self._colapsado else "")
        for etiqueta in self._etiquetas_grupo:
            etiqueta.setVisible(not self._colapsado)

        grupo = QParallelAnimationGroup(self)
        for propiedad in (b"minimumWidth", b"maximumWidth"):
            animacion = QPropertyAnimation(self, propiedad, grupo)
            animacion.setDuration(220)
            animacion.setStartValue(self.width())
            animacion.setEndValue(destino)
            animacion.setEasingCurve(QEasingCurve.Type.OutCubic)
            grupo.addAnimation(animacion)
        self._animacion_ancho = grupo
        grupo.start()
