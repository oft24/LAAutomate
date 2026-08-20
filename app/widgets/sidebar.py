"""Barra lateral agrupada (Operación / Sistema), con iconos y estado
activo distinguible del hover -- reemplaza el QListWidget plano sin
agrupar ni iconos de la version anterior."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from app.resources.tokens import ESPACIADO
from core.config import MARCA_CORTA, NOMBRE_APP

# Simbolos monocromos (sin libreria de iconos externa) -- consistentes con
# la estetica de plano tecnico: cada uno es un glifo esquematico, no un
# dibujo a color.
_GRUPOS: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "Operación",
        [
            ("⌂", "Panel principal"),
            ("⚙", "Automatizaciones"),
            ("◉", "Grabadora"),
            ("◷", "Programador"),
        ],
    ),
    (
        "Sistema",
        [
            ("▤", "Registros"),
            ("▣", "Bóveda de credenciales"),
            ("◈", "Wiki"),
        ],
    ),
]

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

        boton_colapsar = QPushButton("⟨")
        boton_colapsar.setObjectName("navItem")
        boton_colapsar.setFixedSize(28, 28)
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

            for icono, texto in items:
                boton = QPushButton(self._texto_boton(icono, texto))
                boton.setObjectName("navItem")
                boton.setCheckable(True)
                boton.setFixedHeight(36)
                idx_local = indice
                boton.clicked.connect(lambda _checked=False, i=idx_local: self._seleccionar(i))
                layout.addWidget(boton)
                self._botones.append(boton)
                self._items_planos.append((icono, texto))
                indice += 1
            layout.addSpacing(ESPACIADO.md)

        layout.addStretch()
        self._seleccionar(0)

    def _texto_boton(self, icono: str, texto: str) -> str:
        return icono if self._colapsado else f"  {icono}    {texto}"

    def _seleccionar(self, indice: int) -> None:
        for i, boton in enumerate(self._botones):
            boton.setChecked(i == indice)
        self.cambiar_vista.emit(indice)

    def establecer_indice(self, indice: int) -> None:
        self._seleccionar(indice)

    def _alternar_colapso(self) -> None:
        self._colapsado = not self._colapsado
        self.setFixedWidth(ANCHO_COLAPSADO if self._colapsado else ANCHO_EXPANDIDO)
        self._boton_colapsar.setText("⟩" if self._colapsado else "⟨")
        # Colapsada no cabe el nombre completo: se muestran las iniciales,
        # nunca un nombre cortado a la mitad por el ancho del widget.
        self._marca.setText(MARCA_CORTA if self._colapsado else NOMBRE_APP)
        for boton, (icono, texto) in zip(self._botones, self._items_planos):
            boton.setText(self._texto_boton(icono, texto))
            boton.setToolTip(texto if self._colapsado else "")
        for etiqueta in self._etiquetas_grupo:
            etiqueta.setVisible(not self._colapsado)
