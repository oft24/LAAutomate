"""Fuente unica de verdad del sistema de diseno (Direccion B — "Papel
milimetrado"). Nada de valores inventados en los componentes: todo color,
tamano y espacio sale de aqui. `construir_qss()` genera el QSS completo a
partir de estos mismos tokens -- un solo lugar donde cambiar la paleta."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Colores:
    papel: str = "#F6F6F3"
    reticula: str = "#E7E7E1"
    tarjeta: str = "#FFFFFF"
    borde: str = "#DDDCD5"
    borde_fuerte: str = "#C7C6BD"
    tinta: str = "#15181D"
    grafito: str = "#6B7280"
    grafito_claro: str = "#9CA3AF"
    acento: str = "#0F766E"
    acento_suave: str = "#E3F0EE"
    oxido: str = "#B4321F"
    oxido_suave: str = "#F7E3E0"
    musgo: str = "#3F8B52"
    musgo_suave: str = "#E4F1E6"
    ocre: str = "#C17817"
    ocre_suave: str = "#F8ECD9"
    # Tinte de fila para una ejecucion fallida en una tabla. Mas claro
    # que oxido_suave (que es fondo de badge, sobre poca superficie):
    # a lo ancho de una fila entera ese tono ya lee como bloque rojo y
    # compite con el texto en vez de solo senalar donde mirar.
    fila_error: str = "#FDF6F5"


@dataclass(frozen=True)
class Espaciado:
    xs: int = 4
    sm: int = 8
    md: int = 12
    lg: int = 16
    xl: int = 24
    xxl: int = 32
    xxxl: int = 48


@dataclass(frozen=True)
class Radios:
    control: int = 6
    tarjeta: int = 10


@dataclass(frozen=True)
class Tipografia:
    familia_ui: str = "Inter, 'Segoe UI', system-ui, sans-serif"
    familia_mono: str = "'IBM Plex Mono', 'Cascadia Code', Consolas, monospace"
    # 6 tamanos maximo, en px
    t_caption: int = 12
    t_small: int = 13
    t_body: int = 14
    t_body_lg: int = 16
    t_h2: int = 20
    t_h1: int = 28
    peso_regular: int = 400
    peso_medium: int = 500
    peso_semibold: int = 600


@dataclass(frozen=True)
class Densidad:
    alto_fila: int = 44
    alto_control: int = 36


COLORES = Colores()
ESPACIADO = Espaciado()
RADIOS = Radios()
TIPO = Tipografia()
DENSIDAD = Densidad()


def construir_qss() -> str:
    c, e, r, t, d = COLORES, ESPACIADO, RADIOS, TIPO, DENSIDAD
    return f"""
* {{
    font-family: {t.familia_ui};
    font-size: {t.t_body}px;
    color: {c.tinta};
    outline: none;
}}

QMainWindow, QWidget#fondoApp {{
    background-color: {c.papel};
}}

QWidget {{
    background-color: transparent;
}}

/* ---------- Sidebar ---------- */
QWidget#sidebar {{
    background-color: {c.tarjeta};
    border-right: 1px solid {c.borde};
}}
QLabel#sidebarMarca {{
    color: {c.tinta};
    font-size: {t.t_body_lg}px;
    font-weight: {t.peso_semibold};
    letter-spacing: -0.01em;
}}
QLabel#sidebarGrupo {{
    color: {c.grafito};
    font-size: {t.t_caption}px;
    font-weight: {t.peso_semibold};
    letter-spacing: 0.06em;
    padding: {e.sm}px {e.md}px 4px {e.md}px;
}}
QPushButton#navItem {{
    text-align: left;
    padding: {e.sm}px {e.md}px;
    border-radius: {r.control}px;
    border: none;
    background: transparent;
    color: {c.grafito};
    font-weight: {t.peso_medium};
    font-size: {t.t_body}px;
}}
QPushButton#navItem:hover {{
    background-color: {c.reticula};
    color: {c.tinta};
}}
QPushButton#navItem:checked {{
    background-color: {c.acento_suave};
    color: {c.acento};
    font-weight: {t.peso_semibold};
    border-left: 3px solid {c.acento};
    padding-left: {e.md - 3}px;
}}

/* ---------- Encabezado de pagina ---------- */
QLabel#pageTitle {{
    font-size: {t.t_h1}px;
    font-weight: {t.peso_semibold};
    color: {c.tinta};
}}
QLabel#pageSubtitle {{
    font-size: {t.t_body}px;
    color: {c.grafito};
}}

/* ---------- Subtitulos de seccion y texto de tarjeta ---------- */
/* Un solo lugar para el patron "etiqueta chica en mayusculas/semibold
   arriba de una lista o tabla" -- antes cada vista repetia el mismo
   setStyleSheet a mano (font-weight/tamano como numeros magicos). */
QLabel#subtituloSeccion {{
    color: {c.grafito};
    font-size: {t.t_caption}px;
    font-weight: {t.peso_semibold};
    letter-spacing: 0.02em;
}}
QLabel#tarjetaTitulo {{
    color: {c.tinta};
    font-size: {t.t_body_lg}px;
    font-weight: {t.peso_semibold};
}}
QLabel#tarjetaDescripcion {{
    color: {c.grafito};
    font-size: {t.t_caption}px;
}}

/* ---------- Tarjetas / KPI ---------- */
QFrame#tarjeta, QWidget#tarjeta {{
    background-color: {c.tarjeta};
    border: 1px solid {c.borde};
    border-radius: {r.tarjeta}px;
}}
QLabel#kpiValor {{
    font-size: {t.t_h1}px;
    font-weight: {t.peso_semibold};
    color: {c.tinta};
    font-family: {t.familia_mono};
}}
QLabel#kpiEtiqueta {{
    font-size: {t.t_caption}px;
    color: {c.grafito};
    font-weight: {t.peso_medium};
}}
QLabel#kpiDelta {{
    font-size: {t.t_caption}px;
    font-weight: {t.peso_semibold};
}}

/* ---------- Botones ---------- */
QPushButton {{
    background-color: {c.tarjeta};
    border: 1px solid {c.borde};
    border-radius: {r.control}px;
    padding: 0 {e.md}px;
    min-height: {d.alto_control}px;
    font-weight: {t.peso_medium};
    color: {c.tinta};
}}
QPushButton:hover {{
    background-color: {c.reticula};
}}
QPushButton:disabled {{
    color: {c.grafito_claro};
    background-color: {c.reticula};
}}
QPushButton#primario {{
    background-color: {c.acento};
    border-color: {c.acento};
    color: {c.tarjeta};
    font-weight: {t.peso_semibold};
}}
QPushButton#primario:hover {{
    background-color: #0C5F58;
}}
QPushButton#primario:disabled {{
    background-color: {c.grafito_claro};
    border-color: {c.grafito_claro};
}}
QPushButton#peligro {{
    background-color: {c.tarjeta};
    border-color: {c.oxido};
    color: {c.oxido};
}}
QPushButton#peligro:hover {{
    background-color: {c.oxido_suave};
}}
QPushButton#modoToggle {{
    background-color: {c.reticula};
    border-color: {c.borde};
    color: {c.grafito};
    font-weight: {t.peso_medium};
    min-height: {d.alto_control - 4}px;
}}
QPushButton#modoToggle:checked {{
    background-color: {c.acento};
    border-color: {c.acento};
    color: {c.tarjeta};
    font-weight: {t.peso_semibold};
}}
QPushButton#modoToggle:disabled {{
    color: {c.grafito_claro};
}}

/* ---------- Inputs ---------- */
QLineEdit, QPlainTextEdit, QTextEdit {{
    background-color: {c.tarjeta};
    border: 1px solid {c.borde};
    border-radius: {r.control}px;
    padding: {e.xs}px {e.sm}px;
    selection-background-color: {c.acento_suave};
    selection-color: {c.acento};
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{
    border: 1px solid {c.acento};
}}
QLineEdit {{
    min-height: {d.alto_control}px;
}}
QPlainTextEdit#editorCodigo, QPlainTextEdit#consola {{
    font-family: {t.familia_mono};
    font-size: {t.t_small}px;
    background-color: {c.tarjeta};
}}

/* ---------- Tabla ---------- */
QTableWidget {{
    background-color: {c.tarjeta};
    border: 1px solid {c.borde};
    border-radius: {r.tarjeta}px;
    gridline-color: {c.reticula};
    font-size: {t.t_body}px;
}}
QTableWidget::item {{
    padding: 0 {e.sm}px;
    border-bottom: 1px solid {c.reticula};
}}
QTableWidget::item:selected {{
    background-color: {c.acento_suave};
    color: {c.tinta};
}}
QHeaderView::section {{
    background-color: {c.tarjeta};
    color: {c.grafito};
    font-size: {t.t_caption}px;
    font-weight: {t.peso_semibold};
    letter-spacing: 0.04em;
    border: none;
    border-bottom: 1px solid {c.borde};
    padding: {e.sm}px;
}}

/* ---------- Lista (Automatizaciones, Programador) ---------- */
QListWidget {{
    background-color: {c.tarjeta};
    border: 1px solid {c.borde};
    border-radius: {r.tarjeta}px;
    font-size: {t.t_body}px;
    padding: {e.xs}px;
}}
QListWidget::item {{
    padding: {e.sm}px;
    border-radius: {r.control}px;
    min-height: {d.alto_fila - 16}px;
}}
QListWidget::item:selected {{
    background-color: {c.acento_suave};
    color: {c.acento};
    font-weight: {t.peso_semibold};
}}
QListWidget::item:hover:!selected {{
    background-color: {c.reticula};
}}

/* ---------- Checkbox ---------- */
QCheckBox {{
    spacing: {e.sm}px;
    color: {c.tinta};
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {c.borde_fuerte};
    border-radius: 4px;
    background: {c.tarjeta};
}}
QCheckBox::indicator:hover {{
    border-color: {c.acento};
}}
QCheckBox::indicator:checked {{
    background-color: {c.acento};
    border-color: {c.acento};
}}

/* ---------- Boton de icono (menus de fila, ej. "..." de la tabla) ---------- */
QToolButton {{
    border: none;
    border-radius: {r.control}px;
    background: transparent;
    color: {c.grafito};
}}
QToolButton:hover {{
    background-color: {c.reticula};
}}
QToolButton::menu-indicator {{
    image: none;
}}

/* ---------- Menus contextuales ---------- */
QMenu {{
    background-color: {c.tarjeta};
    border: 1px solid {c.borde};
    border-radius: {r.control}px;
    padding: {e.xs}px;
}}
QMenu::item {{
    padding: {e.xs}px {e.md}px;
    border-radius: {r.control}px;
    color: {c.tinta};
}}
QMenu::item:selected {{
    background-color: {c.acento_suave};
    color: {c.acento};
}}
QMenu::separator {{
    height: 1px;
    background: {c.borde};
    margin: {e.xs}px {e.sm}px;
}}

/* ---------- Tooltips ---------- */
QToolTip {{
    background-color: {c.tinta};
    color: {c.tarjeta};
    border: none;
    padding: {e.xs}px {e.sm}px;
    border-radius: {r.control}px;
}}

/* ---------- Dialogos nativos (QMessageBox) ---------- */
/* No reemplazamos el dialogo nativo por uno propio (ese es un cambio de
   arquitectura, no solo visual) pero al menos lo hacemos leer sus colores
   de la misma paleta en vez del gris de Windows por defecto. */
QMessageBox {{
    background-color: {c.tarjeta};
}}
QMessageBox QLabel {{
    color: {c.tinta};
    font-size: {t.t_body}px;
}}
QMessageBox QPushButton {{
    min-width: 88px;
}}

/* ---------- Scrollbars discretas ---------- */
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {c.borde_fuerte};
    border-radius: 5px;
    min-height: 24px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QLabel {{
    background: transparent;
}}
"""
