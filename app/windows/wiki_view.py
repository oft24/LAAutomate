"""Vista de Wiki: catalogo de referencia de los metodos disponibles en
self.web/.excel/.http/.correo/.escritorio/.copiloto -- para no tener que
abrir el codigo fuente de cada modulo solo para recordar que existe
click_por_texto o abrir_copilot.

Contenido curado a mano desde las clases reales en engine/actions/ (no se
genera dinamicamente por introspeccion) para poder anotar cada metodo con
una descripcion breve en español en vez de solo su firma."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.resources.tokens import COLORES, ESPACIADO, TIPO
from app.widgets.page_header import PageHeader

_CATEGORIAS = [
    {
        "atributo": "self.web",
        "titulo": "Navegador (Selenium)",
        "descripcion": "Automatiza páginas web -- Chrome, con reserva automática a Edge si Chrome no está disponible.",
        "metodos": [
            ("ir_a(url)", "Navega el navegador a la URL indicada."),
            ("click(selector, by=By.CSS_SELECTOR)", "Espera a que el elemento sea clickeable y hace clic."),
            ("escribir(selector, texto, by=By.CSS_SELECTOR)", "Espera visibilidad del elemento, lo limpia y escribe el texto."),
            ("leer_texto(selector, by=By.CSS_SELECTOR)", "Espera visibilidad del elemento y devuelve su texto."),
            ("screenshot_error(nombre_automatizacion)", "Guarda una captura del error en logs/screenshots."),
            ("cerrar()", "Cierra el navegador si está abierto."),
        ],
    },
    {
        "atributo": "self.excel",
        "titulo": "Excel",
        "descripcion": "Lee y escribe archivos Excel; también expone la app COM para controlarla en vivo.",
        "metodos": [
            ("leer(ruta, hoja=0)", "Lee un Excel con pandas y devuelve las filas como diccionarios."),
            ("escribir(ruta, filas, hoja=\"Sheet1\")", "Escribe una lista de filas (diccionarios) a un archivo Excel."),
            ("com()", "Devuelve una instancia COM de Excel.Application para controlar el programa en vivo."),
        ],
    },
    {
        "atributo": "self.http",
        "titulo": "HTTP",
        "descripcion": "Llamadas a APIs REST con una sesión compartida y timeout configurado.",
        "metodos": [
            ("get(url, **kwargs)", "Hace un GET usando la sesión compartida."),
            ("post(url, **kwargs)", "Hace un POST usando la sesión compartida."),
            ("con_token(token)", "Agrega el header Authorization Bearer y devuelve self (encadenable)."),
        ],
    },
    {
        "atributo": "self.correo",
        "titulo": "Correo",
        "descripcion": "Envía y busca correos vía Outlook (COM) o SMTP.",
        "metodos": [
            ("enviar_outlook(para, asunto, cuerpo)", "Envía un correo usando Outlook vía COM."),
            (
                "buscar_outlook_por_remitente(remitente, desde, carpeta=...)",
                "Busca correos de un remitente desde una fecha, más recientes primero.",
            ),
            (
                "enviar_smtp(host, puerto, usuario, password, para, asunto, cuerpo)",
                "Envía un correo por SMTP con autenticación.",
            ),
        ],
    },
    {
        "atributo": "self.escritorio",
        "titulo": "Escritorio",
        "descripcion": "Controla apps de escritorio por clicks/teclado (UI Automation) -- sin API, como lo haría una persona.",
        "metodos": [
            (
                "iniciar_o_conectar(comando, titulo_regex, tiempo_espera=20)",
                "Conecta con una ventana ya abierta o, si no existe, lanza el comando y espera.",
            ),
            (
                "conectar_por_titulo(titulo_regex, tiempo_espera=10)",
                "Conecta SOLO con una ventana ya abierta -- no la lanza si no existe.",
            ),
            ("atajo(teclas)", "Envía un atajo de teclado a la ventana conectada, ej. atajo('^e') para Ctrl+E."),
            ("escribir(texto)", "Escribe texto en la ventana conectada."),
            ("esperar(segundos)", "Pausa la ejecución."),
            ("leer_items_lista(control_type=\"ListItem\")", "Lee el texto visible de los ítems de una lista/resultados."),
            (
                "click_por_texto(texto, control_type=None, found_index=None, pausa=0.08)",
                "Click en el control con ese texto visible. Si hay varios que hacen match, pasa "
                "control_type para acotar (ej. \"Button\") o found_index (0, 1, 2...) para elegir cuál "
                "-- útil cuando el mismo ícono se repite en la barra de tareas de cada monitor.",
            ),
            ("click_por_imagen(ruta_imagen, confianza=0.9)", "Busca una imagen en pantalla y hace click en su centro."),
            ("capturar_pantalla(nombre)", "Guarda una captura de pantalla completa en logs/screenshots."),
        ],
    },
    {
        "atributo": "self.copiloto",
        "titulo": "Copilot + Teams",
        "descripcion": "Automatiza Microsoft 365 Copilot y Microsoft Teams vía UI Automation -- sin API ni extensión de navegador.",
        "metodos": [
            ("abrir_copilot()", "Conecta con la ventana de Microsoft 365 Copilot ya abierta."),
            ("buscar_agente(nombre)", "Busca el enlace de un agente por su nombre visible."),
            ("clickear_agente(nombre)", "Abre un agente de Copilot por su nombre."),
            ("enviar_prompt(nombre_agente, texto)", "Escribe y envía un mensaje a un agente."),
            ("leer_tabla_de_respuesta()", "Lee la tabla de la respuesta directo del árbol de accesibilidad."),
            (
                "copiar_tabla_de_respuesta()",
                "Copia la tabla con el botón \"Copy\" real -- conserva el formato para pegarla en Teams.",
            ),
            (
                "esperar_tabla_de_respuesta(tiempo_maximo=60, intervalo=3)",
                "Espera (sondeando) a que aparezca una tabla en la respuesta.",
            ),
            (
                "esperar_y_copiar_tabla(tiempo_maximo=60, intervalo=3)",
                "Espera la tabla y la copia con el botón real en un solo paso.",
            ),
            ("copiar_respuesta_completa()", "Copia el texto completo de la respuesta con \"Copy Response\"."),
            ("abrir_teams()", "Conecta con la ventana de Microsoft Teams, confirmando el proceso real (ms-teams.exe)."),
            ("abrir_chat_propio(correo, nombre_en_lista)", "Abre un chat existente en la lista o lo busca por correo exacto."),
            (
                "pegar_y_enviar(titulo_esperado, contenido_para_escribir=None)",
                "Pega y envía SOLO si el título y el contenido pasan la verificación.",
            ),
        ],
    },
]

_COMO_FUNCIONA = [
    "Cada automatización es un archivo automation.py de verdad -- una clase Python que hereda de "
    "BaseAutomation, con un método ejecutar(). No hay diseñador visual ni JSON de configuración: es "
    "código normal que puedes leer, editar y depurar como cualquier otro.",
    "El decorador @registrar(nombre=..., disparador=...) sobre la clase es lo único que hace falta para "
    "que la app la descubra sola -- al arrancar, escanea la carpeta automations/ e importa todo lo que "
    "encuentra, sin que tengas que registrar nada a mano en ningún otro lado.",
    "Correrla manualmente (botón “Ejecutar”), programada (cron, desde el Programador) o disparada por "
    "correo/carpeta/webhook siempre pasa por el mismo motor: corre en un hilo aparte para no congelar la "
    "app, captura cualquier error con su traceback y una captura de pantalla, y guarda el resultado en el "
    "Historial (visible desde el Panel principal y Registros).",
    "La Grabadora (Web o Escritorio) no genera configuración: observa tus clics y tecleo reales y "
    "traduce cada paso a una llamada de self.web/.escritorio -- el resultado es un automation.py normal, "
    "editable como cualquier otro, no una caja negra.",
    "Las credenciales (self.credenciales.usuario/password) nunca viven escritas en el código: se "
    "guardan cifradas en el almacén de credenciales de Windows a través de la Bóveda, y se inyectan en "
    "tiempo de ejecución según el nombre de la automatización.",
]

_HERRAMIENTAS = [
    ("Python 3.11", "El motor y cada automatización son código Python puro y editable -- sin capas de configuración intermedias."),
    ("PySide6 (Qt)", "La interfaz de escritorio que estás viendo -- ventanas, tablas, formularios."),
    ("Selenium", "Automatiza el navegador (self.web) -- Chrome, con reserva automática a Edge."),
    (
        "pywinauto + pywin32",
        "Controla apps de escritorio (self.escritorio/.copiloto) vía UI Automation -- clics, teclado, "
        "identificar controles -- sin necesitar una API propia de esa app.",
    ),
    (
        "pynput",
        "Escucha global de mouse/teclado -- lo que usa la Grabadora de escritorio para grabar lo que "
        "haces, sin importar la app.",
    ),
    ("APScheduler", "Programa automatizaciones por cron/intervalos (el Programador)."),
    ("keyring", "Guarda usuario/contraseña cifrados en el almacén de credenciales de Windows (la Bóveda)."),
    ("pandas + openpyxl", "Lectura y escritura de archivos Excel (self.excel)."),
    ("SQLite", "Guarda el historial de cada ejecución -- sin necesitar un servidor de base de datos aparte."),
    ("PyInstaller", "Empaqueta todo esto en el .exe que instalaste, sin que necesites Python instalado para usarlo."),
]


class WikiView(QWidget):
    def __init__(self) -> None:
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(ESPACIADO.md)

        layout.addWidget(
            PageHeader(
                "Wiki",
                "Referencia de lo que puedes llamar desde self.<módulo> en cualquier automation.py",
            )
        )

        layout.addWidget(self._construir_tarjeta_parrafos("Cómo funciona la app", _COMO_FUNCIONA))
        layout.addWidget(
            self._construir_tarjeta_herramientas(
                "Herramientas que usamos",
                "Cada pieza tiene un trabajo específico -- ninguna es reemplazable por \"magia\", todas son "
                "librerías reales que puedes revisar en requirements.txt.",
                _HERRAMIENTAS,
            )
        )
        layout.addWidget(self._subtitulo_seccion("Referencia de acciones (self.<módulo>)"))

        self.campo_busqueda = QLineEdit()
        self.campo_busqueda.setPlaceholderText('Buscar método o palabra clave… (ej. "teams", "excel", "click")')
        self.campo_busqueda.textChanged.connect(self._filtrar)
        layout.addWidget(self.campo_busqueda)

        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.Shape.NoFrame)
        contenedor = QWidget()
        layout_tarjetas = QVBoxLayout(contenedor)
        layout_tarjetas.setSpacing(ESPACIADO.md)
        layout_tarjetas.setContentsMargins(0, 0, ESPACIADO.sm, 0)
        area.setWidget(contenedor)
        layout.addWidget(area, stretch=1)

        self._tarjetas: list[tuple[QFrame, list[tuple[QLabel, QLabel, str]]]] = []
        for categoria in _CATEGORIAS:
            tarjeta, filas = self._construir_tarjeta(categoria)
            layout_tarjetas.addWidget(tarjeta)
            self._tarjetas.append((tarjeta, filas))
        layout_tarjetas.addStretch()

    @staticmethod
    def _subtitulo_seccion(texto: str) -> QLabel:
        etiqueta = QLabel(texto)
        etiqueta.setObjectName("subtituloSeccion")
        return etiqueta

    @staticmethod
    def _estilo_metodo() -> str:
        return (
            f"font-family: {TIPO.familia_mono}; font-size: {TIPO.t_caption}px; "
            f"color: {COLORES.acento}; font-weight: {TIPO.peso_semibold};"
        )

    @staticmethod
    def _estilo_descripcion() -> str:
        return f"color: {COLORES.tinta}; font-size: {TIPO.t_caption}px;"

    def _construir_tarjeta_parrafos(self, titulo: str, parrafos: list[str]) -> QFrame:
        tarjeta = QFrame()
        tarjeta.setObjectName("tarjeta")
        v = QVBoxLayout(tarjeta)
        v.setContentsMargins(ESPACIADO.lg, ESPACIADO.lg, ESPACIADO.lg, ESPACIADO.lg)
        v.setSpacing(ESPACIADO.sm)

        encabezado = QLabel(titulo)
        encabezado.setObjectName("tarjetaTitulo")
        v.addWidget(encabezado)

        for parrafo in parrafos:
            etiqueta = QLabel(parrafo)
            etiqueta.setWordWrap(True)
            etiqueta.setStyleSheet(self._estilo_descripcion())
            v.addWidget(etiqueta)

        return tarjeta

    def _construir_tarjeta_herramientas(
        self, titulo: str, descripcion: str, herramientas: list[tuple[str, str]]
    ) -> QFrame:
        tarjeta = QFrame()
        tarjeta.setObjectName("tarjeta")
        v = QVBoxLayout(tarjeta)
        v.setContentsMargins(ESPACIADO.lg, ESPACIADO.lg, ESPACIADO.lg, ESPACIADO.lg)
        v.setSpacing(ESPACIADO.sm)

        encabezado = QLabel(titulo)
        encabezado.setObjectName("tarjetaTitulo")
        v.addWidget(encabezado)

        subtitulo = QLabel(descripcion)
        subtitulo.setWordWrap(True)
        subtitulo.setObjectName("tarjetaDescripcion")
        v.addWidget(subtitulo)

        rejilla = QGridLayout()
        rejilla.setHorizontalSpacing(ESPACIADO.md)
        rejilla.setVerticalSpacing(ESPACIADO.xs)
        rejilla.setColumnStretch(1, 1)
        for i, (nombre, desc) in enumerate(herramientas):
            etiqueta_nombre = QLabel(nombre)
            etiqueta_nombre.setStyleSheet(
                f"color: {COLORES.acento}; font-weight: {TIPO.peso_semibold}; font-size: {TIPO.t_caption}px;"
            )
            etiqueta_nombre.setWordWrap(True)
            rejilla.addWidget(etiqueta_nombre, i, 0, alignment=Qt.AlignmentFlag.AlignTop)

            etiqueta_desc = QLabel(desc)
            etiqueta_desc.setWordWrap(True)
            etiqueta_desc.setStyleSheet(self._estilo_descripcion())
            rejilla.addWidget(etiqueta_desc, i, 1)
        v.addLayout(rejilla)

        return tarjeta

    def _construir_tarjeta(self, categoria: dict) -> tuple[QFrame, list[tuple[QLabel, QLabel, str]]]:
        tarjeta = QFrame()
        tarjeta.setObjectName("tarjeta")
        v = QVBoxLayout(tarjeta)
        v.setContentsMargins(ESPACIADO.lg, ESPACIADO.lg, ESPACIADO.lg, ESPACIADO.lg)
        v.setSpacing(ESPACIADO.sm)

        encabezado = QLabel(f"{categoria['atributo']} — {categoria['titulo']}")
        encabezado.setObjectName("tarjetaTitulo")
        v.addWidget(encabezado)

        subtitulo = QLabel(categoria["descripcion"])
        subtitulo.setWordWrap(True)
        subtitulo.setObjectName("tarjetaDescripcion")
        v.addWidget(subtitulo)

        rejilla = QGridLayout()
        rejilla.setHorizontalSpacing(ESPACIADO.md)
        rejilla.setVerticalSpacing(ESPACIADO.xs)
        rejilla.setColumnStretch(1, 1)

        filas: list[tuple[QLabel, QLabel, str]] = []
        for i, (firma, descripcion) in enumerate(categoria["metodos"]):
            etiqueta_metodo = QLabel(firma)
            etiqueta_metodo.setStyleSheet(self._estilo_metodo())
            etiqueta_metodo.setWordWrap(True)
            rejilla.addWidget(etiqueta_metodo, i, 0, alignment=Qt.AlignmentFlag.AlignTop)

            etiqueta_desc = QLabel(descripcion)
            etiqueta_desc.setWordWrap(True)
            etiqueta_desc.setStyleSheet(self._estilo_descripcion())
            rejilla.addWidget(etiqueta_desc, i, 1)

            texto_busqueda = f"{categoria['atributo']} {firma} {descripcion}".lower()
            filas.append((etiqueta_metodo, etiqueta_desc, texto_busqueda))

        v.addLayout(rejilla)
        return tarjeta, filas

    def _filtrar(self, texto: str) -> None:
        consulta = texto.strip().lower()
        for tarjeta, filas in self._tarjetas:
            alguna_visible = False
            for etiqueta_metodo, etiqueta_desc, texto_busqueda in filas:
                visible = not consulta or consulta in texto_busqueda
                etiqueta_metodo.setVisible(visible)
                etiqueta_desc.setVisible(visible)
                alguna_visible = alguna_visible or visible
            tarjeta.setVisible(alguna_visible)
