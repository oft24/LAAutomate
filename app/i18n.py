"""Traducción local de controles; nunca transforma código, mensajes o archivos."""
from PySide6.QtCore import QObject, Signal, QSettings
from PySide6.QtWidgets import QLabel as QtLabel, QPushButton as QtButton, QToolButton as QtToolButton
from PySide6.QtWidgets import QLineEdit as QtLineEdit, QPlainTextEdit as QtPlainTextEdit, QTableWidget as QtTable, QCheckBox as QtCheckBox


EN = {
    'Actualizar': 'Refresh', 'Automatización': 'Automation', 'Categoría': 'Category',
    'Disparador': 'Trigger', 'Estado': 'Status', 'Cuándo': 'When', 'Duración': 'Duration',
    'Resultado': 'Result', 'Programadas (cron)': 'Scheduled (cron)', 'Solo manuales': 'Manual only',
    'Programado': 'Scheduled', 'Manual': 'Manual', 'Buscar…': 'Search…',
    'Buscar archivo de registro…': 'Search log files…',
    'Buscar en el registro · Enter para siguiente coincidencia': 'Search log · Enter for next match',
    'Selecciona una automatización de la lista para ver y editar su código aquí.': 'Select an automation to view and edit its code here.',
    'El horario se guarda en el código: cron:minuto hora día mes día-semana. La app debe estar abierta para ejecutarlo.': 'Schedules are saved in code: cron:minute hour day month weekday. Keep the app open to run them.',
    'Editar disparador en Automatizaciones': 'Edit trigger in Automations',
    'Un archivo por automatización y por grabadora — elige cuál quieres leer': 'One file per automation and recorder — choose a log to read',
    'Sin disparadores todavía': 'No triggers yet',
    'Registra una automatización con un disparador de tipo cron para verla programada aquí.': 'Register an automation with a cron trigger to see its schedule here.',
    'Copia el mensaje completo al portapapeles.': 'Copy the complete message to the clipboard.',
    'Copia la selección o, si no seleccionaste texto, todo el mensaje.': 'Copy the selection, or the entire message if no text is selected.',
    'Sin ejecuciones todavía — corre una automatización para ver su pista aquí.': 'No runs yet — run an automation to see its timeline here.',
    'Idioma': 'Language', 'Operación': 'Operation', 'Sistema': 'System',
    'Panel principal': 'Dashboard', 'Automatizaciones': 'Automations',
    'Grabadora': 'Recorder', 'Programador': 'Scheduler', 'Asistente IA': 'AI assistant',
    'Registros': 'Logs', 'Bóveda de credenciales': 'Credential vault',
    'Ejecutar': 'Run', 'Ejecutar todo': 'Run all', 'Cancelar': 'Cancel',
    'Guardar': 'Save', 'Guardado': 'Saved', 'Eliminar': 'Delete',
    'Corregir código': 'Repair code', 'Recargar archivo': 'Reload file',
    'Bóveda': 'Vault', 'Código': 'Code', 'Ejecución': 'Execution',
    'Configuración': 'Settings', 'Registradas': 'Registered',
    'Elige una para ver, editar o correr su código': 'Select an automation to view, edit or run its code',
    'Código (automation.py) — edítalo y ejecútalo aquí mismo': 'Code (automation.py) — edit and run it here',
    'Salida en vivo': 'Live output', 'cambios sin guardar': 'unsaved changes',
    'No usa self.credenciales (no depende de la Bóveda).': 'Does not use self.credenciales (no vault required).',
    'Copiar mensaje': 'Copy message', 'Copiar código': 'Copy code',
    'Crear automatización': 'Create automation', 'Generar con Gemini': 'Generate with Gemini',
    'Nueva automatización': 'New automation', 'Nombre del flujo': 'Workflow name',
    'Confirma un nombre fácil de reconocer. El código quedará visible para revisarlo antes de ejecutarlo.': 'Choose an easy-to-recognize name. The code will remain visible for review before you run it.',
    'ejemplo: reporte_diario': 'example: daily_report',
    'Escribe un nombre para continuar.': 'Enter a name to continue.',
    'Ya existe una automatización con ese nombre. No se sobrescribirá.': 'An automation with that name already exists. It will not be overwritten.',
    '✓ Automatización creada': '✓ Automation created',
    'Cancelar generación': 'Cancel generation', 'Intentar sondeo': 'Probe models',
    'Generando…': 'Generating…', 'Código copiado': 'Code copied', 'TÚ': 'YOU',
    'CONTEXTO DE GENERACIÓN': 'GENERATION CONTEXT', 'Configurar clave': 'Set API key',
    'Olvidar': 'Forget key', 'Actualizar modelos': 'Refresh models', 'Modelo': 'Model',
    'Código de referencia': 'Reference code', 'Capturas de este turno': 'Screenshots for this turn',
    'Adjuntar capturas': 'Attach screenshots', 'Limpiar todas': 'Clear all', 'Quitar': 'Remove',
    'Desde capturas': 'From screenshots', 'Mejorar un flujo': 'Improve a workflow',
    'Explicar un error': 'Explain an error', '● Gemini configurado': '● Gemini configured',
    '● Falta configurar la API key': '● API key required',
    'Contexto del proyecto incluido · sin claves ni bóveda': 'Project context included · no keys or vault',
    'Sin capturas. Puedes describir el flujo solo con texto.': 'No screenshots. You can describe the workflow using text only.',
    'Las imágenes solo salen del equipo al presionar “Generar con Gemini”.': 'Images leave your computer only when you click “Generate with Gemini”.',
    'Describe el flujo, adjunta capturas y obtén un automation.py listo para revisar': 'Describe the workflow, attach screenshots and get an automation.py to review',
    'Cuéntame qué quieres automatizar. Puedo usar capturas, la referencia real de acciones y el código de una automatización existente como contexto. No guardaré ni ejecutaré nada sin tu confirmación.': 'Tell me what you want to automate. I can use screenshots, the real action reference and an existing automation as context. I will not save or run anything without your confirmation.',
    'Ejemplo: inicia sesión, descarga el reporte visible en la captura y guárdalo en Excel…': 'Example: sign in, download the report shown in the screenshot and save it to Excel…',
    'Ctrl+V para pegar capturas · puedes agregar varias antes de enviar': 'Press Ctrl+V to paste screenshots · you can add several before sending',
    'Resultado · revisa antes de crear': 'Result · review before creating',
    'Sin código adicional': 'No additional code',
    'Analiza las capturas adjuntas y crea una automatización completa para este flujo:': 'Analyze the attached screenshots and create a complete automation for this workflow:',
    'Revisa la automatización seleccionada y propón una versión más robusta que:': 'Review the selected automation and propose a more robust version that:',
    'Ayúdame a diagnosticar este error y después propón el cambio mínimo seguro:': 'Help me diagnose this error, then propose the smallest safe change:',
    'Sondeo: prueba una respuesta corta en hasta 10 modelos por capacidad. No envía tus capturas ni garantiza que la generación funcione. Si el modelo elegido vuelve a saturarse, buscamos la siguiente alternativa; pulsa Generar para enviar tu solicitud. Los modelos fallidos se omiten durante 5 minutos.': 'Model probe: tests a short response from up to 10 models by capability. It does not send your screenshots or guarantee generation. If the selected model becomes overloaded again, the next alternative is tested; click Generate to send your request. Failed models are skipped for 5 minutes.',
    'Prueba hasta 10 modelos por capacidad y selecciona el primero disponible, sin mensaje ni capturas.': 'Tests up to 10 models by capability and selects the first available one, without your message or screenshots.',
    'Pega texto o imágenes con Ctrl+V. Puedes agregar varias capturas.': 'Paste text or images with Ctrl+V. You can add several screenshots.',
    'Quitar la captura seleccionada': 'Remove the selected screenshot',
    'Conservé tu mensaje actual. Puedes editarlo antes de generar.': 'Your current message was preserved. You can edit it before generating.',
    'Capturas listas. Revisa su contenido antes de generar.': 'Screenshots ready. Review them before generating.',
    'Describe primero la automatización.': 'Describe the automation first.',
    'Consultando modelos…': 'Loading models…',
    'Consultando hasta 10 modelos por capacidad, sin mensaje ni capturas…': 'Probing up to 10 models by estimated capability, without your message or screenshots…',
    'Sondeo cancelado. Mensaje y capturas conservados.': 'Probe cancelled. Message and screenshots preserved.',
    'Generación cancelada. Mensaje y capturas conservados.': 'Generation cancelled. Message and screenshots preserved.',
    'Escritorio': 'Desktop', 'Nombre:': 'Name:', 'URL inicial:': 'Starting URL:',
    'Iniciar grabación': 'Start recording', 'Detener y generar código': 'Stop and generate code',
    'Ver registro': 'View log', 'Guardar automatización': 'Save automation',
    'Código generado': 'Generated code', 'Pasos capturados': 'Recorded steps',
    'Lista para grabar · configura el nombre y el destino.': 'Ready to record · set the name and target.',
    'Sin URL: al iniciar, da tu primer click en la ventana que quieras grabar': 'No URL needed: start, then click the window you want to record',
    'Graba una app web o una app de escritorio dando los clicks tú mismo — al terminar se genera el código': 'Record a web or desktop app by clicking through it — code is generated when you stop',
    'Contraer menú': 'Collapse menu', 'Expandir menú': 'Expand menu',
    'Abrir carpeta': 'Open folder', 'Cerrar': 'Close', 'Omitir por ahora': 'Skip for now',
    'Guardar en la Bóveda': 'Save to vault', 'Contraseña': 'Password', 'Usuario': 'User',
    'Disparadores activos y cuándo va a correr cada automatización': 'Active triggers and upcoming automation runs',
    'Detalle': 'Details', 'Reintentar': 'Retry', 'Abrir log completo': 'Open full log',
    'Ver captura de pantalla': 'View screenshot', 'Sin mensaje adicional.': 'No additional message.',
    'Ejecuciones hoy': 'Runs today', 'Tasa de éxito (7 días)': 'Success rate (7 days)',
    'Duración media': 'Average duration', 'Próxima ejecución': 'Next run',
    'Últimas ejecuciones': 'Recent runs', 'Pista de ejecuciones recientes': 'Recent run timeline',
    'Qué está pasando con tus automatizaciones hoy': 'What is happening with your automations today',
    'Completado': 'Completed', 'Con error': 'Failed', 'En ejecución': 'Running',
}


class Language(QObject):
    changed = Signal()

    def __init__(self):
        super().__init__()
        self.code = 'es'

    def set(self, code, *, persist=True):
        if code not in ('es', 'en'):
            raise ValueError('Unsupported language')
        if persist:
            settings = QSettings('LaAutomate', 'Desktop')
            settings.setValue('language', code)
            settings.sync()
        if code != self.code:
            self.code = code
            self.changed.emit()

    def restore(self):
        code = QSettings('LaAutomate', 'Desktop').value('language', 'es')
        self.set(code if code in ('es', 'en') else 'es', persist=False)


language = Language()


def translate(text):
    if language.code == 'es' or not text:
        return text
    if text in EN:
        return EN[text]
    # Preserve decoration and uppercase used by navigation/section labels.
    stripped = text.lstrip(' /▶■●')
    prefix = text[:len(text) - len(stripped)]
    if stripped in EN:
        return prefix + EN[stripped]
    for source, target in EN.items():
        if stripped == source.upper():
            return prefix + target.upper()
    if stripped.startswith('Se guardará como:'):
        return prefix + 'Saved as:' + stripped[len('Se guardará como:'):]
    return text


class _Localized:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._source_text = self.text()
        self._source_tooltip = self.toolTip()
        language.changed.connect(self._retranslate)
        self._retranslate()

    def setText(self, text):
        self._source_text = text
        super().setText(translate(text))

    def setToolTip(self, text):
        self._source_tooltip = text
        super().setToolTip(translate(text))

    def _retranslate(self):
        super().setText(translate(self._source_text))
        super().setToolTip(translate(self._source_tooltip))


class QLabel(_Localized, QtLabel):
    pass


class QPushButton(_Localized, QtButton):
    pass


class QToolButton(_Localized, QtToolButton):
    pass


class QCheckBox(_Localized, QtCheckBox):
    pass


class _Placeholder:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._source_placeholder = self.placeholderText()
        language.changed.connect(self._retranslate_placeholder)

    def setPlaceholderText(self, text):
        self._source_placeholder = text
        super().setPlaceholderText(translate(text))

    def _retranslate_placeholder(self):
        super().setPlaceholderText(translate(self._source_placeholder))


class QLineEdit(_Placeholder, QtLineEdit):
    pass


class QPlainTextEdit(_Placeholder, QtPlainTextEdit):
    pass


class QTableWidget(QtTable):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._source_headers = []
        language.changed.connect(self._retranslate_headers)

    def setHorizontalHeaderLabels(self, labels):
        self._source_headers = list(labels)
        self._retranslate_headers()

    def _retranslate_headers(self):
        super().setHorizontalHeaderLabels([translate(label) for label in self._source_headers])
