"""Language changes preserve drafts; copy works in editable and read-only chat."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QTextCursor
from PySide6.QtCore import Qt, QSettings as QtSettings
from PySide6.QtTest import QTest
from app.i18n import Language, language, QPushButton
from app.widgets.chat_text import ChatText
from app.windows.assistant_view import _EntradaChat, _Burbuja, _CrearAutomatizacionDialog


@pytest.fixture
def app():
    app = QApplication.instance() or QApplication([])
    language.set('es', persist=False)
    yield app
    language.set('es', persist=False)


def test_language_updates_existing_and_new_controls_without_changing_draft(app):
    button = QPushButton('Copiar mensaje')
    draft = _EntradaChat()
    draft.setPlainText('Guardar **mi mensaje**')
    language.set('en', persist=False)
    assert button.text() == 'Copy message'
    assert QPushButton('Cancelar').text() == 'Cancel'
    button.setText('Generar con Gemini')
    assert button.text() == 'Generate with Gemini'
    assert draft.toPlainText() == 'Guardar **mi mensaje**'
    language.set('es', persist=False)
    assert button.text() == 'Generar con Gemini'


def test_language_selection_is_persisted(monkeypatch, tmp_path):
    import app.i18n as i18n

    ruta = tmp_path / 'ui.ini'
    monkeypatch.setattr(
        i18n,
        'QSettings',
        lambda *_args: QtSettings(str(ruta), QtSettings.Format.IniFormat),
    )
    first = Language()
    first.set('en')
    restored = Language()
    restored.restore()
    assert restored.code == 'en'


@pytest.mark.parametrize('readonly', [False, True])
def test_ctrl_c_copies_selected_draft(app, readonly):
    editor = _EntradaChat()
    editor.setPlainText('Texto áéí\nsegunda línea')
    editor.setReadOnly(readonly)
    editor.selectAll()
    QTest.keyClick(editor, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
    assert app.clipboard().text() == editor.toPlainText()


def test_chat_copy_button_preserves_original_markdown(app):
    message = '**Mensaje**\ncon acentos: ñ'
    bubble = _Burbuja('model', message)
    bubble.boton_copiar_mensaje.click()
    assert app.clipboard().text() == message
    view = bubble.findChild(ChatText)
    view.selectAll()
    view.copy()
    assert app.clipboard().text() == view.toPlainText()


def test_translatable_system_bubble_changes_but_keeps_user_content(app):
    system_text = (
        'Cuéntame qué quieres automatizar. Puedo usar capturas, la referencia real de acciones '
        'y el código de una automatización existente como contexto. No guardaré ni ejecutaré '
        'nada sin tu confirmación.'
    )
    bubble = _Burbuja('model', system_text, traducible=True)
    language.set('en', persist=False)
    bubble.boton_copiar_mensaje.click()
    assert app.clipboard().text().startswith('Tell me what you want to automate.')

    user_text = 'No traduzcas mi variable PRODUCTO_NOMBRE'
    user_bubble = _Burbuja('user', user_text)
    user_bubble.boton_copiar_mensaje.click()
    assert app.clipboard().text() == user_text


def test_create_dialog_normalizes_name_and_prevents_overwrite(app, monkeypatch, tmp_path):
    import app.windows.assistant_view as assistant

    monkeypatch.setattr(assistant, 'BASE_DIR', tmp_path)
    dialog = _CrearAutomatizacionDialog('Mi reporte 2026')
    assert dialog.nombre_normalizado() == 'mi_reporte_2026'
    assert dialog.boton_confirmar.objectName() == 'primario'
    assert dialog.boton_confirmar.isEnabled()
    assert 'automations/mi_reporte_2026/' in dialog.vista_nombre.text()

    (tmp_path / 'automations' / 'mi_reporte_2026').mkdir(parents=True)
    dialog._validar_nombre()
    assert not dialog.boton_confirmar.isEnabled()
    assert not dialog.error_nombre.isHidden()

    dialog.campo_nombre.clear()
    assert not dialog.boton_confirmar.isEnabled()
