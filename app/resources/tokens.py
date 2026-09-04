"""Fuente única de verdad visual de LaAutomate.

La interfaz usa una estética de consola moderna: fondos grafito, superficies
elevadas y acentos luminosos. Los colores semánticos siguen viviendo aquí
para que una vista nunca tenga que inventar un hexadecimal propio.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Colores:
    papel: str = "#070B10"
    # La sidebar va un punto mas honda que el lienzo para separarla sin
    # dibujar un borde. Estaba escrita a mano dentro del QSS: era uno de
    # los dos unicos colores de la interfaz que no salian de aqui, justo
    # lo que este archivo existe para evitar.
    papel_hondo: str = "#060A0F"
    reticula: str = "#111923"
    tarjeta: str = "#0C121A"
    tarjeta_elevada: str = "#101925"
    borde: str = "#1C2A3A"
    borde_fuerte: str = "#2D4056"
    tinta: str = "#F3F7FC"
    grafito: str = "#91A4BC"
    grafito_claro: str = "#5D718A"
    acento: str = "#00E887"
    # Hover del boton primario: el acento un paso mas apagado. Tambien
    # estaba escrito a mano en el QSS.
    acento_hover: str = "#00C978"
    acento_suave: str = "#06271C"
    cian: str = "#22D3EE"
    cian_suave: str = "#08242C"
    violeta: str = "#9B7CFF"
    violeta_suave: str = "#1C1731"
    oxido: str = "#FF6577"
    oxido_suave: str = "#2B1119"
    musgo: str = "#00E887"
    musgo_suave: str = "#06271C"
    ocre: str = "#FFB020"
    ocre_suave: str = "#2B210C"
    # Tinte de fila para una ejecucion fallida en una tabla. Mas claro
    # que oxido_suave (que es fondo de badge, sobre poca superficie):
    # a lo ancho de una fila entera ese tono ya lee como bloque rojo y
    # compite con el texto en vez de solo senalar donde mirar.
    fila_error: str = "#160E14"


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
    control: int = 8
    tarjeta: int = 12


@dataclass(frozen=True)
class Tipografia:
    familia_ui: str = "Inter, 'Segoe UI', system-ui, sans-serif"
    familia_mono: str = "'IBM Plex Mono', 'Cascadia Code', Consolas, monospace"
    # 6 tamanos maximo, en px
    t_caption: int = 11
    t_small: int = 12
    t_body: int = 13
    t_body_lg: int = 16
    t_h2: int = 20
    t_h1: int = 26
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
    background-color: {c.papel_hondo};
    border-right: 1px solid {c.borde};
}}
QLabel#marcaIcono {{
    background-color: {c.acento_suave};
    border: 1px solid {c.acento};
    border-radius: 7px;
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
    background-color: {c.tarjeta_elevada};
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
QLabel#pageEyebrow {{
    color: {c.cian};
    font-family: {t.familia_mono};
    font-size: {t.t_caption}px;
    font-weight: {t.peso_semibold};
    letter-spacing: 0.12em;
}}
QFrame#tarjetaKpi {{
    background-color: {c.tarjeta};
    border: 1px solid {c.borde};
    border-radius: {r.tarjeta}px;
}}
QFrame#tarjetaKpi:hover {{
    background-color: {c.tarjeta_elevada};
    border-color: {c.borde_fuerte};
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
    background-color: {c.tarjeta_elevada};
    border: 1px solid {c.borde};
    border-radius: {r.control}px;
    padding: 0 {e.md}px;
    min-height: {d.alto_control}px;
    font-weight: {t.peso_medium};
    color: {c.tinta};
}}
QPushButton:hover {{
    background-color: {c.borde};
    border-color: {c.borde_fuerte};
}}
QPushButton:pressed {{
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
    background-color: {c.acento_hover};
    border-color: {c.acento_hover};
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
QLineEdit, QPlainTextEdit, QTextEdit, QTextBrowser, QComboBox, QSpinBox {{
    background-color: {c.tarjeta};
    border: 1px solid {c.borde};
    border-radius: {r.control}px;
    padding: {e.xs}px {e.sm}px;
    selection-background-color: {c.acento_suave};
    selection-color: {c.acento};
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QTextBrowser:focus, QComboBox:focus {{
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
QLineEdit::placeholder, QPlainTextEdit::placeholder {{
    color: {c.grafito_claro};
}}
/* OJO: aqui NO se estilan ::drop-down ni ::down-arrow, y es a proposito.
   En cuanto la hoja de estilos define QComboBox::drop-down -- aunque solo
   sea `border: none` -- Qt deja de dibujar la flecha nativa y el control
   queda visualmente identico a una caja de texto: no hay forma de saber
   que se puede desplegar. Y con el combo en modo editable el problema es
   peor, porque hacer clic en el texto solo pone el cursor; la lista solo
   se abre desde la flecha que no estaba.
   El truco CSS del triangulo (width/height 0 + borders) en ::down-arrow
   tampoco vale: Qt no lo interpreta como CSS y pinta la caja del borde,
   un rectangulo gris. Comprobado con renders de las tres variantes.
   Sin esas dos reglas Qt dibuja su triangulo, que se lee bien sobre el
   fondo oscuro. */
QComboBox {{
    min-height: {d.alto_control}px;
    /* hueco a la derecha para que el texto no se meta debajo de la flecha */
    padding: 0 26px 0 {e.sm}px;
}}
QComboBox:hover {{
    border-color: {c.borde_fuerte};
}}
QComboBox QAbstractItemView {{
    background-color: {c.tarjeta_elevada};
    border: 1px solid {c.borde_fuerte};
    border-radius: {r.control}px;
    color: {c.tinta};
    padding: {e.xs}px;
    outline: none;
    selection-background-color: {c.acento_suave};
    selection-color: {c.acento};
}}
/* Con 40 modelos en la lista, unas filas apretadas se leen fatal. */
QComboBox QAbstractItemView::item {{
    min-height: 26px;
    padding: 0 {e.sm}px;
    border-radius: 4px;
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
    background-color: {c.tarjeta_elevada};
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
    background-color: {c.tarjeta_elevada};
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
    background-color: {c.tarjeta_elevada};
    color: {c.tinta};
    border: 1px solid {c.borde_fuerte};
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
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {c.borde_fuerte};
    border-radius: 5px;
    min-width: 24px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ---------- Asistente IA ---------- */
QFrame#panelContexto {{
    background-color: {c.tarjeta};
    border: 1px solid {c.borde};
    border-radius: {r.tarjeta}px;
}}
QFrame#burbujaUsuario {{
    background-color: {c.acento_suave};
    border: 1px solid {c.acento};
    border-radius: {r.tarjeta}px;
}}
QFrame#burbujaIA {{
    background-color: {c.tarjeta_elevada};
    border: 1px solid {c.borde};
    border-radius: {r.tarjeta}px;
}}
QLabel#rolUsuario {{
    color: {c.acento};
    font-size: {t.t_caption}px;
    font-weight: {t.peso_semibold};
}}
QLabel#rolIA {{
    color: {c.cian};
    font-size: {t.t_caption}px;
    font-weight: {t.peso_semibold};
}}
QLabel#chipArchivo {{
    color: {c.cian};
    background-color: {c.cian_suave};
    border: 1px solid {c.borde_fuerte};
    border-radius: {r.control}px;
    padding: 5px 8px;
    font-size: {t.t_caption}px;
}}
QLabel#estadoIA {{
    color: {c.ocre};
    font-size: {t.t_caption}px;
    font-weight: {t.peso_semibold};
}}
QSplitter::handle {{
    background-color: {c.borde};
}}
QSplitter::handle:horizontal {{
    width: 1px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QLabel {{
    background: transparent;
}}
"""
