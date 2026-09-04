"""Widgets de la vista Grabadora: la franja de estado en vivo y la lista
de pasos capturados.

Antes todo el estado de una grabación cabía en un QLabel de una línea con
una frase distinta para cada caso. Eso obligaba a elegir QUÉ contar: si se
mostraban las revinculaciones, los clicks ignorados desaparecían del
mensaje. Y lo que se estaba capturando no se veía hasta detener, así que
un error (la ventana equivocada, el tecleo que no entra) sólo aparecía al
final, con la grabación ya perdida.

Aquí cada dato tiene su sitio fijo: la píldora dice si graba, el objetivo
dice qué ventana, y cada contador es un chip que sólo se tiñe cuando deja
de ser cero.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.resources.tokens import COLORES, ESPACIADO, RADIOS, TIPO

MAX_PASOS_VISIBLES = 200


class _Chip(QLabel):
    """Contador con forma de píldora. Neutro en cero, ocre en cuanto hay
    algo que mirar -- que es justo cuando el usuario necesita enterarse."""

    def __init__(self, etiqueta_singular: str, etiqueta_plural: str) -> None:
        super().__init__()
        self._singular = etiqueta_singular
        self._plural = etiqueta_plural
        self.setFixedHeight(24)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.establecer_valor(0)

    def establecer_valor(self, valor: int) -> None:
        etiqueta = self._singular if valor == 1 else self._plural
        self.setText(f"  {valor} {etiqueta}  ")
        if valor:
            self.setStyleSheet(
                f"background-color: {COLORES.ocre_suave}; color: {COLORES.ocre};"
                f" border: 1px solid {COLORES.ocre}; border-radius: 12px;"
                f" font-size: {TIPO.t_caption}px; font-weight: {TIPO.peso_semibold};"
            )
        else:
            self.setStyleSheet(
                f"background-color: {COLORES.papel}; color: {COLORES.grafito};"
                f" border: 1px solid {COLORES.borde}; border-radius: 12px;"
                f" font-size: {TIPO.t_caption}px; font-weight: {TIPO.peso_medium};"
            )


class EstadoGrabacion(QFrame):
    """Franja de estado en vivo. Se oculta cuando no hay grabación en
    curso: fuera de una grabación no hay nada que informar y una franja
    vacía sólo sería ruido encima del código generado."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("tarjeta")

        fila = QHBoxLayout(self)
        fila.setContentsMargins(ESPACIADO.lg, ESPACIADO.md, ESPACIADO.lg, ESPACIADO.md)
        fila.setSpacing(ESPACIADO.md)

        self._pildora = QLabel("GRABANDO")
        self._pildora.setFixedHeight(26)
        self._pildora.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._pildora.setStyleSheet(
            f"background-color: {COLORES.ocre}; color: {COLORES.tarjeta};"
            f" border-radius: 13px; padding: 0 11px;"
            f" font-size: {TIPO.t_caption}px; font-weight: {TIPO.peso_semibold};"
        )
        fila.addWidget(self._pildora)

        columna_objetivo = QVBoxLayout()
        columna_objetivo.setSpacing(1)
        self._etiqueta_objetivo = QLabel("Ventana objetivo")
        self._etiqueta_objetivo.setStyleSheet(
            f"color: {COLORES.grafito}; font-size: {TIPO.t_caption}px;"
        )
        columna_objetivo.addWidget(self._etiqueta_objetivo)
        self._objetivo = QLabel("—")
        self._objetivo.setStyleSheet(
            f"font-family: {TIPO.familia_mono}; font-size: {TIPO.t_small}px;"
            f" font-weight: {TIPO.peso_medium};"
        )
        columna_objetivo.addWidget(self._objetivo)
        fila.addLayout(columna_objetivo)

        fila.addStretch()

        self.chip_clicks = _Chip("click ignorado", "clicks ignorados")
        self.chip_teclas = _Chip("tecla ignorada", "teclas ignoradas")
        self.chip_revinculaciones = _Chip("revinculación", "revinculaciones")
        for chip in (self.chip_clicks, self.chip_teclas, self.chip_revinculaciones):
            fila.addWidget(chip)

    def _pintar_borde(self, hay_avisos: bool) -> None:
        color = COLORES.ocre if hay_avisos else COLORES.borde
        fondo = COLORES.ocre_suave if hay_avisos else COLORES.tarjeta
        self.setStyleSheet(
            f"QFrame#tarjeta {{ background-color: {fondo}; border: 1px solid {color};"
            f" border-radius: {RADIOS.tarjeta}px; }}"
        )

    def actualizar_escritorio(self, grabadora) -> None:
        """Toma los contadores de una GrabadoraEscritorio. Sólo LEE
        propiedades: nada de lo que se muestra aquí cambia la grabación."""
        titulo = grabadora.titulo_objetivo
        if titulo:
            self._objetivo.setText(titulo)
        elif grabadora.modo_ventana == "multiple":
            self._objetivo.setText("cualquier ventana — da tus clicks")
        else:
            self._objetivo.setText("da tu PRIMER click en la ventana que quieras grabar")

        self.chip_clicks.setVisible(True)
        self.chip_teclas.setVisible(True)
        self.chip_revinculaciones.setVisible(True)
        self.chip_clicks.establecer_valor(grabadora.clicks_ignorados)
        self.chip_teclas.establecer_valor(grabadora.teclas_ignoradas)
        self.chip_revinculaciones.establecer_valor(grabadora.ventanas_revinculadas)

        self._pintar_borde(
            bool(grabadora.clicks_ignorados or grabadora.teclas_ignoradas or grabadora.ventanas_revinculadas)
        )

    def actualizar_web(self, grabadora) -> None:
        """La grabadora web no tiene candado de ventana ni contadores de
        descarte: los chips no aplican y se ocultan en vez de mostrarse
        siempre en cero, que haría creer que sí se están vigilando."""
        self._etiqueta_objetivo.setText("Página")
        self._objetivo.setText(grabadora.url_actual or "abriendo el navegador…")
        for chip in (self.chip_clicks, self.chip_teclas, self.chip_revinculaciones):
            chip.setVisible(False)
        self._pintar_borde(False)

    def reiniciar(self) -> None:
        self._etiqueta_objetivo.setText("Ventana objetivo")
        self._objetivo.setText("—")
        for chip in (self.chip_clicks, self.chip_teclas, self.chip_revinculaciones):
            chip.establecer_valor(0)
        self._pintar_borde(False)


# ---------------------------------------------------------------------------
# Lista de pasos
# ---------------------------------------------------------------------------

# tipo de paso -> (que llamada va a salir en el .py, de donde sale el detalle)
_ETIQUETAS_ESCRITORIO = {
    "conectar": "conectar_por_titulo",
    "click": "click_por_texto",
    "click_coordenada": "click_en",
    "click_password": "click_en",
    "escribir": "escribir",
    "escribir_credencial": "escribir(self.credenciales.password)",
    "tecla_enter": 'atajo("{ENTER}")',
    "tecla_tab": 'atajo("{TAB}")',
    "tecla_navegacion": "atajo",
}

_ETIQUETAS_WEB = {
    "ir_a": "ir_a",
    "click": "click",
    "escribir": "escribir",
}


def describir_paso(paso: dict) -> tuple[str, str, bool]:
    """(llamada, detalle, es_sensible) de un paso capturado.

    `es_sensible` marca los pasos de credencial: se dibujan distinto para
    que se vea que ahí NO se guardó ningún valor -- si se vieran iguales
    que un `escribir` normal, alguien podría creer que su contraseña quedó
    escrita en el archivo."""
    tipo = paso.get("tipo", "?")

    if tipo == "conectar":
        modo = paso.get("modo")
        etiqueta = "conectar_por_clase" if modo == "clase" else "conectar_por_titulo"
        detalle = str(paso.get("valor", ""))
        if paso.get("tras_rebind"):
            detalle += "  ·  tras revinculación (espera 30 s)"
        return etiqueta, detalle, False

    if tipo == "click":
        detalle = str(paso.get("texto", ""))
        if paso.get("control_tipo"):
            detalle += f"  ·  {paso['control_tipo']}"
        if paso.get("found_index") is not None:
            detalle += f"  ·  coincidencia #{paso['found_index']}"
        return "click_por_texto", detalle, False

    if tipo in ("click_coordenada", "click_password"):
        detalle = f"{paso.get('x')}, {paso.get('y')}"
        if tipo == "click_password":
            return "click_en", detalle + "  ·  campo de contraseña", True
        if paso.get("control_tipo"):
            detalle += f"  ·  {paso['control_tipo']} sin texto"
        return "click_en", detalle, False

    if tipo == "escribir":
        return "escribir", str(paso.get("valor", "")), False

    if tipo == "escribir_credencial":
        return "escribir", "self.credenciales.password  ·  el valor nunca se capturó", True

    if tipo == "tecla_navegacion":
        veces = paso.get("veces", 1)
        tecla = paso.get("tecla", "")
        return "atajo", f"{{{tecla} {veces}}}" if veces > 1 else f"{{{tecla}}}", False

    if tipo == "ir_a":
        return "ir_a", str(paso.get("url", "")), False

    etiqueta = _ETIQUETAS_ESCRITORIO.get(tipo) or _ETIQUETAS_WEB.get(tipo) or tipo
    return etiqueta, "", False


class PasosGrabados(QWidget):
    """Lo capturado hasta ahora, en vivo. Se reconstruye sólo cuando la
    lista cambió de verdad -- el sondeo corre dos veces por segundo y
    rehacer los widgets en cada tick haría parpadear el scroll."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        self._area = QScrollArea()
        self._area.setWidgetResizable(True)
        self._area.setFrameShape(QFrame.Shape.NoFrame)
        self._contenido = QWidget()
        self._lista = QVBoxLayout(self._contenido)
        self._lista.setContentsMargins(ESPACIADO.xs, ESPACIADO.xs, ESPACIADO.xs, ESPACIADO.xs)
        self._lista.setSpacing(2)
        self._lista.addStretch()
        self._area.setWidget(self._contenido)
        raiz.addWidget(self._area)

        self._firma: tuple | None = None
        self.establecer_pasos([])

    @staticmethod
    def _firma_de(pasos: list[dict]) -> tuple:
        # el ultimo paso se compara entero porque la desambiguacion lo muta
        # DESPUES de agregarlo (le pone found_index, o lo degrada a
        # coordenada) sin cambiar el largo de la lista.
        ultimo = tuple(sorted(pasos[-1].items(), key=str)) if pasos else ()
        return (len(pasos), ultimo)

    def establecer_pasos(self, pasos: list[dict]) -> None:
        firma = self._firma_de(pasos)
        if firma == self._firma:
            return
        self._firma = firma

        while self._lista.count():
            item = self._lista.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not pasos:
            self._lista.addWidget(self._fila_vacia("Todavía no se ha capturado ningún paso."))
        else:
            visibles = pasos[-MAX_PASOS_VISIBLES:]
            omitidos = len(pasos) - len(visibles)
            if omitidos:
                self._lista.addWidget(self._fila_vacia(f"… {omitidos} paso(s) anteriores"))
            for numero, paso in enumerate(visibles, start=omitidos + 1):
                self._lista.addWidget(self._fila(numero, paso))
            self._lista.addWidget(self._fila_vacia("esperando tu siguiente click o tecla…"))

        self._lista.addStretch()
        barra = self._area.verticalScrollBar()
        barra.setValue(barra.maximum())

    @staticmethod
    def _fila_vacia(texto: str) -> QWidget:
        etiqueta = QLabel(texto)
        etiqueta.setStyleSheet(
            f"color: {COLORES.grafito_claro}; font-size: {TIPO.t_caption}px; padding: 7px 10px;"
        )
        return etiqueta

    @staticmethod
    def _fila(numero: int, paso: dict) -> QWidget:
        llamada, detalle, sensible = describir_paso(paso)

        marco = QFrame()
        fila = QHBoxLayout(marco)
        fila.setContentsMargins(ESPACIADO.sm, 6, ESPACIADO.sm, 6)
        fila.setSpacing(ESPACIADO.sm)

        indice = QLabel(str(numero))
        indice.setFixedWidth(22)
        indice.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        indice.setStyleSheet(
            f"color: {COLORES.grafito_claro}; font-family: {TIPO.familia_mono}; font-size: 11px;"
        )
        fila.addWidget(indice)

        columna = QVBoxLayout()
        columna.setSpacing(1)
        color_llamada = COLORES.acento if sensible else COLORES.tinta
        etiqueta_llamada = QLabel(llamada)
        etiqueta_llamada.setStyleSheet(
            f"color: {color_llamada}; font-family: {TIPO.familia_mono};"
            f" font-size: {TIPO.t_caption}px; font-weight: {TIPO.peso_medium};"
        )
        columna.addWidget(etiqueta_llamada)
        if detalle:
            etiqueta_detalle = QLabel(detalle)
            etiqueta_detalle.setStyleSheet(f"color: {COLORES.grafito_claro}; font-size: 11px;")
            etiqueta_detalle.setToolTip(detalle)
            columna.addWidget(etiqueta_detalle)
        fila.addLayout(columna)
        fila.addStretch()

        if sensible:
            marco.setStyleSheet(
                f"QFrame {{ background-color: {COLORES.acento_suave}; border-radius: {RADIOS.control}px; }}"
            )
        elif paso.get("tras_rebind"):
            marco.setStyleSheet(
                f"QFrame {{ background-color: {COLORES.ocre_suave}; border-radius: {RADIOS.control}px; }}"
            )
        return marco
