"""Le pide al agente 'Monitor de Fallas' en Microsoft 365 Copilot la tabla
de errores de hoy, y te la manda por Teams en un mensaje a ti mismo --
usando el botón "Copy" real de la tabla (aparece al pasar el mouse por
encima), así en Teams llega como una tabla de verdad, no como texto
reformateado a mano.

Disparador: cron diario a las 8:00 am -- pero como cualquier automatizacion
de esta plataforma, tambien puedes correrla cuando quieras (boton "Ejecutar
ahora" en la app, o `python manage.py ejecutar alerta_diaria_errores`).

Requiere que Microsoft 365 Copilot y Microsoft Teams ya esten abiertos
(con sesion iniciada) en esta maquina.

Configuracion (en tu .env, ver .env.example): CORREO_PROPIO y
NOMBRE_CHAT_PROPIO identifican tu chat contigo mismo en Teams.
"""
from __future__ import annotations

from core.config import var
from engine.automation_base import AutomationResult, BaseAutomation
from engine.registry import registrar

NOMBRE_AGENTE = "Monitor de Fallas"
CORREO_PROPIO = var("CORREO_PROPIO", "tu.correo@empresa.com")
NOMBRE_CHAT_PROPIO = var("NOMBRE_CHAT_PROPIO", "Tu Nombre (You)")


@registrar(nombre="alerta_diaria_errores", disparador="cron:0 8 * * *", categoria="notificaciones")
class AlertaDiariaErrores(BaseAutomation):
    def ejecutar(self) -> AutomationResult:
        self.copiloto.abrir_copilot()
        self.copiloto.clickear_agente(NOMBRE_AGENTE)
        self.copiloto.enviar_prompt(NOMBRE_AGENTE, "Dame una tabla con los errores de hoy.")

        resultado = self.copiloto.esperar_y_copiar_tabla(tiempo_maximo=60)
        if resultado.tipo != "tabla":
            raise RuntimeError(
                f"No se pudo copiar la tabla de errores de {NOMBRE_AGENTE} "
                f"(tipo={resultado.tipo}, detalle={resultado.detalle})"
            )
        self.logger.info("Tabla copiada (%d caracteres en texto plano de respaldo)", len(resultado.contenido))

        self.copiloto.abrir_teams()
        if not self.copiloto.abrir_chat_propio(CORREO_PROPIO, NOMBRE_CHAT_PROPIO):
            raise RuntimeError("No se encontró el chat contigo mismo en Teams")

        # contenido_para_escribir=None a proposito: se pega tal cual quedo
        # en el portapapeles tras el "Copy" real de Copilot (con su HTML),
        # no un texto armado a mano.
        enviado = self.copiloto.pegar_y_enviar(titulo_esperado=NOMBRE_CHAT_PROPIO)
        if not enviado:
            raise RuntimeError("La verificación antes de enviar falló -- no se mandó nada a Teams")

        return AutomationResult(success=True, data={"caracteres_enviados": len(resultado.contenido)})
