"""Presentación y seguridad de los nuevos componentes, sin red."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QUrl
from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import QApplication, QLabel

from app.widgets.chat_text import ChatText
from app.widgets.code_editor import CodeEditor
from app.widgets.empty_state import EmptyState


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_editor_numeros_no_modifican_codigo(app):
    editor = CodeEditor()
    editor.resize(600, 300)
    editor.show()
    source = "\n".join(f"print({i})" for i in range(105))
    editor.setPlainText(source)
    app.processEvents()
    assert editor.toPlainText() == source
    assert editor.blockCount() == 105
    assert editor.viewportMargins().left() == editor.ancho_numeros()
    assert len(editor.extraSelections()) == 1
    editor.close()


def test_resultado_solo_lectura(app):
    editor = CodeEditor(readOnly=True)
    assert editor.isReadOnly()
    assert not editor.extraSelections()
    editor.setPlainText("print('ok')")
    editor.setReadOnly(False)
    assert editor.extraSelections()
    editor.setReadOnly(True)
    assert not editor.extraSelections()
    editor.setReadOnly(False)
    editor.clear()
    assert not editor.extraSelections()


def test_markdown_legible_y_texto_usuario_literal(app):
    model = ChatText("## Resultado\n\n**Listo**\n\n- Revisar código", markdown=True)
    user = ChatText("<b>texto</b> **literal**")
    assert "##" not in model.toPlainText()
    assert "**" not in model.toPlainText()
    assert user.toPlainText() == "<b>texto</b> **literal**"
    assert not model.openLinks()
    assert not model.openExternalLinks()


@pytest.mark.parametrize("url", ["file:///C:/private.png", "https://example.com/tracker.png"])
def test_chat_no_carga_recursos(app, url):
    widget = ChatText(f"![imagen]({url})", markdown=True)
    assert widget.loadResource(QTextDocument.ResourceType.ImageResource, QUrl(url)) is None


def test_burbuja_se_adapta_al_ancho(app):
    widget = ChatText("Una respuesta para revisar. " * 60, markdown=True)
    widget.resize(800, 100)
    widget.show()
    app.processEvents()
    wide = widget.height()
    widget.resize(300, widget.height())
    app.processEvents()
    assert wide <= widget.height() <= 420
    widget.close()


def test_estado_vacio_no_recorta_descripcion(app):
    widget = EmptyState("Sin credenciales guardadas todavía", "Guárdalas aquí arriba, o desde el diálogo que aparece al terminar de grabar una automatización que usó un campo de contraseña.")
    widget.resize(828, 144)
    widget.show()
    app.processEvents()
    for label in widget.findChildren(QLabel):
        assert label.height() >= label.heightForWidth(label.width())
    widget.close()
