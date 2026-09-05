"""Escribe una automatización en disco y la deja registrada y usable.

Son cuatro pasos —carpeta, `automation.py`, `__init__.py` y recarga del
módulo— y saltarse uno produce una carpeta que existe en disco pero no
aparece en la lista. Por eso están aquí una sola vez, y no repetidos en
cada sitio que crea automatizaciones (grabadora, asistente, autocorrector).

La validación del nombre también vive aquí; `engine.actions.recorder` la
reexporta por compatibilidad.
"""
from __future__ import annotations

import ast
import importlib
import re
import sys
from pathlib import Path

NOMBRE_VALIDO = re.compile(r"^[a-z][a-z0-9_]*$")

CARPETA_AUTOMATIZACIONES = Path("automations")


def nombre_de_clase(nombre_automatizacion: str) -> str:
    return "".join(parte.capitalize() for parte in nombre_automatizacion.split("_"))


def validar_nombre(nombre: str) -> None:
    if not NOMBRE_VALIDO.match(nombre):
        raise ValueError(
            "El nombre debe empezar con una letra minúscula y usar solo letras, números y guion bajo "
            "(ej. 'mi_proceso_web')."
        )


def clase_exportada(codigo: str, nombre: str) -> str | None:
    """Qué clase debe reexportar el `__init__.py` de esta automatización.

    Se LEE del código, no se deduce del nombre de la carpeta. Antes se
    escribía siempre `nombre_de_clase(nombre)`, lo que daba por hecho que
    la clase se llama igual que la carpeta en CamelCase. Cuando no coincide
    -- porque alguien renombró la clase en el editor, o porque el Agente IA
    la llamó de otra forma -- el `__init__.py` queda importando un nombre
    que no existe y la automatización muere con:

        ImportError: cannot import name 'DemoIaCalculadora' from
        'automations.demo_ia_calculadora.automation'

    Es el peor fallo posible: no se nota al guardar, solo al recargar; y
    antes de que `descubrir()` fuera tolerante, impedía que la app abriera.
    Se encontró ejecutando de verdad código generado por Gemini, que había
    llamado `CalcDemo` a la clase de la carpeta `demo_ia_calculadora`.

    Devuelve None si el archivo no define ninguna clase utilizable (o no
    compila): ahí no hay nada que reexportar y forzarlo sería inventar.
    """
    try:
        arbol = ast.parse(codigo)
    except SyntaxError:
        return None

    clases = [n for n in ast.walk(arbol) if isinstance(n, ast.ClassDef)]
    if not clases:
        return None

    # 1º la que lleva @registrar -- es la que el motor va a instanciar.
    for clase in clases:
        for decorador in clase.decorator_list:
            llamada = decorador.func if isinstance(decorador, ast.Call) else decorador
            if getattr(llamada, "id", getattr(llamada, "attr", "")) == "registrar":
                return clase.name

    # 2º la que hereda de BaseAutomation, por si el decorador falta.
    for clase in clases:
        if any(getattr(base, "id", "") == "BaseAutomation" for base in clase.bases):
            return clase.name

    # 3º la que coincide con el nombre de la carpeta, si existe de verdad.
    esperada = nombre_de_clase(nombre)
    return esperada if any(c.name == esperada for c in clases) else clases[0].name


def escribir_paquete(nombre: str, codigo: str, base: Path | None = None) -> Path:
    """Escribe automations/<nombre>/{automation.py,__init__.py} y ya.

    Separado de `guardar_automatizacion` porque escribir en disco e
    IMPORTAR son dos cosas distintas: importar ejecuta el archivo, y hay
    sitios (una prueba, un borrador) donde eso no se quiere.
    """
    validar_nombre(nombre)

    carpeta = (base or CARPETA_AUTOMATIZACIONES) / nombre
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / "automation.py"
    ruta.write_text(codigo, encoding="utf-8")

    clase = clase_exportada(codigo, nombre)
    if clase:
        contenido_init = f"from automations.{nombre}.automation import {clase}\n\n__all__ = [{clase!r}]\n"
    else:
        # Sin clase que exportar, un __init__.py vacío es correcto: el
        # decorador @registrar vive en automation.py y es ese módulo el
        # que importa el registry.
        contenido_init = f"# automations/{nombre}: sin clase que reexportar.\n"
    (carpeta / "__init__.py").write_text(contenido_init, encoding="utf-8")
    return ruta


def guardar_automatizacion(nombre: str, codigo: str, base: Path | None = None) -> Path:
    """Escribe el paquete y deja el módulo cargado en memoria.

    Devuelve la ruta del automation.py escrito. El `import`/`reload` final
    es lo que dispara el decorador `@registrar`: sin él la automatización
    está en disco pero el registry no la conoce hasta reiniciar la app.
    """
    ruta = escribir_paquete(nombre, codigo, base)

    modulo = f"automations.{nombre}.automation"
    if modulo in sys.modules:
        importlib.reload(sys.modules[modulo])
    else:
        importlib.import_module(modulo)

    # Import tarde a proposito: registry importa automation_base y la app
    # entera; hacerlo arriba convertiria a almacen (que es solo disco) en
    # un modulo pesado de importar.
    from engine.registry import olvidar_error

    olvidar_error(nombre)
    return ruta


def listar_en_disco(base: Path | None = None) -> list[str]:
    """Carpetas de automations/ que tienen un automation.py, ordenadas.

    Es a propósito distinto de `engine.registry.listar()`: el registry
    solo conoce las que se importaron BIEN. Justo la que hay que arreglar
    -- la que no compila -- no está ahí, y si el Agente IA solo mirara el
    registry no podría ofrecerse a corregir precisamente el caso que más
    lo necesita.
    """
    carpeta = base or CARPETA_AUTOMATIZACIONES
    if not carpeta.exists():
        return []
    return sorted(
        hijo.name
        for hijo in carpeta.iterdir()
        if hijo.is_dir() and not hijo.name.startswith("_") and (hijo / "automation.py").exists()
    )


def leer_codigo(nombre: str, base: Path | None = None) -> str:
    ruta = (base or CARPETA_AUTOMATIZACIONES) / nombre / "automation.py"
    return ruta.read_text(encoding="utf-8") if ruta.exists() else ""
