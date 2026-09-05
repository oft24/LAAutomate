from __future__ import annotations

from pathlib import Path
from core.config import var
from core.config import BASE_DIR
from core.gemini_client import validar_capturas
from engine.automation_base import AutomationResult, BaseAutomation
from engine.registry import registrar


@registrar(
    nombre="buscar_perros_santa_discord",
    disparador="manual",
    categoria="general",
)
class BuscarPerrosSantaDiscord(BaseAutomation):
    def ejecutar(self) -> AutomationResult:
        # Conserva la navegación que funcionaba; añade un archivo real al envío.
        ruta_configurada = var("DISCORD_IMAGEN_LOCAL").strip()
        if ruta_configurada:
            ruta = Path(ruta_configurada).resolve(strict=True)
        else:
            import time
            self.web.ir_a("https://search.brave.com/images?q=imagenes+de+perros+con+gorro+de+santa+claus")
            ruta = self.web.guardar_imagen_resultado(
                BASE_DIR / "datos" / "discord" / f"perro-santa-{time.time_ns()}.png"
            )
        if not ruta.is_file() or ruta.stat().st_size > 12 * 1024 * 1024:
            raise ValueError("La imagen debe ser un archivo local de hasta 12 MB.")
        validar_capturas([ruta])
        self.escritorio.iniciar_o_conectar(
            var("DISCORD_COMANDO", "discord"), r".*Discord.*",
            tiempo_espera=30, nombre_aplicacion="Discord",
        )
        self.escritorio.atajo("^k")
        self.escritorio.esperar(1)
        self.escritorio.escribir("chat-general-no-mudae")
        self.escritorio.esperar(1)
        self.escritorio.atajo("{ENTER}")
        self.escritorio.esperar(2)
        confirmado = self.escritorio.enviar_imagen_discord(ruta)

        return AutomationResult(
            success=confirmado,
            message=("Imagen enviada: apareció un nuevo enlace al adjunto." if confirmado else
                     "Se pulsó Enviar, pero no se pudo verificar el adjunto. No se reintentará automáticamente."),
            data={"enviado": True if confirmado else None, "requiere_revision": not confirmado, "archivo": ruta.name},
        )
