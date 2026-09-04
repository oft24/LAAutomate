"""Iconos de la interfaz: SVG de trazo dibujados aqui, no glifos de fuente.

Antes la sidebar usaba caracteres sueltos (⌂ ⚙ ◉ ◷ ▤ ▣ ◈). Se veian
distinto en cada equipo (dependen de la fuente que Windows tenga para ese
bloque Unicode), no se pueden recolorear con el estado activo del boton
--el color del texto los arrastra a todos-- y no escalan a un tamano
elegido. Un SVG de trazo se rasteriza al tamano exacto que se pide, en el
color exacto que se pide, y es el mismo dibujo en cualquier maquina.

Todos comparten reja de 16, trazo 1.4 y extremos redondeados para que se
lean como UN set y no como siete iconos de sitios distintos.
"""
from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QGuiApplication, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_TRAZOS: dict[str, str] = {
    "panel": '<path d="M2.5 6.8 8 2.5l5.5 4.3V13a.5.5 0 0 1-.5.5H3a.5.5 0 0 1-.5-.5z"/>'
    '<path d="M6.3 13.5V9.2h3.4v4.3"/>',
    "automatizaciones": '<path d="M6.2 2.6c-1.4 0-1.6.9-1.6 2.1v1.5c0 .9-.5 1.5-1.4 1.8.9.3 1.4.9 1.4 1.8v1.5'
    'c0 1.2.2 2.1 1.6 2.1"/>'
    '<path d="M9.8 2.6c1.4 0 1.6.9 1.6 2.1v1.5c0 .9.5 1.5 1.4 1.8-.9.3-1.4.9-1.4 1.8v1.5'
    'c0 1.2-.2 2.1-1.6 2.1"/>',
    "grabadora": '<circle cx="8" cy="8" r="5.6"/><circle cx="8" cy="8" r="2.2" fill="CURRENT" stroke="none"/>',
    "programador": '<circle cx="8" cy="8" r="5.8"/><path d="M8 4.6V8l2.4 1.4"/>',
    "registros": '<path d="M3.2 3.6h9.6M3.2 6.7h9.6M3.2 9.8h6.4M3.2 12.9h4.2"/>',
    "boveda": '<rect x="3.4" y="7" width="9.2" height="6.4" rx="1.4"/><path d="M5.8 7V5.4a2.2 2.2 0 0 1 4.4 0V7"/>',
    "wiki": '<path d="M2.8 3.2h3.4c1 0 1.8.8 1.8 1.8v8c0-.7-.6-1.3-1.3-1.3H2.8z"/>'
    '<path d="M13.2 3.2H9.8c-1 0-1.8.8-1.8 1.8v8c0-.7.6-1.3 1.3-1.3h3.9z"/>',
    "asistente": '<path d="M3.2 3.4h9.6v7.2H8l-2.8 2v-2H3.2z"/>'
    '<path d="M8 5.2v3.6M6.2 7h3.6"/>',
    "chevron_izq": '<path d="M9.8 3.5 5.3 8l4.5 4.5"/>',
    "chevron_der": '<path d="M6.2 3.5 10.7 8l-4.5 4.5"/>',
    "buscar": '<circle cx="7.2" cy="7.2" r="4.2"/><path d="M10.3 10.3 13.4 13.4"/>',
    "carpeta": '<path d="M2.6 12.4V4.2c0-.4.3-.7.7-.7h2.9l1.3 1.6h4.8c.4 0 .7.3.7.7v6.6c0 .4-.3.7-.7.7H3.3'
    'a.7.7 0 0 1-.7-.7z"/>',
}

_PLANTILLA = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" '
    'fill="none" stroke="{color}" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round">'
    "{trazos}</svg>"
)


def _factor_de_pantalla() -> float:
    """Se rasteriza al doble (o a lo que pida la pantalla) y se marca el
    devicePixelRatio: sin esto el icono sale borroso en un monitor con
    escalado, que es el caso normal en los equipos donde corre esto."""
    pantalla = QGuiApplication.primaryScreen()
    if pantalla is None:
        return 2.0
    return max(2.0, float(pantalla.devicePixelRatio()))


@lru_cache(maxsize=128)
def _pixmap(nombre: str, color: str, tamano: int, factor: float) -> QPixmap:
    trazos = _TRAZOS[nombre].replace("CURRENT", color)
    svg = _PLANTILLA.format(color=color, trazos=trazos)

    lado = int(round(tamano * factor))
    pixmap = QPixmap(lado, lado)
    pixmap.fill(Qt.GlobalColor.transparent)

    pintor = QPainter(pixmap)
    pintor.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    QSvgRenderer(QByteArray(svg.encode("utf-8"))).render(pintor)
    pintor.end()

    pixmap.setDevicePixelRatio(factor)
    return pixmap


def icono(nombre: str, color: str, tamano: int = 16) -> QIcon:
    """QIcon del trazo `nombre` en `color`. Cacheado por (nombre, color,
    tamano): la sidebar lo pide en cada cambio de vista."""
    return QIcon(_pixmap(nombre, color, tamano, _factor_de_pantalla()))


def nombres_disponibles() -> tuple[str, ...]:
    return tuple(_TRAZOS)
