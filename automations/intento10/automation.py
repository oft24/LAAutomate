"""Automatizacion generada por la Grabadora de escritorio.

Revisa cada paso antes de confiar en ella: los controles se identifican por su texto visible, y pueden necesitar ajuste si la app cambia de version o de idioma.

Los datos del servidor (nombre, IP, usuario) salen del .env y no del
codigo -- ver .env.example. La contraseña nunca se graba: viene de la
Bóveda de credenciales.
"""
from __future__ import annotations

import re

from core.config import var
from engine.automation_base import AutomationResult, BaseAutomation
from engine.registry import registrar

SERVIDOR = var("VNC_SERVIDOR", "servidor.demo")
USUARIO = var("VNC_USUARIO", "usuario.demo")
IP_SERVIDOR = var("VNC_IP", "127.0.0.1")

# pywinauto empareja el titulo como expresion regular: por eso el nombre
# del servidor se escapa antes de armarlo.
TITULO_AUTENTICACION = r"UltraVNC\ Viewer\ \-\ Authentication\ \ \ " + re.escape(SERVIDOR.upper()) + r":5900"
TITULO_SESION = (
    re.escape(SERVIDOR) + r"\ \(\ " + re.escape(IP_SERVIDOR) + r"\ \)\ \-\ service\ mode\ viewonly"
)


@registrar(nombre='intento10', disparador="manual", categoria="grabada")
class Intento10(BaseAutomation):
    def ejecutar(self) -> AutomationResult:
        self.escritorio.conectar_por_clase('Shell_TrayWnd')
        self.escritorio.click_por_texto('UltraVNC Viewer', control_type='Button')
        self.escritorio.conectar_por_titulo('UltraVNC\\ Viewer\\ \\-\\ 1\\.6\\.4\\.0')
        self.escritorio.click_en(338, 97)  # Edit, sin texto identificable
        self.escritorio.escribir(SERVIDOR)
        self.escritorio.click_por_texto('Connect', control_type='Button')
        self.escritorio.conectar_por_titulo(TITULO_AUTENTICACION)
        self.escritorio.click_en(436, 23)  # Edit, sin texto identificable
        self.escritorio.escribir(USUARIO)
        self.escritorio.click_en(409, 85)  # campo de Edit -- su valor no se grabó por seguridad
        self.escritorio.escribir(self.credenciales.password)  # TODO: guarda esta contraseña en la Bóveda de credenciales (no se grabó en texto plano)
        self.escritorio.click_por_texto('Login', control_type='Button')
        self.escritorio.conectar_por_titulo(TITULO_SESION)
        self.escritorio.click_por_texto('UltraVNC Viewer', control_type='Pane')
        self.escritorio.click_por_texto('Close', control_type='Button')
        return AutomationResult(success=True)
