"""Markdown de solo lectura, sin cargar recursos ni navegar enlaces externos."""
from PySide6.QtCore import QTimer
from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import QFrame, QTextBrowser

from app.resources.tokens import COLORES


class ChatText(QTextBrowser):
    def __init__(self, texto, *, markdown=False):
        super().__init__()
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setOpenLinks(False)
        self.setOpenExternalLinks(False)
        self.setStyleSheet(f"background: transparent; border: none; padding: 0; color: {COLORES.tinta}; font-size: 13px;")
        self.document().setDefaultStyleSheet(
            f"p {{ margin: 4px 0; }} pre {{ background-color: {COLORES.papel}; white-space: pre-wrap; }} "
            f"code {{ color: {COLORES.cian}; font-family: Consolas; }}"
        )
        if markdown:
            self.document().setMarkdown(texto, QTextDocument.MarkdownFeature.MarkdownDialectGitHub |
                             QTextDocument.MarkdownFeature.MarkdownNoHTML)
        else:
            self.setPlainText(texto)
        self.document().documentLayout().documentSizeChanged.connect(self._ajustar)
        QTimer.singleShot(0, self._ajustar)

    def loadResource(self, resource_type, name):
        # Las respuestas del modelo nunca deben leer archivos locales ni URLs.
        return None

    def _ajustar(self, *_):
        height = min(420, max(42, int(self.document().size().height()) + 8))
        if height != self.height():
            self.setFixedHeight(height)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._ajustar()
