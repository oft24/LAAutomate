"""Ejecuta una automatización y, si falla, intenta repararla y reanudar.

El ciclo por intento:

1. Correr con la bitácora activa.
2. Si falla: captura del momento exacto + traceback + últimas acciones.
3. Mandarle todo eso a Gemini junto con el código y `docs/PRACTICAS.md`.
4. Validar el arreglo (que compile, que conserve `@registrar`, la clase y
   el método `ejecutar`), guardarlo y recargar el módulo.
5. Volver a correr.

Como máximo 5 intentos. Y se para antes si el modelo devuelve el mismo
código dos veces seguidas: insistir con un arreglo que no cambia nada solo
gasta cuota y tiempo.

**No corre solo en las ejecuciones programadas.** Que un cron reescriba
código a las 3 de la mañana sin que nadie mire es una forma excelente de
despertarse con una automatización que hace algo distinto de lo que
hacía. Se activa en las ejecuciones manuales, donde hay una persona
mirando el resultado.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from core.config import LOGS_DIR
from core.gemini_client import (
    ErrorGemini,
    GeminiClient,
    es_modelo_de_texto,
    extraer_codigo_python,
    listar_modelos,
    modelo_por_defecto,
    ordenar_para_elegir,
    tiene_api_key,
)
from core.logger import get_logger
from engine import practicas
from engine.almacen import guardar_automatizacion, leer_codigo
from engine.automation_base import AutomationResult
from engine.bitacora import Bitacora
from engine.registry import AutomationSpec, obtener

logger = get_logger(__name__)

MAX_INTENTOS = 5

# Dónde se guarda el rastro de cada reparación: las capturas de cada
# intento y el código que se probó. Sobrevive a la sesión a propósito --
# es lo que permite entender después por qué la automatización acabó
# escrita como está.
CARPETA_REPARACIONES = LOGS_DIR / "reparaciones"


@dataclass
class Intento:
    """Un ciclo fallo → diagnóstico → arreglo."""

    numero: int
    error: str
    acciones: str
    capturas: list[Path] = field(default_factory=list)
    diagnostico: str = ""
    cambios: list[str] = field(default_factory=list)
    practica: str = ""
    codigo_propuesto: str = ""
    aplicado: bool = False
    motivo_descarte: str = ""


@dataclass
class Reparacion:
    """Todo lo que pasó, para poder contárselo a una persona."""

    automatizacion: str
    intentos: list[Intento] = field(default_factory=list)
    resultado: AutomationResult | None = None
    codigo_original: str = ""
    carpeta: Path | None = None

    @property
    def exito(self) -> bool:
        return bool(self.resultado and self.resultado.success)

    @property
    def reparada(self) -> bool:
        """Falló al principio pero acabó funcionando tras un arreglo."""
        return self.exito and any(i.aplicado for i in self.intentos)

    def resumen(self) -> str:
        if self.exito and not self.intentos:
            return "Funcionó a la primera; no hubo nada que reparar."
        if self.reparada:
            aplicados = sum(1 for i in self.intentos if i.aplicado)
            return (
                f"Reparada tras {aplicados} arreglo(s) en {len(self.intentos)} intento(s). "
                f"Último diagnóstico: {self.intentos[-1].diagnostico or 'sin diagnóstico'}"
            )
        return (
            f"No se pudo reparar en {len(self.intentos)} intento(s). "
            f"Último error: {self.resultado.message if self.resultado else 'desconocido'}"
        )


class Autocorrector:
    """Corre una automatización y la repara si falla."""

    def __init__(
        self,
        runner,
        modelo: str | None = None,
        max_intentos: int = MAX_INTENTOS,
        on_progreso=None,
    ) -> None:
        self.runner = runner
        self.modelo = modelo
        self.max_intentos = max(1, min(int(max_intentos), MAX_INTENTOS))
        # Modelos de reserva, por si el elegido se satura. Se resuelven la
        # primera vez que hacen falta, no en el constructor: construir un
        # Autocorrector no deberia costar una llamada de red.
        self._reservas: list[str] | None = None
        # Callback opcional (texto -> None) para ir contando lo que pasa
        # mientras pasa: una reparación tarda minutos y el silencio es
        # indistinguible de un cuelgue.
        self.on_progreso = on_progreso

    # ------------------------------------------------------------ público

    def ejecutar(self, spec: AutomationSpec) -> Reparacion:
        nombre = spec.nombre
        reparacion = Reparacion(automatizacion=nombre, codigo_original=leer_codigo(nombre))
        reparacion.carpeta = self._carpeta_de_sesion(nombre)

        for numero in range(1, self.max_intentos + 1):
            etiqueta = "" if numero == 1 else f"_intento{numero}"
            self._contar(f"Ejecutando {nombre} (intento {numero} de {self.max_intentos})…")

            bitacora = Bitacora()
            resultado = self.runner.ejecutar(spec, bitacora=bitacora, etiqueta_captura=etiqueta)
            reparacion.resultado = resultado

            if resultado.success:
                self._contar(
                    "Funcionó." if numero == 1 else f"Funcionó tras {numero - 1} arreglo(s)."
                )
                self._recordar_lo_aprendido(reparacion)
                return reparacion

            intento = Intento(
                numero=numero,
                error=resultado.message,
                acciones=resultado.data.get("acciones", bitacora.como_texto()),
                capturas=self._capturas_de(resultado),
            )
            reparacion.intentos.append(intento)
            self._archivar(reparacion, intento)

            if numero == self.max_intentos:
                self._contar(f"Se agotaron los {self.max_intentos} intentos.")
                break
            if not tiene_api_key():
                intento.motivo_descarte = "no hay API key de Gemini configurada"
                self._contar("Falló, pero no hay API key: no puedo intentar repararla.")
                break

            self._contar(f"Falló: {resultado.message[:120]}  →  pidiendo un arreglo…")
            if not self._reparar(nombre, intento):
                break

            spec = obtener(nombre)  # el módulo se recargó: hay que releer el spec

        self._recordar_lo_aprendido(reparacion)
        return reparacion

    # ------------------------------------------------------------ privado

    def _reparar(self, nombre: str, intento: Intento) -> bool:
        """Pide el arreglo, lo valida y lo guarda. False = no seguir."""
        codigo_actual = leer_codigo(nombre)
        prompt = self._prompt(nombre, codigo_actual, intento)
        try:
            respuesta = self._preguntar(prompt, intento.capturas)
        except ErrorGemini as exc:
            intento.motivo_descarte = f"Gemini no pudo responder: {exc}"
            self._contar(intento.motivo_descarte)
            return False

        intento.diagnostico = self._seccion(respuesta, "DIAGNOSTICO")
        intento.practica = self._seccion(respuesta, "PRACTICA")
        propuesto = extraer_codigo_python(respuesta)

        if not propuesto:
            intento.motivo_descarte = "la respuesta no traía ningún bloque de código"
            self._contar(intento.motivo_descarte)
            return False

        intento.codigo_propuesto = propuesto

        if propuesto.strip() == codigo_actual.strip():
            # Insistir con un arreglo que no cambia nada solo gasta cuota.
            intento.motivo_descarte = "el arreglo era idéntico al código actual"
            self._contar("El modelo devolvió el mismo código: no tiene sentido reintentar.")
            return False

        try:
            guardar_automatizacion(nombre, propuesto)
        except Exception as exc:  # noqa: BLE001 - un arreglo malo no debe tumbar el ciclo
            intento.motivo_descarte = f"el arreglo no se pudo cargar: {type(exc).__name__}: {exc}"
            self._contar(intento.motivo_descarte)
            self._restaurar(nombre, codigo_actual)
            return False

        intento.aplicado = True
        intento.cambios = self._lineas(self._seccion(respuesta, "CAMBIOS"))
        self._contar(f"Arreglo aplicado: {intento.diagnostico[:140] or 'sin diagnóstico'}")
        return True

    def _preguntar(self, prompt: str, capturas) -> str:
        """Pide el arreglo, cambiando de modelo si el elegido se satura.

        El cliente ya reintenta dos veces sobre el MISMO modelo, que cubre
        el pico pasajero. Esto cubre lo otro: que ese modelo esté saturado
        de forma sostenida. Se comprobó con `gemini-3.7-flash`, que
        devolvió 503 «high demand» y dejó una reparación a medias.
        """
        ultimo: ErrorGemini | None = None
        for modelo in self._modelos_a_probar():
            try:
                # .texto y no la respuesta entera: generar() devuelve un
                # RespuestaGemini (texto + modelo + tokens), no una cadena.
                return GeminiClient(modelo=modelo).generar(prompt, capturas=capturas).texto
            except ErrorGemini as exc:
                ultimo = exc
                if not self._es_saturacion(exc):
                    raise
                self._contar(f"{modelo} está saturado; probando con otro modelo…")
        raise ultimo if ultimo else ErrorGemini("no hay ningún modelo disponible")

    @staticmethod
    def _es_saturacion(exc: ErrorGemini) -> bool:
        """¿Merece la pena probar con OTRO modelo?

        Sí cuando el problema es de ese modelo concreto: saturación, cuota,
        o que tardó más de la cuenta —se midió un `Read timed out` a los
        120 s con un modelo de razonamiento, un prompt grande y una captura
        adjunta; un Flash habría contestado—.

        No cuando el problema es de la cuenta: una clave inválida o un
        permiso que falta fallarían igual en todos, y recorrer la lista
        solo gastaría tiempo y cuota.
        """
        texto = str(exc).lower()
        return any(
            pista in texto
            for pista in ("saturado", "high demand", "cuota", "timed out", "no respondió")
        )

    def _modelos_a_probar(self) -> list[str]:
        """El modelo elegido primero, y detrás los mejores de la cuenta."""
        if self._reservas is not None:
            return self._reservas

        elegido = [self.modelo] if self.modelo else []
        try:
            disponibles = listar_modelos()
            preferido = modelo_por_defecto(disponibles)
            utiles = [
                m.nombre
                for m in ordenar_para_elegir(disponibles)
                if es_modelo_de_texto(m.nombre)
            ]
            orden = elegido + [preferido] + utiles
        except ErrorGemini:
            # Sin lista (sin red, sin permiso) se sigue con lo que haya:
            # no poder enumerar modelos no debe impedir intentar el arreglo.
            orden = elegido or [None]

        vistos, unicos = set(), []
        for nombre in orden:
            if nombre not in vistos:
                vistos.add(nombre)
                unicos.append(nombre)
        # Tres como mucho: si tres modelos distintos estan saturados, el
        # problema no es el modelo y seguir probando solo gasta tiempo.
        self._reservas = unicos[:3]
        return self._reservas

    def _restaurar(self, nombre: str, codigo: str) -> None:
        """Deja el archivo como estaba si el arreglo no carga.

        Sin esto, un intento fallido deja la automatización PEOR que antes:
        con código que ni siquiera importa.
        """
        try:
            guardar_automatizacion(nombre, codigo)
        except Exception:
            logger.exception("No se pudo restaurar %s tras un arreglo fallido", nombre)

    def _prompt(self, nombre: str, codigo: str, intento: Intento) -> str:
        partes = [
            f"La automatización «{nombre}» falló al ejecutarse. Repárala.",
            "",
            "## Error",
            "```",
            intento.error[:2000],
            "```",
            "",
            "## Qué estaba haciendo (bitácora de acciones)",
            "```",
            intento.acciones[:4000],
            "```",
            "",
            "## Código actual",
            "```python",
            codigo.rstrip(),
            "```",
        ]
        if intento.capturas:
            partes += [
                "",
                "## Captura del momento del fallo",
                "La imagen adjunta es la pantalla en el instante exacto del error. "
                "Úsala para ver qué había realmente delante: qué ventana estaba al "
                "frente, si apareció un diálogo inesperado, o si el control que se "
                "buscaba se llama distinto de lo que el código supone.",
            ]

        aprendido = practicas.leer()
        if aprendido:
            partes += ["", "## Prácticas ya aprendidas en este proyecto", aprendido]

        partes += [
            "",
            "## Cómo responder",
            "Responde EXACTAMENTE con estas cuatro secciones, en este orden:",
            "",
            "DIAGNOSTICO: la causa REAL en una o dos frases (no el síntoma).",
            "CAMBIOS: una línea por cada cambio que hiciste.",
            "PRACTICA: UNA regla accionable y general que evitaría este fallo en el "
            "futuro, en una sola frase. Si no aprendiste nada nuevo, escribe «ninguna».",
            "",
            "Y después un único bloque ```python con el archivo automation.py COMPLETO "
            "y corregido. Conserva el nombre en @registrar, el nombre de la clase y "
            "todo lo que ya funcionaba: cambia lo mínimo necesario.",
        ]
        return "\n".join(partes)

    @staticmethod
    def _seccion(texto: str, etiqueta: str) -> str:
        """Saca el contenido de una sección con nombre de la respuesta.

        Tolerante a propósito: el modelo puede escribir «DIAGNOSTICO:»,
        «**DIAGNOSTICO**:» o ponerlo como encabezado. Exigir un formato
        exacto haría fallar la reparación por un asterisco.
        """
        import re

        patron = rf"[*#\s]*{etiqueta}[*\s]*:?\s*(.+?)(?=\n[*#\s]*(?:DIAGNOSTICO|CAMBIOS|PRACTICA)\b|\n```|$)"
        encontrado = re.search(patron, texto, re.IGNORECASE | re.DOTALL)
        return " ".join(encontrado.group(1).split()) if encontrado else ""

    @staticmethod
    def _lineas(texto: str) -> list[str]:
        partes = [t.strip(" -*•\t") for t in texto.replace(";", "\n").splitlines()]
        return [p for p in partes if p]

    @staticmethod
    def _capturas_de(resultado: AutomationResult) -> list[Path]:
        rutas = []
        for clave in ("captura_web", "captura_escritorio"):
            valor = resultado.data.get(clave)
            if valor and Path(valor).exists():
                rutas.append(Path(valor))
        return rutas

    def _carpeta_de_sesion(self, nombre: str) -> Path:
        carpeta = CARPETA_REPARACIONES / f"{nombre}_{datetime.now():%Y%m%d_%H%M%S}"
        carpeta.mkdir(parents=True, exist_ok=True)
        return carpeta

    def _archivar(self, reparacion: Reparacion, intento: Intento) -> None:
        """Guarda las capturas y el código de este intento.

        Las capturas se COPIAN: las originales las pisa la ejecución
        siguiente, y comparar el antes y el después es justo lo que hace
        falta para saber si un arreglo avanzó.
        """
        if reparacion.carpeta is None:
            return
        copiadas = []
        for indice, captura in enumerate(intento.capturas):
            destino = reparacion.carpeta / f"intento{intento.numero}_{indice}{captura.suffix}"
            try:
                shutil.copy2(captura, destino)
                copiadas.append(destino)
            except OSError:
                copiadas.append(captura)
        intento.capturas = copiadas or intento.capturas

        try:
            (reparacion.carpeta / f"intento{intento.numero}_error.txt").write_text(
                f"{intento.error}\n\n{intento.acciones}\n", encoding="utf-8"
            )
        except OSError:
            pass

    def _recordar_lo_aprendido(self, reparacion: Reparacion) -> None:
        """Anota en PRACTICAS.md lo que se aprendió, si la reparación sirvió.

        Solo cuando funcionó: una «lección» sacada de un arreglo que no
        arregló nada es peor que ninguna, porque contamina el prompt de
        todas las reparaciones siguientes.
        """
        if not reparacion.reparada:
            return
        for intento in reversed(reparacion.intentos):
            if not intento.aplicado or not intento.practica:
                continue
            if intento.practica.strip().lower().startswith("ninguna"):
                continue
            if practicas.anotar(intento.practica, reparacion.automatizacion, intento.error):
                self._contar(f"Práctica aprendida y anotada: {intento.practica[:120]}")
            return

    def _contar(self, mensaje: str) -> None:
        logger.info(mensaje)
        if self.on_progreso:
            try:
                self.on_progreso(mensaje)
            except Exception:  # noqa: BLE001 - un fallo pintando no debe romper la reparación
                pass
