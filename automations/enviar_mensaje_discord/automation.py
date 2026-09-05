from __future__ import annotations

import re
from core.config import var
from engine.automation_base import AutomationResult, BaseAutomation
from engine.registry import registrar


@registrar(nombre="enviar_mensaje_discord", disparador="manual", categoria="general")
class EnviarMensajeDiscord(BaseAutomation):
    """Automatización para abrir Discord, situarse en un canal y enviar un mensaje."""

    def ejecutar(self) -> AutomationResult:
        # 1. Obtener la ruta o comando para lanzar Discord desde la configuración (.env)
        comando_discord = var("DISCORD_COMANDO", "discord")
        canal_destino = var("DISCORD_CANAL", "general")
        mensaje = var("DISCORD_MENSAJE", "hola")

        self.logger.info("Conectando con la aplicación Discord...")
        # 2. Iniciar o conectar con la ventana de Discord (aumentando timeout a 30s)
        self.escritorio.iniciar_o_conectar(
            comando=comando_discord,
            titulo_regex=r".*Discord.*",
            tiempo_espera=30,
            nombre_aplicacion="Discord",
        )

        # Pausa para asegurar que la interfaz esté lista y con foco
        self.escritorio.esperar(2)

        self.logger.info(f"Navegando al canal '{canal_destino}' mediante el buscador rápido...")
        # 3. Abrir el Quick Switcher / Buscador rápido de Discord con Ctrl + K
        self.escritorio.atajo("^k")
        self.escritorio.esperar(1)

        # 4. Escribir el nombre del canal y presionar Enter para ingresar
        self.escritorio.escribir(canal_destino)
        self.escritorio.esperar(1)
        self.escritorio.atajo("{ENTER}")
        self.escritorio.esperar(2)

        self.logger.info("Enviando mensaje al chat...")
        # 5. Escribir el mensaje en el área de texto activa y presionar Enter
        self.escritorio.escribir(mensaje)
        self.escritorio.esperar(0.5)
        self.escritorio.atajo("{ENTER}")

        self.logger.info("Mensaje enviado correctamente.")
        return AutomationResult(
            success=True,
            message=f"Mensaje '{mensaje}' enviado exitosamente al canal '{canal_destino}' en Discord.",
            data={"canal": canal_destino, "mensaje": mensaje},
        )
