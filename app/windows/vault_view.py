from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStackedLayout,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from app.i18n import QLineEdit, QTableWidget
from app.i18n import QLabel, QPushButton

from app.resources.tokens import COLORES, DENSIDAD, ESPACIADO, TIPO
from app.widgets.empty_state import EmptyState
from app.widgets.page_header import PageHeader
from app.widgets.toast import mostrar_toast
from core.vault import Vault
from engine.registry import listar

_TIPS = [
    "El nombre que escribas aquí debe ser EXACTAMENTE el mismo que el de la automatización "
    "(el que usaste en @registrar(nombre=...) o en la Grabadora) — así es como self.credenciales "
    "sabe cuáles cargar en cada ejecución.",
    "En tu automation.py, accede a los valores guardados con self.credenciales.usuario y "
    "self.credenciales.password. Nunca los escribas literalmente en el código.",
    "Puedes actualizar unas credenciales guardando de nuevo con el mismo nombre — se sobrescriben, "
    "no se duplican.",
    "El botón “Editar” de la tabla de abajo precarga el nombre y el usuario -- la contraseña nunca "
    "se muestra, y si dejas ese campo vacío se conserva la que ya estaba guardada.",
]


class VaultView(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.vault = Vault()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        layout.addWidget(
            PageHeader(
                "Bóveda de credenciales",
                "Guarda usuario/contraseña cifrados para que tus automatizaciones los usen sin escribirlos en el código",
            )
        )

        fila = QHBoxLayout()
        fila.setSpacing(ESPACIADO.lg)

        tarjeta = QFrame()
        tarjeta.setObjectName("tarjeta")
        tarjeta.setMaximumWidth(420)
        tarjeta.setMinimumWidth(340)
        v = QVBoxLayout(tarjeta)
        v.setContentsMargins(ESPACIADO.xl, ESPACIADO.xl, ESPACIADO.xl, ESPACIADO.xl)
        v.setSpacing(ESPACIADO.md)

        self.titulo_formulario = QLabel("Guardar nuevas credenciales")
        self.titulo_formulario.setObjectName("tarjetaTitulo")
        v.addWidget(self.titulo_formulario)

        nota = QLabel(
            "Los secretos se guardan en el almacén de credenciales de Windows — nunca en texto "
            "plano dentro del proyecto."
        )
        nota.setObjectName("tarjetaDescripcion")
        nota.setWordWrap(True)
        v.addWidget(nota)

        formulario = QFormLayout()
        formulario.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        formulario.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        formulario.setSpacing(ESPACIADO.sm)
        self.campo_nombre = QLineEdit()
        self.campo_nombre.setPlaceholderText("nombre_de_la_automatización")
        self.campo_usuario = QLineEdit()
        self.campo_password = QLineEdit(echoMode=QLineEdit.EchoMode.Password)
        self.campo_password.setPlaceholderText("Contraseña")
        formulario.addRow("Automatización", self.campo_nombre)
        formulario.addRow("Usuario", self.campo_usuario)
        formulario.addRow("Contraseña", self.campo_password)
        v.addLayout(formulario)

        fila_botones_formulario = QHBoxLayout()
        boton_guardar = QPushButton("Guardar en la bóveda")
        boton_guardar.setObjectName("primario")
        boton_guardar.clicked.connect(self._guardar)
        fila_botones_formulario.addWidget(boton_guardar)

        self.boton_cancelar_edicion = QPushButton("Cancelar edición")
        self.boton_cancelar_edicion.setVisible(False)
        self.boton_cancelar_edicion.clicked.connect(self._cancelar_edicion)
        fila_botones_formulario.addWidget(self.boton_cancelar_edicion)
        v.addLayout(fila_botones_formulario)

        self._nombre_en_edicion: str | None = None

        fila.addWidget(tarjeta)
        fila.addWidget(self._construir_tarjeta_tips(), stretch=1)

        layout.addLayout(fila)

        layout.addWidget(self._subtitulo("Credenciales guardadas"))

        self._contenedor_guardadas = QWidget()
        self._pila_guardadas = QStackedLayout(self._contenedor_guardadas)

        self.tabla = QTableWidget(0, 5)
        self.tabla.setHorizontalHeaderLabels(["Automatización", "Usuario", "Contraseña", "Token", ""])
        self.tabla.verticalHeader().hide()
        self.tabla.verticalHeader().setDefaultSectionSize(DENSIDAD.alto_fila)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.setShowGrid(False)
        header = self.tabla.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        # Fixed, no ResizeToContents: un cell widget (los botones Editar/
        # Eliminar) no siempre reporta su sizeHint real a tiempo para el
        # calculo automatico de ancho -- mismo problema ya visto en
        # scheduler_view y data_table con los badges de estado.
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.tabla.setColumnWidth(4, 160)

        self._vacio_guardadas = EmptyState(
            "Sin credenciales guardadas todavía",
            "Guárdalas aquí arriba, o desde el diálogo que aparece al terminar de grabar una automatización "
            "que usó un campo de contraseña.",
        )
        self._pila_guardadas.addWidget(self.tabla)
        self._pila_guardadas.addWidget(self._vacio_guardadas)
        layout.addWidget(self._contenedor_guardadas, stretch=1)

        self._llenar_guardadas()

    @staticmethod
    def _subtitulo(texto: str) -> QLabel:
        etiqueta = QLabel(texto)
        etiqueta.setObjectName("subtituloSeccion")
        return etiqueta

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # se refresca cada vez que se navega a esta vista -- las
        # credenciales pueden haberse guardado desde OTRO lugar (ej. el
        # diálogo de la Grabadora al terminar de grabar), no solo desde
        # el formulario de esta misma vista.
        self._llenar_guardadas()

    def _llenar_guardadas(self) -> None:
        filas = []
        for spec in listar():
            try:
                credenciales = self.vault.credenciales_para(spec.nombre)
            except Exception:
                self.tabla.setRowCount(0)
                mostrar_toast(self, "No se pudo leer la Bóveda de Windows. Tus credenciales no se han modificado.", "error")
                return
            if credenciales.usuario or credenciales.password or credenciales.token:
                filas.append((spec.nombre, credenciales))

        self._pila_guardadas.setCurrentWidget(self._vacio_guardadas if not filas else self.tabla)

        self.tabla.setRowCount(len(filas))
        for i, (nombre, credenciales) in enumerate(filas):
            self.tabla.setItem(i, 0, QTableWidgetItem(nombre))
            self.tabla.setItem(i, 1, QTableWidgetItem(credenciales.usuario or "—"))
            # el VALOR nunca se muestra, ni aqui ni en ningun otro lugar de
            # la app -- solo si hay algo guardado o no.
            self.tabla.setItem(i, 2, self._item_estado(bool(credenciales.password)))
            self.tabla.setItem(i, 3, self._item_estado(bool(credenciales.token)))
            self.tabla.setCellWidget(i, 4, self._botones_fila(nombre))

    @staticmethod
    def _item_estado(guardado: bool) -> QTableWidgetItem:
        item = QTableWidgetItem("Guardada" if guardado else "—")
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item.setForeground(QColor(COLORES.musgo if guardado else COLORES.grafito_claro))
        fuente = item.font()
        fuente.setBold(guardado)
        item.setFont(fuente)
        return item

    def _botones_fila(self, nombre: str) -> QWidget:
        contenedor = QWidget()
        fila = QHBoxLayout(contenedor)
        fila.setContentsMargins(0, 0, 0, 0)
        fila.setSpacing(ESPACIADO.xs)

        boton_editar = QPushButton("Editar")
        boton_editar.clicked.connect(lambda: self._editar_credencial(nombre))
        fila.addWidget(boton_editar)

        boton_eliminar = QPushButton("Eliminar")
        boton_eliminar.clicked.connect(lambda: self._eliminar_credencial(nombre))
        fila.addWidget(boton_eliminar)

        return contenedor

    def _editar_credencial(self, nombre: str) -> None:
        try:
            credenciales = self.vault.credenciales_para(nombre)
        except Exception:
            mostrar_toast(self, "No se pudo leer esta credencial en la Bóveda de Windows.", "error")
            return
        self._nombre_en_edicion = nombre

        self.campo_nombre.setText(nombre)
        self.campo_usuario.setText(credenciales.usuario or "")
        self.campo_password.clear()
        # el valor real NUNCA se precarga aqui -- solo se avisa que ya
        # existe uno, y que dejarlo vacío lo conserva sin cambios.
        self.campo_password.setPlaceholderText(
            "Contraseña guardada -- déjalo vacío para conservarla" if credenciales.password else "Contraseña"
        )

        self.titulo_formulario.setText(f"Editando “{nombre}”")
        # el nombre queda bloqueado durante la edicion -- cambiarlo aqui
        # NO renombra la credencial (la Boveda no soporta eso), solo
        # crearia una entrada nueva bajo otro nombre y confundiria cual es
        # cual.
        self.campo_nombre.setEnabled(False)
        self.boton_cancelar_edicion.setVisible(True)
        self.campo_password.setFocus()

    def _cancelar_edicion(self) -> None:
        self._nombre_en_edicion = None
        self.campo_nombre.clear()
        self.campo_nombre.setEnabled(True)
        self.campo_usuario.clear()
        self.campo_password.clear()
        self.campo_password.setPlaceholderText("Contraseña")
        self.titulo_formulario.setText("Guardar nuevas credenciales")
        self.boton_cancelar_edicion.setVisible(False)

    def _eliminar_credencial(self, nombre: str) -> None:
        respuesta = QMessageBox.question(
            self,
            "Eliminar credenciales",
            f"¿Eliminar las credenciales guardadas de “{nombre}” de la Bóveda?\n\n"
            "Si su automation.py todavía usa self.credenciales, la próxima ejecución fallará "
            "hasta que guardes unas nuevas.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if respuesta != QMessageBox.StandardButton.Yes:
            return
        try:
            self.vault.eliminar(nombre)
        except Exception:
            mostrar_toast(self, "No se pudo completar la eliminación. Revisa la Bóveda antes de reintentar.", "error")
            return
        self._llenar_guardadas()
        mostrar_toast(self, f"Credenciales de “{nombre}” eliminadas de la Bóveda.", "info")

    @staticmethod
    def _construir_tarjeta_tips() -> QFrame:
        tarjeta = QFrame()
        tarjeta.setObjectName("tarjeta")
        v = QVBoxLayout(tarjeta)
        v.setContentsMargins(ESPACIADO.xl, ESPACIADO.xl, ESPACIADO.xl, ESPACIADO.xl)
        v.setSpacing(ESPACIADO.sm)

        titulo = QLabel("Cómo se usan en tu código")
        titulo.setObjectName("tarjetaTitulo")
        v.addWidget(titulo)

        for tip in _TIPS:
            etiqueta = QLabel(f"•  {tip}")
            etiqueta.setObjectName("tarjetaDescripcion")
            etiqueta.setWordWrap(True)
            v.addWidget(etiqueta)

        ejemplo = QLabel(
            "self.correo.enviar_smtp(\n"
            "    host, puerto,\n"
            "    self.credenciales.usuario,\n"
            "    self.credenciales.password,\n"
            "    para, asunto, cuerpo,\n"
            ")"
        )
        ejemplo.setStyleSheet(
            f"background-color: {COLORES.papel}; border: 1px solid {COLORES.borde}; "
            f"border-radius: 6px; padding: {ESPACIADO.sm}px; font-family: {TIPO.familia_mono}; "
            f"font-size: {TIPO.t_caption}px; color: {COLORES.tinta};"
        )
        v.addWidget(ejemplo)
        v.addStretch()
        return tarjeta

    def _guardar(self) -> None:
        nombre = self.campo_nombre.text().strip()
        if not nombre:
            mostrar_toast(self, "Escribe el nombre de la automatización antes de guardar.", "error")
            return
        if nombre not in {spec.nombre for spec in listar()}:
            mostrar_toast(self, "Selecciona el nombre de una automatización registrada para poder recuperar sus credenciales aquí.", "error")
            return

        usuario = self.campo_usuario.text()
        password = self.campo_password.text()
        editando = self._nombre_en_edicion == nombre

        if not usuario and not password:
            if editando:
                # nada que actualizar -- dejar ambos vacios mientras se
                # edita significa "no cambiar nada", no "borrar todo".
                mostrar_toast(self, "No escribiste ningún cambio -- nada que guardar.", "error")
            else:
                mostrar_toast(self, "Escribe un usuario o una contraseña antes de guardar.", "error")
            return

        # se escribe SOLO lo que el usuario realmente llenó -- dejar la
        # contraseña vacía al editar (para conservar la ya guardada) no
        # debe borrarla, a diferencia del Vault.guardar() original que
        # sobrescribe ambos campos siempre.
        try:
            if usuario:
                self.vault.guardar_usuario(nombre, usuario)
            if password:
                self.vault.guardar_password(nombre, password)
        except Exception:
            mostrar_toast(self, "No se completó el guardado. Algún campo pudo actualizarse; revisa la Bóveda y vuelve a intentarlo.", "error")
            return

        if editando:
            self._cancelar_edicion()
        else:
            self.campo_password.clear()
        self._llenar_guardadas()
        mostrar_toast(self, f"Credenciales guardadas para «{nombre}».", "exito")
