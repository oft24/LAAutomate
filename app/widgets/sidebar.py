"""Barra lateral agrupada (Operación / Sistema), con iconos y estado
activo distinguible del hover -- reemplaza el QListWidget plano sin
agrupar ni iconos de la version anterior."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from app.resources.iconos import icono
from app.resources.tokens import COLORES, ESPACIADO
from core.config import MARCA_CORTA, NOMBRE_APP

# Iconos SVG de trazo (ver app/resources/iconos.py). Antes eran glifos
# sueltos (⌂ ⚙ ◉ ◷ ▤ ▣ ◈) dentro del propio texto del boton: se veian
# distinto segun la fuente que tuviera cada equipo y no podian tomar el
# color del estado activo por separado del texto.
_GRUPOS: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "Operación",
        [
            ("panel", "Panel principal"),
            ("automatizaciones", "Automatizaciones"),
            ("grabadora", "Grabadora"),
            ("programador", "Programador"),
        ],
    ),
    (
        "Sistema",
        [
            ("registros", "Registros"),
            ("boveda", "Bóveda de credenciales"),
            ("wiki", "Wiki"),
        ],
    ),
]

TAMANO_ICONO = 16

ANCHO_EXPANDIDO = 224
ANCHO_COLAPSADO = 56


class Sidebar(QWidget):
    cambiar_vista = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("sidebar")
        self.setFixedWidth(ANCHO_EXPANDIDO)
        self._colapsado = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(ESPACIADO.sm, ESPACIADO.md, ESPACIADO.sm, ESPACIADO.lg)
        layout.setSpacing(2)

        # La marca comparte fila con el boton de colapsar en vez de ocupar
        # una linea propia: la sidebar ya es angosta y el nombre de la app
        # no merece robarle altura a la navegacion.
        fila_marca = QHBoxLayout()
        fila_marca.setContentsMargins(ESPACIADO.sm, 0, 0, 0)
        fila_marca.setSpacing(ESPACIADO.xs)

        self._marca = QLabel(NOMBRE_APP)
        self._marca.setObjectName("sidebarMarca")
        fila_marca.addWidget(self._marca)
        fila_marca.addStretch()

        boton_colapsar = QPushButton()
        boton_colapsar.setObjectName("navItem")
        boton_colapsar.setFixedSize(28, 28)
        boton_colapsar.setIconSize(QSize(14, 14))
        boton_colapsar.setIcon(icono("chevron_izq", COLORES.grafito, 14))
        boton_colapsar.clicked.connect(self._alternar_colapso)
        self._boton_colapsar = boton_colapsar
        fila_marca.addWidget(boton_colapsar, alignment=Qt.AlignmentFlag.AlignVCenter)

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

            for nombre_icono, texto in items:
                boton = QPushButton(self._texto_boton(texto))
                boton.setObjectName("navItem")
                boton.setCheckable(True)
                boton.setFixedHeight(36)
                boton.setIconSize(QSize(TAMANO_ICONO, TAMANO_ICONO))
                idx_local = indice
                boton.clicked.connect(lambda _checked=False, i=idx_local: self._seleccionar(i))
                layout.addWidget(boton)
                self._botones.append(boton)
                self._items_planos.append((nombre_icono, texto))
                indice += 1
            layout.addSpacing(ESPACIADO.md)

        layout.addStretch()
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

    def _alternar_colapso(self) -> None:
        self._colapsado = not self._colapsado
        self.setFixedWidth(ANCHO_COLAPSADO if self._colapsado else ANCHO_EXPANDIDO)
        self._boton_colapsar.setIcon(
            icono("chevron_der" if self._colapsado else "chevron_izq", COLORES.grafito, 14)
        )
        # Colapsada no cabe el nombre completo: se muestran las iniciales,
        # nunca un nombre cortado a la mitad por el ancho del widget.
        self._marca.setText(MARCA_CORTA if self._colapsado else NOMBRE_APP)
        for boton, (_nombre_icono, texto) in zip(self._botones, self._items_planos):
            boton.setText(self._texto_boton(texto))
            boton.setToolTip(texto if self._colapsado else "")
        for etiqueta in self._etiquetas_grupo:
            etiqueta.setVisible(not self._colapsado)
