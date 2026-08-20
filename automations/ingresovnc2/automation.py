"""Automatizacion generada por la Grabadora de escritorio.

Revisa cada paso antes de confiar en ella: los controles se identifican por su texto visible, y pueden necesitar ajuste si la app cambia de version o de idioma.

Los datos del servidor (nombre, usuario) salen del .env y no del codigo
-- ver .env.example. La contraseña nunca se graba: viene de la Bóveda de
credenciales.
"""
from __future__ import annotations

import re

from core.config import var
from engine.automation_base import AutomationResult, BaseAutomation
from engine.registry import registrar

SERVIDOR = var("VNC_SERVIDOR_ALT", "servidor.demo2")
USUARIO = var("VNC_USUARIO", "usuario.demo")

# pywinauto empareja el titulo como expresion regular: por eso el nombre
# del servidor se escapa antes de armarlo.
TITULO_AUTENTICACION = r"UltraVNC\ Viewer\ \-\ Authentication\ \ \ " + re.escape(SERVIDOR.upper()) + r":5900"


@registrar(nombre='ingresovnc2', disparador="manual", categoria="grabada")
class Ingresovnc2(BaseAutomation):
    def ejecutar(self) -> AutomationResult:
        self.escritorio.conectar_por_clase('Shell_SecondaryTrayWnd')
        self.escritorio.click_por_texto('UltraVNC Viewer', control_type='Button')
        self.escritorio.conectar_por_titulo('UltraVNC\\ Viewer\\ \\-\\ 1\\.6\\.4\\.0')
        self.escritorio.click_en(344, 83)  # ComboBox, sin texto identificable
        self.escritorio.escribir(SERVIDOR)
        self.escritorio.click_por_texto('Connect', control_type='Button')
        self.escritorio.conectar_por_titulo(TITULO_AUTENTICACION)
        self.escritorio.click_en(344, 29)  # Edit, sin texto identificable
        self.escritorio.escribir(USUARIO)
        self.escritorio.click_en(354, 88)  # campo de Edit -- su valor no se grabó por seguridad
        self.escritorio.escribir(self.credenciales.password)  # TODO: guarda esta contraseña en la Bóveda de credenciales (no se grabó en texto plano)
        self.escritorio.click_por_texto('Login', control_type='Button')
        self.escritorio.conectar_por_titulo('UltraVNC\\ Viewer\\ \\-\\ Information')
        self.escritorio.click_por_texto('Close', control_type='Button')
        return AutomationResult(success=True)
