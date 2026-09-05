"""Geometría de controles: la hoja de estilos no debe romper el tamaño real."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QLineEdit, QComboBox

from app.resources.tokens import COLORES, construir_qss


@pytest.fixture(scope="module")
def app():
    app = QApplication.instance() or QApplication([])
    QFontDatabase.addApplicationFont("C:/Windows/Fonts/segoeui.ttf")
    app.setFont(QFont("Segoe UI", 10))
    return app


def test_controles_tienen_alturas_coherentes(app):
    ventana = QWidget()
    ventana.setStyleSheet(construir_qss())
    layout = QVBoxLayout(ventana)
    controles = [QPushButton("Ejecutar"), QLineEdit(), QComboBox()]
    for control in controles:
        layout.addWidget(control)
    ventana.show()
    app.processEvents()
    alturas = [control.height() for control in controles]
    assert max(alturas) - min(alturas) <= 2, alturas
    ventana.close()


def test_guardar_es_compacto_y_deshabilitado_no_es_una_barra_gris(app):
    from app.windows.recorder_view import RecorderView
    vista = RecorderView()
    vista.setStyleSheet(construir_qss())
    vista.resize(1100, 750)
    vista.show()
    app.processEvents()
    assert vista.boton_guardar.width() == 204
    assert not vista.boton_guardar.isEnabled()
    assert vista.boton_guardar.mapTo(vista, QPoint()).y() < vista.vista_codigo.mapTo(vista, QPoint()).y()
    fondo = vista.boton_guardar.grab().toImage().pixelColor(10, 10).name()
    assert fondo.lower() == COLORES.tarjeta_elevada.lower()
    assert vista.boton_modo_web.height() == vista.boton_modo_escritorio.height() == 32
    vista.close()


def test_menu_colapsado_no_superpone_control_y_logo(app):
    from app.widgets.sidebar import Sidebar, ANCHO_COLAPSADO
    barra = Sidebar()
    barra.setStyleSheet(construir_qss())
    barra.resize(224, 740)
    barra.show()
    barra._alternar_colapso()
    QTest.qWait(300)
    app.processEvents()
    assert barra.width() == ANCHO_COLAPSADO
    assert barra._boton_colapsar.size().width() == barra._boton_colapsar.size().height() == 32
    logo = barra._logo.mapTo(barra, QPoint())
    control = barra._boton_colapsar.mapTo(barra, QPoint())
    assert control.y() > logo.y() + barra._logo.height()
    assert control.x() >= 0 and control.x() + 32 <= barra.width()
    assert all(boton.height() == 44 for boton in barra._botones)
    assert barra._boton_colapsar.accessibleName() == "Expandir menú"
    barra.close()
