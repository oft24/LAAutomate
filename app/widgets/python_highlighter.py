"""Resaltado Python liviano para los editores de LaAutomate."""
from __future__ import annotations

from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat

from app.resources.tokens import COLORES


def _formato(color: str, *, negrita: bool = False, cursiva: bool = False) -> QTextCharFormat:
    formato = QTextCharFormat()
    formato.setForeground(QColor(color))
    if negrita:
        formato.setFontWeight(QFont.Weight.DemiBold)
    formato.setFontItalic(cursiva)
    return formato


class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, documento) -> None:
        super().__init__(documento)
        palabras = (
            "and|as|assert|async|await|break|case|class|continue|def|del|elif|else|"
            "except|False|finally|for|from|global|if|import|in|is|lambda|match|None|"
            "nonlocal|not|or|pass|raise|return|True|try|while|with|yield"
        )
        self._reglas = [
            (QRegularExpression(rf"\b(?:{palabras})\b"), _formato(COLORES.violeta, negrita=True)),
            (QRegularExpression(r"\b(?:self|cls)\b"), _formato(COLORES.cian)),
            (QRegularExpression(r"@[A-Za-z_][A-Za-z0-9_.]*"), _formato(COLORES.acento, negrita=True)),
            (QRegularExpression(r"\b(?:0[xX][0-9A-Fa-f]+|\d+(?:\.\d+)?)\b"), _formato(COLORES.cian)),
            (QRegularExpression(r"\b(?:def|class)\s+([A-Za-z_][A-Za-z0-9_]*)"), _formato(COLORES.cian, negrita=True)),
            (QRegularExpression(r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\""), _formato(COLORES.ocre)),
            (QRegularExpression(r"#.*$"), _formato(COLORES.grafito_claro, cursiva=True)),
        ]

    def highlightBlock(self, texto: str) -> None:  # noqa: N802 - nombre de la API Qt
        for patron, formato in self._reglas:
            coincidencias = patron.globalMatch(texto)
            while coincidencias.hasNext():
                coincidencia = coincidencias.next()
                self.setFormat(coincidencia.capturedStart(), coincidencia.capturedLength(), formato)

