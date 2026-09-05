"""Editor compartido: números de línea y foco de lectura sin alterar el código."""
from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QTextFormat
from PySide6.QtWidgets import QPlainTextEdit, QTextEdit, QWidget

from app.resources.tokens import COLORES


class _Numeros(QWidget):
    def sizeHint(self):
        return QSize(self.parent().ancho_numeros(), 0)

    def paintEvent(self, event):
        self.parent().pintar_numeros(event)


class CodeEditor(QPlainTextEdit):
    def __init__(self, parent=None, *, readOnly=False):
        super().__init__(parent)
        self.setReadOnly(readOnly)
        self.setObjectName("editorCodigo")
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.numeros = _Numeros(self)
        self.blockCountChanged.connect(self._margen)
        self.updateRequest.connect(self._actualizar_numeros)
        self.cursorPositionChanged.connect(self._linea_actual)
        self.textChanged.connect(self._linea_actual)
        self._margen()
        self._linea_actual()

    def ancho_numeros(self):
        return 22 + self.fontMetrics().horizontalAdvance("9") * len(str(max(1, self.blockCount())))

    def setReadOnly(self, value):
        super().setReadOnly(value)
        self._linea_actual()

    def _margen(self, *_):
        self.setViewportMargins(self.ancho_numeros(), 0, 0, 0)

    def _actualizar_numeros(self, rect, dy):
        if dy:
            self.numeros.scroll(0, dy)
        else:
            self.numeros.update(0, rect.y(), self.numeros.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._margen()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        area = self.contentsRect()
        self.numeros.setGeometry(QRect(area.left(), area.top(), self.ancho_numeros(), area.height()))

    def _linea_actual(self):
        selection = QTextEdit.ExtraSelection()
        selection.format.setBackground(QColor(COLORES.tarjeta_elevada))
        selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
        selection.cursor = self.textCursor()
        selection.cursor.clearSelection()
        self.setExtraSelections([] if self.isReadOnly() or self.document().isEmpty() else [selection])

    def pintar_numeros(self, event):
        painter = QPainter(self.numeros)
        painter.fillRect(event.rect(), QColor(COLORES.tarjeta))
        painter.setFont(self.font())
        block = self.firstVisibleBlock()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        while block.isValid() and top <= event.rect().bottom():
            height = round(self.blockBoundingRect(block).height())
            if block.isVisible() and top + height >= event.rect().top():
                active = block.blockNumber() == self.textCursor().blockNumber()
                painter.setPen(QColor(COLORES.cian if active else COLORES.grafito_claro))
                painter.drawText(0, top, self.numeros.width() - 10, self.fontMetrics().height(),
                                 Qt.AlignmentFlag.AlignRight, str(block.blockNumber() + 1))
            top += height
            block = block.next()
