"""Anota cada acción que ejecuta una automatización, en orden.

El traceback dice en qué línea murió; la bitácora dice qué pasó antes. Es
la diferencia entre «ElementNotFoundError en la línea 34» y «conectó con
la Calculadora, escribió 12, y el clic siguiente no encontró el botón».

No sustituye al log: lleva solo las acciones, ya resumidas, que es lo que
cabe en el contexto de un modelo.
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field

# Cuántas acciones se guardan. Un lote largo puede hacer miles; para
# diagnosticar sirven las últimas, y guardar todo solo gasta memoria.
MAXIMO_PASOS = 200

# Cuántas se le enseñan al modelo por defecto. Más de 20 empieza a diluir
# lo importante -- el fallo casi siempre está en las últimas tres.
PASOS_PARA_DIAGNOSTICO = 20

# Argumentos que NO se anotan nunca, ni resumidos. `escribir` recibe el
# valor tecleado, que puede ser una contraseña de la Bóveda.
ACCIONES_SENSIBLES = ("escribir", "escribir_credencial", "pegar_y_enviar")

MAX_LARGO_ARGUMENTO = 60


@dataclass
class Paso:
    segundo: float
    accion: str
    argumentos: str
    ok: bool = True
    error: str = ""

    def __str__(self) -> str:
        estado = "" if self.ok else f"  -> FALLÓ: {self.error}"
        return f"[{self.segundo:6.1f}s] {self.accion}({self.argumentos}){estado}"


@dataclass
class Bitacora:
    inicio: float = field(default_factory=time.monotonic)
    pasos: list[Paso] = field(default_factory=list)
    pausada: bool = False

    @contextmanager
    def en_pausa(self):
        """No anota nada mientras dure el bloque.

        Lo usa el runner al fallar: sus capturas de diagnostico
        (`screenshot_error`, `capturar_pantalla`) pasan por los mismos
        objetos espiados que las acciones de la automatizacion, asi que se
        colaban en la bitacora -- y quedaban como las ULTIMAS acciones,
        justo donde el modelo mira primero para entender que paso. La
        limpieza del motor no es algo que la automatizacion hiciera.
        """
        anterior = self.pausada
        self.pausada = True
        try:
            yield self
        finally:
            self.pausada = anterior

    def registrar(self, accion: str, argumentos: str, ok: bool = True, error: str = "") -> None:
        if self.pausada:
            return
        self.pasos.append(Paso(time.monotonic() - self.inicio, accion, argumentos, ok, error))
        if len(self.pasos) > MAXIMO_PASOS:
            # Se tira por el principio: el final es lo que explica el fallo.
            del self.pasos[: len(self.pasos) - MAXIMO_PASOS]

    def ultimos(self, cuantos: int = PASOS_PARA_DIAGNOSTICO) -> list[Paso]:
        return self.pasos[-cuantos:]

    def como_texto(self, cuantos: int = PASOS_PARA_DIAGNOSTICO) -> str:
        if not self.pasos:
            return "(la automatización no llegó a ejecutar ninguna acción)"
        recientes = self.ultimos(cuantos)
        cabecera = (
            f"Últimas {len(recientes)} acciones de {len(self.pasos)}:"
            if len(self.pasos) > len(recientes)
            else f"Las {len(recientes)} acciones que ejecutó:"
        )
        return cabecera + "\n" + "\n".join(str(p) for p in recientes)

    def limpiar(self) -> None:
        self.pasos.clear()
        self.inicio = time.monotonic()


def _resumir(valor) -> str:
    texto = repr(valor)
    return texto if len(texto) <= MAX_LARGO_ARGUMENTO else texto[: MAX_LARGO_ARGUMENTO - 3] + "…'"


def describir_argumentos(accion: str, args: tuple, kwargs: dict) -> str:
    """Convierte los argumentos de una llamada en algo legible y seguro.

    Para las acciones sensibles se anota la LONGITUD del texto en vez del
    texto: saber que se tecleó algo de 12 caracteres basta para
    diagnosticar, y una contraseña nunca debe acabar en un archivo de
    diagnóstico ni, mucho menos, viajando a un modelo.
    """
    if any(accion.endswith(s) for s in ACCIONES_SENSIBLES):
        largo = len(str(args[0])) if args and args[0] is not None else 0
        return f"<texto de {largo} caracteres, no registrado>"

    partes = [_resumir(a) for a in args]
    partes += [f"{k}={_resumir(v)}" for k, v in kwargs.items()]
    return ", ".join(partes)


class Espia:
    """Envuelve un objeto de acciones y anota cada llamada en la bitácora.

    Se usa `__getattr__` en vez de generar métodos uno a uno para que
    NUNCA haya que tocar este archivo al añadir una acción nueva a
    `engine/actions/`: cualquier método público del objeto envuelto queda
    anotado automáticamente. Los atributos que no son funciones (como
    `self.web.driver`) se devuelven tal cual, sin envolver.
    """

    def __init__(self, objetivo, prefijo: str, bitacora: Bitacora) -> None:
        # Con nombres "privados" para no chocar con los del objeto envuelto.
        object.__setattr__(self, "_objetivo", objetivo)
        object.__setattr__(self, "_prefijo", prefijo)
        object.__setattr__(self, "_bitacora", bitacora)

    def __getattr__(self, nombre: str):
        atributo = getattr(object.__getattribute__(self, "_objetivo"), nombre)
        if not callable(atributo) or nombre.startswith("_"):
            return atributo

        prefijo = object.__getattribute__(self, "_prefijo")
        bitacora = object.__getattribute__(self, "_bitacora")

        def _envuelto(*args, **kwargs):
            accion = f"{prefijo}.{nombre}"
            descripcion = describir_argumentos(accion, args, kwargs)
            try:
                resultado = atributo(*args, **kwargs)
            except Exception as exc:
                bitacora.registrar(accion, descripcion, ok=False, error=f"{type(exc).__name__}: {exc}")
                raise
            bitacora.registrar(accion, descripcion)
            return resultado

        return _envuelto

    def __setattr__(self, nombre: str, valor) -> None:
        setattr(object.__getattribute__(self, "_objetivo"), nombre, valor)
