"""Chat multimodal para diseñar automatizaciones con Gemini."""
from __future__ import annotations

import ast
import importlib
import re
import sys
import threading
import time
from uuid import uuid4
from pathlib import Path

from PySide6.QtCore import QThread, QTimer, Qt, Signal, QSize, QTemporaryDir
from PySide6.QtGui import QIcon, QPixmap, QImage
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.resources.tokens import COLORES, ESPACIADO, TIPO
from app.widgets.page_header import PageHeader
from app.widgets.code_editor import CodeEditor
from app.widgets.chat_text import ChatText
from app.widgets.python_highlighter import PythonHighlighter
from core.config import BASE_DIR, LOGS_DIR, var
from core.gemini_client import (
    MODELO_POR_DEFECTO,
    GeminiClient,
    RespuestaGemini,
    construir_contexto_proyecto,
    eliminar_api_key,
    es_modelo_de_texto,
    extraer_codigo_python,
    guardar_api_key,
    listar_modelos,
    modelo_por_defecto,
    ordenar_para_elegir,
    tiene_api_key,
    validar_capturas,
)
from engine.almacen import listar_en_disco
from engine.diagnostico import contexto_de_fallo, prompt_de_correccion
from engine.registry import errores_de_descubrimiento, listar

_NOMBRE_SEGURO = re.compile(r"[^a-z0-9_]+")


class _EntradaChat(QPlainTextEdit):
    imagenPegada = Signal(QImage)

    def insertFromMimeData(self, fuente):
        if self.isReadOnly():
            return
        if fuente.hasImage():
            self.imagenPegada.emit(QImage(fuente.imageData()))
        else:
            super().insertFromMimeData(fuente)


class _CapturasWorker(QThread):
    listo = Signal(object)
    error = Signal(str)

    def __init__(self, rutas, parent=None, imagen=None):
        super().__init__(parent)
        self.rutas = rutas
        self.imagen = imagen

    def run(self):
        try:
            if self.imagen is not None:
                if not self.imagen.save(str(self.rutas[-1]), "PNG"):
                    raise ValueError("No se pudo preparar la imagen del portapapeles.")
            datos = validar_capturas(self.rutas)
            miniaturas = {}
            for ruta, (_, contenido) in zip(self.rutas, datos):
                imagen = QImage.fromData(contenido)
                if imagen.isNull():
                    raise ValueError(f"No se pudo mostrar {ruta.name}.")
                miniaturas[str(ruta)] = imagen.scaled(
                    64, 44, Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            self.listo.emit((self.rutas, miniaturas))
        except Exception as exc:
            if self.imagen is not None:
                self.rutas[-1].unlink(missing_ok=True)
            self.error.emit(str(exc))
_NOMBRE_EN_DECORADOR = re.compile(
    r"(@registrar\s*\(\s*nombre\s*=\s*)([\"'])(.*?)(\2)", re.DOTALL
)
_IMPORTACIONES_PERMITIDAS = {
    "__future__",
    "collections",
    "core",
    "csv",
    "datetime",
    "decimal",
    "engine",
    "itertools",
    "json",
    "math",
    "pathlib",
    "re",
    "selenium",
    "time",
    "typing",
}


def normalizar_nombre(texto: str) -> str:
    nombre = _NOMBRE_SEGURO.sub("_", texto.strip().lower()).strip("_")
    if nombre and nombre[0].isdigit():
        nombre = f"automatizacion_{nombre}"
    return nombre


def _es_literal_seguro(nodo: ast.AST | None) -> bool:
    if nodo is None or isinstance(nodo, ast.Constant):
        return True
    if isinstance(nodo, (ast.Tuple, ast.List, ast.Set)):
        return all(_es_literal_seguro(elemento) for elemento in nodo.elts)
    if isinstance(nodo, ast.Dict):
        return all(_es_literal_seguro(k) and _es_literal_seguro(v) for k, v in zip(nodo.keys, nodo.values))
    if isinstance(nodo, ast.UnaryOp) and isinstance(nodo.op, (ast.UAdd, ast.USub)):
        return _es_literal_seguro(nodo.operand)
    return False


def _validar_importacion_segura(arbol: ast.Module) -> None:
    futuro_anotaciones = False
    for nodo in arbol.body:
        if isinstance(nodo, ast.Import):
            raices = {alias.name.split(".", 1)[0] for alias in nodo.names}
            if not raices <= _IMPORTACIONES_PERMITIDAS:
                raise ValueError(f"Importación no permitida al cargar el borrador: {', '.join(sorted(raices))}")
            continue
        if isinstance(nodo, ast.ImportFrom):
            raiz = (nodo.module or "").split(".", 1)[0]
            if raiz not in _IMPORTACIONES_PERMITIDAS:
                raise ValueError(f"Importación no permitida al cargar el borrador: {raiz}")
            if nodo.module == "__future__" and any(alias.name == "annotations" for alias in nodo.names):
                futuro_anotaciones = True
            continue
        if isinstance(nodo, ast.Expr) and isinstance(nodo.value, ast.Constant) and isinstance(nodo.value.value, str):
            continue  # docstring de módulo
        if isinstance(nodo, (ast.Assign, ast.AnnAssign)):
            destinos = nodo.targets if isinstance(nodo, ast.Assign) else [nodo.target]
            if not all(isinstance(destino, ast.Name) for destino in destinos) or not _es_literal_seguro(nodo.value):
                raise ValueError("El borrador contiene código ejecutable a nivel de módulo.")
            continue
        if not isinstance(nodo, ast.ClassDef):
            raise ValueError("El borrador contiene código ejecutable a nivel de módulo.")

        if nodo.keywords or any(not isinstance(base, ast.Name) for base in nodo.bases):
            raise ValueError("La herencia o metaclase ejecutaría código al importar el borrador.")

        for decorador in nodo.decorator_list:
            if not (
                isinstance(decorador, ast.Call)
                and isinstance(decorador.func, ast.Name)
                and decorador.func.id == "registrar"
                and all(_es_literal_seguro(arg) for arg in decorador.args)
                and all(_es_literal_seguro(keyword.value) for keyword in decorador.keywords)
            ):
                raise ValueError("La clase solo puede usar el decorador @registrar(...).")
        for miembro in nodo.body:
            if isinstance(miembro, ast.Pass):
                continue
            if isinstance(miembro, ast.Expr) and isinstance(miembro.value, ast.Constant):
                continue
            if isinstance(miembro, (ast.Assign, ast.AnnAssign)):
                destinos = miembro.targets if isinstance(miembro, ast.Assign) else [miembro.target]
                if not all(isinstance(destino, ast.Name) for destino in destinos) or not _es_literal_seguro(miembro.value):
                    raise ValueError("La clase contiene una asignación que se ejecutaría al importarla.")
                continue
            if not isinstance(miembro, (ast.FunctionDef, ast.AsyncFunctionDef)):
                raise ValueError("La clase contiene código que se ejecutaría al importarla.")
            if miembro.decorator_list:
                raise ValueError("Los métodos del borrador no pueden llevar decoradores.")
            defaults = [*miembro.args.defaults, *miembro.args.kw_defaults]
            if not all(_es_literal_seguro(valor) for valor in defaults):
                raise ValueError("Un valor por defecto ejecutaría código al importar el borrador.")

    if not futuro_anotaciones:
        raise ValueError("El borrador debe comenzar con “from __future__ import annotations”.")


def preparar_codigo(codigo: str, nombre: str) -> str:
    """Valida sintaxis y fija el nombre del registry al nombre de carpeta."""
    nombre = normalizar_nombre(nombre)
    if not nombre:
        raise ValueError("Escribe un nombre con letras o números.")
    if not _NOMBRE_EN_DECORADOR.search(codigo):
        raise ValueError("El bloque no contiene @registrar(nombre=...).")
    codigo = _NOMBRE_EN_DECORADOR.sub(rf"\g<1>\g<2>{nombre}\g<4>", codigo, count=1)
    arbol = ast.parse(codigo)
    compile(arbol, "automation.py", "exec")
    _validar_importacion_segura(arbol)
    from engine.scheduler import Scheduler
    Scheduler.validar_disparador_codigo(codigo)
    clases = [n for n in arbol.body if isinstance(n, ast.ClassDef)]
    if not any(
        any(isinstance(base, ast.Name) and base.id == "BaseAutomation" for base in clase.bases)
        for clase in clases
    ):
        raise ValueError("El código no define una clase que herede de BaseAutomation.")
    return codigo.rstrip() + "\n"


class _ModelosWorker(QThread):
    """Pregunta a la cuenta que modelos tiene, fuera del hilo de la interfaz.

    Es una llamada de red: hacerla en el hilo de la GUI congela la ventana
    y Windows la pinta como "no responde".
    """

    listo = Signal(object)
    error = Signal(str)

    def run(self) -> None:
        try:
            modelos = listar_modelos()
            self.listo.emit((ordenar_para_elegir(modelos), modelo_por_defecto(modelos)))
        except Exception as exc:  # noqa: BLE001 - sin modelos se sigue con la lista de reserva
            self.error.emit(str(exc))


class _GeminiWorker(QThread):
    listo = Signal(object)
    error = Signal(str)

    def __init__(
        self,
        mensaje: str,
        historial: list[tuple[str, str]],
        capturas: list[Path],
        contexto: str,
        modelo: str,
    ) -> None:
        super().__init__()
        self.mensaje = mensaje
        self.historial = historial
        self.capturas = capturas
        self.contexto = contexto
        self.modelo = modelo
        self.cancelado = threading.Event()

    def cancelar(self):
        self.cancelado.set()

    def run(self) -> None:
        try:
            respuesta = GeminiClient(modelo=self.modelo, timeout=(10, 90), reintentos=0).generar(
                self.mensaje,
                historial=self.historial,
                capturas=self.capturas,
                contexto=self.contexto,
                cancelado=self.cancelado,
            )
        except Exception as exc:  # noqa: BLE001 - se traduce a un mensaje de UI
            self.error.emit(f"{type(exc).__name__}: {exc}")
            return
        self.listo.emit(respuesta)


class _Burbuja(QFrame):
    def __init__(self, rol: str, texto: str) -> None:
        super().__init__()
        es_usuario = rol == "user"
        self.setObjectName("burbujaUsuario" if es_usuario else "burbujaIA")
        self.setMinimumWidth(0)
        self.setMaximumWidth(860)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(ESPACIADO.md, ESPACIADO.sm, ESPACIADO.md, ESPACIADO.md)
        layout.setSpacing(5)

        etiqueta_rol = QLabel("TÚ" if es_usuario else "LA  /  GEMINI")
        etiqueta_rol.setObjectName("rolUsuario" if es_usuario else "rolIA")
        layout.addWidget(etiqueta_rol)

        cuerpo = ChatText(texto, markdown=not es_usuario)
        layout.addWidget(cuerpo)


class AssistantView(QWidget):
    def __init__(self, on_automatizacion_creada=None) -> None:
        super().__init__()
        self.on_automatizacion_creada = on_automatizacion_creada
        self._historial: list[tuple[str, str]] = []
        self._capturas: list[Path] = []
        self._ultima_respuesta = ""
        self._worker: _GeminiWorker | None = None
        self._worker_modelos: _ModelosWorker | None = None
        self._rotas: dict[str, str] = {}
        self._puntos = 0
        self._modelos_cargados = False

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(24, 24, 24, 24)
        raiz.setSpacing(ESPACIADO.md)
        raiz.addWidget(
            PageHeader(
                "Asistente IA",
                "Describe el flujo, adjunta capturas y obtén un automation.py listo para revisar",
            )
        )

        divisor = QSplitter(Qt.Orientation.Horizontal)
        divisor.setChildrenCollapsible(False)
        divisor.addWidget(self._construir_chat())
        divisor.addWidget(self._construir_contexto())
        divisor.setStretchFactor(0, 1)
        divisor.setStretchFactor(1, 0)
        divisor.setSizes([900, 310])
        raiz.addWidget(divisor, stretch=1)

        self._timer_pensando = QTimer(self)
        self._timer_pensando.setInterval(350)
        self._timer_pensando.timeout.connect(self._animar_estado)

        self._agregar_burbuja(
            "model",
            "Cuéntame qué quieres automatizar. Puedo usar capturas, la referencia real de acciones "
            "y el código de una automatización existente como contexto. No guardaré ni ejecutaré "
            "nada sin tu confirmación.",
        )
        self._agregar_sugerencias()
        self.refrescar_contexto()
        self._actualizar_estado_clave()

    def _construir_chat(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, ESPACIADO.lg, 0)
        layout.setSpacing(ESPACIADO.md)

        self._area = QScrollArea()
        self._area.setWidgetResizable(True)
        self._area.setFrameShape(QFrame.Shape.NoFrame)
        self._mensajes = QWidget()
        self._layout_mensajes = QVBoxLayout(self._mensajes)
        self._layout_mensajes.setContentsMargins(0, 0, ESPACIADO.sm, 0)
        self._layout_mensajes.setSpacing(ESPACIADO.md)
        self._layout_mensajes.addStretch()
        self._area.setWidget(self._mensajes)
        layout.addWidget(self._area, stretch=1)

        compositor = QFrame()
        compositor.setObjectName("tarjeta")
        v = QVBoxLayout(compositor)
        v.setContentsMargins(ESPACIADO.md, ESPACIADO.md, ESPACIADO.md, ESPACIADO.md)
        v.setSpacing(ESPACIADO.sm)
        self.entrada = _EntradaChat()
        self.entrada.imagenPegada.connect(self._pegar_imagen)
        self.entrada.setToolTip("Pega texto o imágenes con Ctrl+V. Puedes agregar varias capturas.")
        self.entrada.setPlaceholderText(
            "Ejemplo: inicia sesión, descarga el reporte visible en la captura y guárdalo en Excel…"
        )
        self.entrada.setMaximumHeight(112)
        v.addWidget(self.entrada)
        v.addWidget(self._etiqueta("Ctrl+V para pegar capturas · puedes agregar varias antes de enviar"))

        self.panel_resultado = QFrame()
        self.panel_resultado.setObjectName("tarjeta")
        resultado = QVBoxLayout(self.panel_resultado)
        resultado.addWidget(self._etiqueta("Resultado · revisa antes de crear"))
        self.codigo_resultado = CodeEditor(readOnly=True)
        self.codigo_resultado.setObjectName("editorCodigo")
        self.codigo_resultado.setMaximumHeight(145)
        self._resaltador_resultado = PythonHighlighter(self.codigo_resultado.document())
        resultado.addWidget(self.codigo_resultado)
        fila_resultado = QHBoxLayout()
        self.boton_copiar = QPushButton("Copiar código")
        self.boton_copiar.setEnabled(False)
        self.boton_copiar.clicked.connect(self._copiar_codigo)
        fila_resultado.addWidget(self.boton_copiar)
        self.boton_crear = QPushButton("Crear automatización")
        self.boton_crear.setEnabled(False)
        self.boton_crear.clicked.connect(self._crear_automatizacion)
        fila_resultado.addWidget(self.boton_crear)
        fila_resultado.addStretch()
        resultado.addLayout(fila_resultado)
        self.panel_resultado.hide()
        layout.addWidget(self.panel_resultado)
        fila = QHBoxLayout()
        self.estado = QLabel("")
        self.estado.setObjectName("estadoIA")
        self.estado.setWordWrap(True)
        v.addWidget(self.estado)
        fila.addStretch()
        self.boton_enviar = QPushButton("Generar con Gemini")
        self.boton_enviar.setObjectName("primario")
        self.boton_enviar.clicked.connect(self._enviar)
        self.boton_cancelar_chat = QPushButton("Cancelar generación")
        self.boton_cancelar_chat.setEnabled(False)
        self.boton_cancelar_chat.clicked.connect(self._cancelar_chat)
        fila.addWidget(self.boton_cancelar_chat)
        fila.addWidget(self.boton_enviar)
        v.addLayout(fila)
        layout.addWidget(compositor)
        return panel

    def _construir_contexto(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("panelContexto")
        panel.setMinimumWidth(250)
        v = QVBoxLayout(panel)
        v.setContentsMargins(ESPACIADO.lg, ESPACIADO.lg, ESPACIADO.lg, ESPACIADO.lg)
        v.setSpacing(ESPACIADO.sm)

        titulo = QLabel("CONTEXTO DE GENERACIÓN")
        titulo.setObjectName("subtituloSeccion")
        v.addWidget(titulo)

        self.estado_clave = QLabel()
        self.estado_clave.setWordWrap(True)
        v.addWidget(self.estado_clave)
        fila_clave = QHBoxLayout()
        boton_clave = QPushButton("Configurar clave")
        self.boton_clave = boton_clave
        boton_clave.clicked.connect(self._configurar_clave)
        fila_clave.addWidget(boton_clave)
        boton_olvidar = QPushButton("Olvidar")
        self.boton_olvidar = boton_olvidar
        boton_olvidar.setObjectName("peligro")
        boton_olvidar.clicked.connect(self._olvidar_clave)
        fila_clave.addWidget(boton_olvidar)
        v.addLayout(fila_clave)

        v.addWidget(self._etiqueta("Modelo"))
        self.combo_modelo = QComboBox()
        self.combo_modelo.setEditable(True)
        # Reserva mientras llega la lista real. Ya no se ofrecen
        # gemini-2.5-pro ni gemini-2.5-flash: siguen apareciendo en
        # /models pero contestan 404 "no longer available to new users"
        # en cuentas nuevas, asi que elegirlos era un error garantizado.
        modelos = [var("GEMINI_MODEL", MODELO_POR_DEFECTO), MODELO_POR_DEFECTO]
        self.combo_modelo.addItems(list(dict.fromkeys(m for m in modelos if m)))
        # Se distingue entre "lo eligio el usuario" y "es mi valor de
        # reserva": si no se distingue, la app conserva la reserva porque
        # tambien aparece en la lista viva y nunca llega a proponer el
        # modelo recomendado de la cuenta. `textEdited` y `activated` solo
        # se disparan por interaccion humana, no al rellenar la lista.
        self._modelo_manual = bool(var("GEMINI_MODEL", "").strip())
        self.combo_modelo.activated.connect(self._marcar_modelo_manual)
        self.combo_modelo.lineEdit().textEdited.connect(self._marcar_modelo_manual)
        v.addWidget(self.combo_modelo)
        self.boton_modelos = QPushButton("Actualizar modelos")
        self.boton_modelos.clicked.connect(lambda: self._cargar_modelos_disponibles(forzar=True))
        v.addWidget(self.boton_modelos)

        v.addWidget(self._etiqueta("Código de referencia"))
        self.combo_automatizacion = QComboBox()
        v.addWidget(self.combo_automatizacion)

        detalle_contexto = (
            "Siempre se incluyen arquitectura, acciones y lógica de la grabadora. "
            "El log solo se agrega al preparar un diagnóstico; revisa el mensaje y las capturas antes de enviarlos. No se lee .env ni la Bóveda como contexto."
        )
        nota = QLabel("Contexto del proyecto incluido · sin claves ni bóveda")
        nota.setToolTip(detalle_contexto)
        nota.setObjectName("tarjetaDescripcion")
        nota.setWordWrap(True)
        v.addWidget(nota)

        v.addSpacing(ESPACIADO.sm)
        v.addWidget(self._etiqueta("Capturas de este turno"))
        boton_adjuntar = QPushButton("Adjuntar capturas")
        self.boton_adjuntar = boton_adjuntar
        boton_adjuntar.clicked.connect(self._adjuntar_capturas)
        v.addWidget(boton_adjuntar)
        self.lista_capturas = QListWidget()
        self.lista_capturas.setIconSize(QSize(64, 44))
        self.lista_capturas.setMaximumHeight(135)
        v.addWidget(self.lista_capturas)
        self.resumen_capturas = QLabel("Sin capturas. Puedes describir el flujo solo con texto.")
        self.resumen_capturas.setWordWrap(True)
        v.addWidget(self.resumen_capturas)
        fila_capturas = QHBoxLayout()
        boton_limpiar = QPushButton("Limpiar todas")
        self.boton_limpiar = boton_limpiar
        boton_limpiar.setEnabled(False)
        boton_limpiar.clicked.connect(self._limpiar_capturas)
        fila_capturas.addWidget(boton_limpiar)
        self.boton_quitar = QPushButton("Quitar")
        self.boton_quitar.setToolTip("Quitar la captura seleccionada")
        self.boton_quitar.setEnabled(False)
        self.boton_quitar.clicked.connect(self._quitar_captura)
        self.lista_capturas.currentRowChanged.connect(
            lambda fila: self.boton_quitar.setEnabled(fila >= 0 and self._worker is None)
        )
        fila_capturas.addWidget(self.boton_quitar)
        v.addLayout(fila_capturas)
        v.addStretch()

        privacidad = QLabel("Las imágenes solo salen del equipo al presionar “Generar con Gemini”.")
        privacidad.setObjectName("chipArchivo")
        privacidad.setWordWrap(True)
        v.addWidget(privacidad)
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.Shape.NoFrame)
        area.setMinimumWidth(270)
        area.setMaximumWidth(320)
        area.setWidget(panel)
        return area

    @staticmethod
    def _etiqueta(texto: str) -> QLabel:
        etiqueta = QLabel(texto)
        etiqueta.setObjectName("subtituloSeccion")
        return etiqueta

    def refrescar_contexto(self) -> None:
        # Se lista lo que hay EN DISCO, no solo lo que el registry cargo
        # bien: una automatizacion que no compila no esta registrada, y es
        # justo la que mas necesita que el asistente la mire. Sale marcada
        # con un aviso para que se vea de un vistazo cual esta rota.
        actual = self.combo_automatizacion.currentData()
        self._rotas = errores_de_descubrimiento()
        registradas = {spec.nombre for spec in listar()}
        self.combo_automatizacion.clear()
        self.combo_automatizacion.addItem("Sin código adicional", None)
        for nombre in listar_en_disco():
            rota = nombre in self._rotas or nombre not in registradas
            self.combo_automatizacion.addItem(f"{nombre}  (no compila)" if rota else nombre, nombre)
        if actual:
            indice = self.combo_automatizacion.findData(actual)
            if indice >= 0:
                self.combo_automatizacion.setCurrentIndex(indice)

    def _agregar_burbuja(self, rol: str, texto: str) -> None:
        burbuja = _Burbuja(rol, texto)
        alineacion = Qt.AlignmentFlag.AlignRight if rol == "user" else Qt.AlignmentFlag.AlignLeft
        self._layout_mensajes.insertWidget(self._layout_mensajes.count() - 1, burbuja)
        QTimer.singleShot(0, lambda: self._area.verticalScrollBar().setValue(self._area.verticalScrollBar().maximum()))

    def _agregar_sugerencias(self) -> None:
        fila = QWidget()
        layout = QHBoxLayout(fila)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(ESPACIADO.sm)
        sugerencias = (
            ("Desde capturas", "Analiza las capturas adjuntas y crea una automatización completa para este flujo:"),
            ("Mejorar un flujo", "Revisa la automatización seleccionada y propón una versión más robusta que:"),
            ("Explicar un error", "Ayúdame a diagnosticar este error y después propón el cambio mínimo seguro:"),
        )
        for titulo, prompt in sugerencias:
            boton = QPushButton(titulo)
            if titulo == "Explicar un error":
                # Este chip pegaba una plantilla vacia y dejaba al usuario
                # buscando el traceback a mano en logs/. Ahora carga el log
                # real y adjunta la captura que el runner tomo en el
                # momento del fallo: es la diferencia entre "diagnostica
                # este error" y "diagnostica ESTE error".
                boton.setToolTip("Carga el log y la captura del último fallo de la automatización elegida.")
                boton.clicked.connect(self._preparar_correccion)
            else:
                boton.clicked.connect(
                    lambda _checked=False, texto=prompt: self._usar_sugerencia(texto)
                )
            layout.addWidget(boton)
        layout.addStretch()
        self._layout_mensajes.insertWidget(self._layout_mensajes.count() - 1, fila)
        self._sugerencias = fila

    def _usar_sugerencia(self, texto: str) -> None:
        if self.entrada.toPlainText().strip():
            self.entrada.setFocus()
            self.estado.setText("Conservé tu mensaje actual. Puedes editarlo antes de generar.")
            return
        self.entrada.setPlainText(texto)
        self.entrada.setFocus()

    def mostrar_reparacion(self, reparacion) -> None:
        """Cuenta en el chat una sesion de autocorreccion ya terminada.

        Se apoya en las burbujas y la lista de capturas que ya existen: la
        reparacion no necesita una pantalla propia, necesita quedar en el
        sitio donde el usuario ya conversa sobre su codigo. Las capturas de
        cada intento se adjuntan para poder mirarlas y seguir preguntando
        sobre ellas sin volver a buscarlas en logs/.
        """
        lineas = [f"**Autocorrección de «{reparacion.automatizacion}»**", "", reparacion.resumen()]

        for intento in reparacion.intentos:
            lineas += ["", f"— Intento {intento.numero} —", f"Falló con: {intento.error[:200]}"]
            if intento.acciones:
                ultimas = [l for l in intento.acciones.splitlines() if l.strip()][-4:]
                if ultimas:
                    lineas += ["Últimas acciones:"] + [f"  {l}" for l in ultimas]
            if intento.diagnostico:
                lineas.append(f"Diagnóstico: {intento.diagnostico}")
            for cambio in intento.cambios:
                lineas.append(f"  · {cambio}")
            if intento.motivo_descarte:
                lineas.append(f"No se aplicó: {intento.motivo_descarte}")
            if intento.practica:
                lineas.append(f"Práctica: {intento.practica}")

        if not reparacion.exito:
            lineas += [
                "",
                "Sigue fallando. El código quedó como lo dejó el último arreglo que sí cargó; "
                "revísalo en Automatizaciones antes de volver a ejecutarlo.",
            ]

        self._agregar_burbuja("model", "\n".join(lineas))

        # Las capturas de los intentos, adjuntas para poder preguntar sobre ellas.
        existentes = {str(r).lower() for r in self._capturas}
        for intento in reparacion.intentos:
            for captura in intento.capturas:
                if captura.exists() and str(captura).lower() not in existentes:
                    self._capturas.append(captura)
                    self.lista_capturas.addItem(captura.name)
                    existentes.add(str(captura).lower())

        self.refrescar_contexto()
        self._refrescar_capturas()
        self.estado.setText(
            f"Autocorrección de «{reparacion.automatizacion}»: "
            + ("reparada" if reparacion.reparada else "sin resolver")
        )

    def _preparar_correccion(self) -> None:
        """El chip «Explicar un error»: usa la automatización ya elegida."""
        nombre = self.combo_automatizacion.currentData()
        if not nombre:
            self.estado.setText("Elige primero una automatización en “Código de referencia”.")
            return
        self.preparar_correccion(nombre)

    def preparar_correccion(self, nombre: str) -> bool:
        """Deja el chat listo para corregir `nombre`. True si hay rastro.

        La llama el botón «Corregir código» de Automatizaciones. Selecciona
        la automatización en el combo para que el código también viaje como
        contexto: sin eso el modelo diagnostica un log a ciegas.
        """
        for i in range(self.combo_automatizacion.count()):
            if self.combo_automatizacion.itemData(i) == nombre:
                self.combo_automatizacion.setCurrentIndex(i)
                break

        log, captura = contexto_de_fallo(nombre, LOGS_DIR)
        causa = getattr(self, "_rotas", {}).get(nombre, "")
        self.entrada.setPlainText(prompt_de_correccion(nombre, log, causa))

        if captura is not None and str(captura).lower() not in {str(r).lower() for r in self._capturas}:
            self._capturas.append(captura)
            self.lista_capturas.addItem(captura.name)
        self._refrescar_capturas()

        if not log.strip() and not causa:
            self.estado.setText(f"Sin log de “{nombre}”: ejecútala para que falle y vuelve a pulsar.")
            return False
        if captura is None:
            self.estado.setText(
                f"Cargado el log de “{nombre}” (no hay captura del error). "
                "Revisa el mensaje y pulsa Enviar."
            )
        else:
            self.estado.setText(
                f"Cargado el log de “{nombre}” y su captura del error. "
                "Revisa el mensaje y pulsa Enviar."
            )
        return True

    def _cargar_modelos_disponibles(self, forzar: bool = False) -> None:
        """Reemplaza la lista de reserva por los modelos reales de la cuenta."""
        if not tiene_api_key() or self._worker_modelos is not None:
            return
        if self._worker is not None or (self._modelos_cargados and not forzar):
            return
        self.boton_modelos.setEnabled(False)
        self.boton_clave.setEnabled(False)
        self.boton_olvidar.setEnabled(False)
        self.boton_modelos.setText("Consultando modelos…")
        self._worker_modelos = _ModelosWorker()
        self._worker_modelos.listo.connect(self._al_llegar_modelos)
        self._worker_modelos.error.connect(self._al_fallar_modelos)
        self._worker_modelos.finished.connect(self._liberar_worker_modelos)
        self._worker_modelos.start()

    def _al_llegar_modelos(self, resultado) -> None:
        self._modelos_cargados = True
        modelos, preferido = resultado
        elegido = self.combo_modelo.currentText().strip()

        self.combo_modelo.clear()
        # Primero los que sirven para escribir codigo, del mas nuevo al mas
        # viejo; despues un separador y el resto (imagen, audio, agentes).
        # No se ocultan: alguien puede querer probar uno a mano, pero no
        # deben estorbar arriba.
        utiles = [m for m in modelos if es_modelo_de_texto(m.nombre)]
        otros = [m for m in modelos if not es_modelo_de_texto(m.nombre)]
        for modelo in utiles:
            self.combo_modelo.addItem(modelo.nombre)
        if otros:
            self.combo_modelo.insertSeparator(self.combo_modelo.count())
            for modelo in otros:
                self.combo_modelo.addItem(modelo.nombre)

        # Solo se conserva una eleccion REAL del usuario (o GEMINI_MODEL
        # del .env). El valor con el que arranca el desplegable es una
        # reserva mia, y conservarla significaba no usar nunca el modelo
        # recomendado de la cuenta.
        indice = self.combo_modelo.findText(elegido) if (self._modelo_manual and elegido) else -1
        if indice < 0:
            indice = max(0, self.combo_modelo.findText(preferido))
        self.combo_modelo.setCurrentIndex(indice)

        self.estado.setText(
            f"{len(utiles)} modelos de Gemini utilizables (de {len(modelos)} en tu cuenta). "
            f"Elegido: {self.combo_modelo.currentText()}."
        )

    def _marcar_modelo_manual(self, *_args) -> None:
        self._modelo_manual = True

    def _al_fallar_modelos(self, mensaje: str) -> None:
        """Sin esto la lista se quedaba con la reserva en silencio, que es
        indistinguible de "esta cuenta solo tiene un modelo"."""
        self.estado.setText(f"No pude leer los modelos de tu cuenta: {mensaje}")

    def _liberar_worker_modelos(self) -> None:
        if self._worker_modelos is not None:
            self._worker_modelos.deleteLater()
        self._worker_modelos = None
        self.boton_modelos.setText("Actualizar modelos")
        self.boton_modelos.setEnabled(self._worker is None)
        self.boton_clave.setEnabled(self._worker is None)
        self._actualizar_estado_clave()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.refrescar_contexto()
        self._cargar_modelos_disponibles()

    def _actualizar_estado_clave(self) -> None:
        if tiene_api_key():
            self.estado_clave.setText("● Gemini configurado")
            self.estado_clave.setStyleSheet(f"color: {COLORES.musgo}; font-weight: 600;")
        else:
            self.estado_clave.setText("● Falta configurar la API key")
            self.estado_clave.setStyleSheet(f"color: {COLORES.ocre}; font-weight: 600;")
        self.boton_olvidar.setEnabled(tiene_api_key() and self._worker is None and self._worker_modelos is None)

    def _configurar_clave(self) -> None:
        clave, aceptado = QInputDialog.getText(
            self,
            "Configurar Gemini",
            "API key (se guardará en el Administrador de credenciales de Windows):",
            QLineEdit.EchoMode.Password,
        )
        if not aceptado or not clave.strip():
            return
        try:
            guardar_api_key(clave)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo guardar", str(exc))
            return
        self._actualizar_estado_clave()
        self._modelos_cargados = False
        self._cargar_modelos_disponibles()

    def _olvidar_clave(self) -> None:
        if QMessageBox.question(self, "Olvidar clave", "¿Eliminar la clave de Gemini guardada en Windows?",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        try:
            eliminar_api_key()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo eliminar", str(exc))
            return
        self._actualizar_estado_clave()
        self._modelos_cargados = False
        self.estado.setText("Clave de Windows eliminada." + (
            " Sigue configurada una clave en GEMINI_API_KEY; elimínala del entorno para desconectar."
            if tiene_api_key() else " Configura una clave para volver a generar."
        ))

    def _adjuntar_capturas(self) -> None:
        if self._worker is not None or getattr(self, "_worker_capturas", None):
            return
        if getattr(self, "_dialogo_capturas", None):
            self._dialogo_capturas.raise_()
            return
        dialogo = QFileDialog(self, "Adjuntar capturas")
        # Evita extensiones del shell/OneDrive del selector nativo de Windows.
        dialogo.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        dialogo.setOption(QFileDialog.Option.DontUseCustomDirectoryIcons, True)
        dialogo.setFileMode(QFileDialog.FileMode.ExistingFiles)
        dialogo.setNameFilter("Imágenes (*.png *.jpg *.jpeg *.webp)")
        dialogo.setDirectory(str(BASE_DIR))
        dialogo.filesSelected.connect(self._cargar_capturas)
        dialogo.finished.connect(self._cerrar_selector_capturas)
        self._dialogo_capturas = dialogo
        dialogo.open()

    def _cerrar_selector_capturas(self, _resultado):
        dialogo = self._dialogo_capturas
        self._dialogo_capturas = None
        dialogo.deleteLater()

    def _pegar_imagen(self, imagen):
        if self._worker is not None:
            return
        if imagen.isNull() or imagen.width() * imagen.height() > 25_000_000:
            self.estado.setText("Imagen inválida o demasiado grande (máximo 25 megapíxeles).")
            return
        if getattr(self, "_worker_capturas", None):
            self.estado.setText("Espera a que termine la carga y vuelve a pegar la siguiente captura.")
            return
        if len(self._capturas) >= 10:
            self.estado.setText("Adjunta como máximo 10 capturas por turno.")
            return
        if not hasattr(self, "_temporales_capturas"):
            self._temporales_capturas = QTemporaryDir()
        if not self._temporales_capturas.isValid():
            self.estado.setText("No se pudo crear la carpeta temporal para la captura.")
            return
        ruta = Path(self._temporales_capturas.path()) / f"Pegada-{uuid4().hex[:8]}.png"
        self._cargar_capturas([str(ruta)], imagen=imagen)

    def _cargar_capturas(self, rutas, imagen=None):
        if not rutas or self._worker is not None or getattr(self, "_worker_capturas", None):
            return
        unicas = {str(r).lower(): r for r in self._capturas}
        for ruta in rutas:
            unicas.setdefault(str(Path(ruta)).lower(), Path(ruta))
        if len(unicas) > 10:
            self.estado.setText("Adjunta como máximo 10 capturas por turno.")
            return
        self.estado.setText("Validando capturas… No se envía nada a Gemini.")
        self._worker_capturas = _CapturasWorker(list(unicas.values()), self, imagen=imagen)
        for boton in (self.boton_adjuntar, self.boton_limpiar, self.boton_quitar, self.boton_enviar, self._sugerencias):
            boton.setEnabled(False)
        self._worker_capturas.listo.connect(self._capturas_listas)
        self._worker_capturas.error.connect(self.estado.setText)
        self._worker_capturas.finished.connect(self._liberar_capturas)
        self._worker_capturas.start()

    def _capturas_listas(self, resultado):
        self._capturas, self._miniaturas = resultado
        self.estado.setText("Capturas listas. Revisa su contenido antes de generar.")
        self._refrescar_capturas()

    def _liberar_capturas(self):
        self._worker_capturas.deleteLater()
        self._worker_capturas = None
        self.boton_adjuntar.setEnabled(self._worker is None)
        self.boton_enviar.setEnabled(self._worker is None)
        self._sugerencias.setEnabled(self._worker is None)
        self._refrescar_capturas()

    def _refrescar_capturas(self) -> None:
        self.lista_capturas.clear()
        for ruta in self._capturas:
            item = QListWidgetItem(ruta.name)
            imagen = getattr(self, "_miniaturas", {}).get(str(ruta))
            if imagen is not None:
                item.setIcon(QIcon(QPixmap.fromImage(imagen)))
            item.setToolTip(str(ruta))
            self.lista_capturas.addItem(item)
        cantidad = len(self._capturas)
        self.resumen_capturas.setText(f"{cantidad} captura(s) para el siguiente envío · máximo 12 MB"
                                     if cantidad else "Sin capturas. Puedes describir el flujo solo con texto.")
        libre = self._worker is None and getattr(self, "_worker_capturas", None) is None
        self.boton_limpiar.setEnabled(bool(cantidad) and libre)
        self.boton_quitar.setEnabled(self.lista_capturas.currentRow() >= 0 and libre)

    def _quitar_captura(self) -> None:
        indice = self.lista_capturas.currentRow()
        if self._worker is None and getattr(self, "_worker_capturas", None) is None and 0 <= indice < len(self._capturas):
            self._capturas.pop(indice)
            self._refrescar_capturas()

    def _limpiar_capturas(self) -> None:
        if getattr(self, "_worker_capturas", None) is not None:
            return
        self._miniaturas = {}
        self._capturas.clear()
        self.lista_capturas.clear()
        self._refrescar_capturas()

    def _enviar(self) -> None:
        if getattr(self, "_worker_capturas", None) is not None:
            self.estado.setText("Espera a que termine la carga de capturas.")
            return
        if self._worker_modelos is not None:
            self.estado.setText("Espera a que termine la consulta de modelos antes de generar.")
            return
        if self._worker is not None:
            return
        mensaje = self.entrada.toPlainText().strip()
        if not mensaje:
            self.estado.setText("Describe primero la automatización.")
            return
        if not tiene_api_key():
            QMessageBox.information(
                self,
                "Configura Gemini",
                "Guarda tu API key con el botón “Configurar clave”. No se mostrará ni se escribirá en el código.",
            )
            return

        try:
            # GeminiWorker valida de nuevo los archivos antes de enviarlos.
            # Nunca leer/decodificar imágenes en el hilo de la interfaz.
            contexto = construir_contexto_proyecto(self.combo_automatizacion.currentData())
            modelo = self.combo_modelo.currentText().strip()
            if not re.fullmatch(r"[A-Za-z0-9._-]+", modelo):
                raise ValueError("Selecciona un modelo válido.")
        except Exception as exc:
            self.estado.setText(f"No se pudo preparar el envío: {exc}")
            return

        nombres_capturas = ", ".join(ruta.name for ruta in self._capturas)
        visible = mensaje + (f"\n\nCapturas: {nombres_capturas}" if nombres_capturas else "")
        self._agregar_burbuja("user", visible)
        self.entrada.setReadOnly(True)
        self.boton_enviar.setEnabled(False)
        self.boton_crear.setEnabled(False)
        self.boton_copiar.setEnabled(False)
        self._puntos = 0
        self._timer_pensando.start()
        self.estado.setText(f"Generando con {modelo}…")
        self.boton_enviar.setText("Generando…")
        self._inicio_generacion = time.monotonic()
        self._generacion_cancelada = False
        self.boton_cancelar_chat.setEnabled(True)
        self.panel_resultado.hide()
        for widget in (self.combo_modelo, self.combo_automatizacion, self.boton_adjuntar,
                       self.boton_limpiar, self.boton_quitar, self.boton_clave, self.boton_olvidar,
                       self.boton_modelos, self._sugerencias):
            widget.setEnabled(False)

        self._worker = _GeminiWorker(
            mensaje,
            list(self._historial),
            list(self._capturas),
            contexto,
            self.combo_modelo.currentText().strip(),
        )
        self._worker.listo.connect(lambda respuesta: self._al_responder(mensaje, respuesta))
        self._worker.error.connect(self._al_error)
        self._worker.finished.connect(self._liberar_worker)
        self._worker.start()

    def _animar_estado(self) -> None:
        if getattr(self, "_generacion_cancelada", False):
            return
        self._puntos = (self._puntos + 1) % 4
        segundos = int(time.monotonic() - getattr(self, "_inicio_generacion", time.monotonic()))
        self.estado.setText(f"Esperando respuesta de Gemini · {segundos} s" + "." * self._puntos)

    def _cancelar_chat(self):
        if self._worker is None:
            return
        self._generacion_cancelada = True
        self._worker.cancelar()
        self._timer_pensando.stop()
        self.boton_cancelar_chat.setEnabled(False)
        self.estado.setText("Cancelando: se descartará la respuesta. La conexión en curso debe terminar o agotar su espera; tu mensaje y capturas se conservan.")

    def _al_responder(self, mensaje: str, respuesta: RespuestaGemini) -> None:
        if getattr(self, "_generacion_cancelada", False):
            self.estado.setText("Generación cancelada. Puedes editar y volver a enviar.")
            return
        self._timer_pensando.stop()
        self.estado.setText(f"Respuesta de {respuesta.modelo}")
        self._ultima_respuesta = respuesta.texto
        self.entrada.clear()
        self._historial.extend((("user", mensaje), ("model", respuesta.texto)))
        self._agregar_burbuja("model", respuesta.texto)
        hay_codigo = extraer_codigo_python(respuesta.texto) is not None
        self.boton_crear.setEnabled(hay_codigo)
        self.boton_copiar.setEnabled(hay_codigo)
        self.codigo_resultado.setPlainText(extraer_codigo_python(respuesta.texto) or "")
        self.panel_resultado.setVisible(hay_codigo)
        self._limpiar_capturas()

    def _al_error(self, mensaje: str) -> None:
        self._timer_pensando.stop()
        if getattr(self, "_generacion_cancelada", False):
            self.estado.setText("Generación cancelada. Mensaje y capturas conservados.")
            return
        self.estado.setText(f"No se pudo generar: {mensaje[:500]}")
        self.estado.setToolTip(mensaje)
        self._agregar_burbuja("model", f"No pude completar la solicitud.\n\n{mensaje}")

    def _liberar_worker(self) -> None:
        self.boton_cancelar_chat.setEnabled(False)
        if self._worker is not None:
            self._worker.deleteLater()
        self._worker = None
        self.boton_enviar.setEnabled(True)
        self.boton_enviar.setText("Generar con Gemini")
        self.entrada.setReadOnly(False)
        for widget in (self.combo_modelo, self.combo_automatizacion, self.boton_adjuntar,
                       self.boton_clave, self._sugerencias):
            widget.setEnabled(True)
        self.boton_modelos.setEnabled(self._worker_modelos is None)
        self._actualizar_estado_clave()
        self._refrescar_capturas()

    def _copiar_codigo(self) -> None:
        codigo = extraer_codigo_python(self._ultima_respuesta)
        if codigo:
            QApplication.clipboard().setText(codigo)
            self.estado.setText("Código copiado")

    def _crear_automatizacion(self) -> None:
        codigo = extraer_codigo_python(self._ultima_respuesta)
        if not codigo:
            return
        sugerido = "nueva_automatizacion"
        coincidencia = re.search(r"nombre\s*=\s*[\"']([^\"']+)", codigo)
        if coincidencia:
            sugerido = normalizar_nombre(coincidencia.group(1)) or sugerido
        nombre, aceptado = QInputDialog.getText(
            self,
            "Crear automatización",
            "Nombre de carpeta y registro:",
            text=sugerido,
        )
        if not aceptado:
            return
        nombre = normalizar_nombre(nombre)
        try:
            codigo = preparar_codigo(codigo, nombre)
        except (SyntaxError, ValueError) as exc:
            QMessageBox.warning(self, "Código no válido", str(exc))
            return

        carpeta = BASE_DIR / "automations" / nombre
        if carpeta.exists():
            QMessageBox.warning(
                self,
                "Ya existe",
                f"La automatización “{nombre}” ya existe. No se sobrescribió ningún archivo.",
            )
            return

        try:
            carpeta.mkdir(parents=True)
            (carpeta / "__init__.py").write_text("", encoding="utf-8")
            (carpeta / "automation.py").write_text(codigo, encoding="utf-8")
            importlib.invalidate_caches()
            nombre_modulo = f"automations.{nombre}.automation"
            sys.modules.pop(nombre_modulo, None)
            importlib.import_module(nombre_modulo)
        except Exception as exc:  # noqa: BLE001 - conserva el borrador para poder repararlo
            QMessageBox.critical(
                self,
                "Guardada con error",
                f"Se escribió el borrador, pero no se pudo cargar: {type(exc).__name__}: {exc}",
            )
            return

        self.estado.setText(f"“{nombre}” creada; revísala antes de ejecutar")
        self.refrescar_contexto()
        if self.on_automatizacion_creada:
            self.on_automatizacion_creada(nombre)
