"""Mide si un prompt genera mejor código que otro. Con números, no opiniones.

    python tools/evaluar_prompts.py            # base vs base+prácticas
    python tools/evaluar_prompts.py --repeticiones 3
    python tools/evaluar_prompts.py --modelo gemini-3.5-flash

Cada tarea del banco tiene una trampa conocida: una forma de escribirla que
parece razonable y que se ha comprobado que FALLA al ejecutarse de verdad.
La puntuación mide si el modelo cae en ella.

Las comprobaciones son estáticas —sobre el AST y el texto del código— a
propósito: ejecutar cada respuesta contra las apps reales tardaría horas y
haría el resultado dependiente de qué ventanas hubiera abiertas. Lo que se
mide aquí es si el prompt guía al modelo lejos de errores ya conocidos, no
si el código funciona en esta máquina hoy.
"""
from __future__ import annotations

import argparse
import ast
import os
import re
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
os.chdir(RAIZ)


# --------------------------------------------------------------- el banco


@dataclass
class Tarea:
    nombre: str
    peticion: str
    trampa: str
    # Cada comprobación: (etiqueta, función(codigo) -> bool, puntos)
    comprobaciones: list = field(default_factory=list)


def _usa(codigo: str, *fragmentos: str) -> bool:
    return any(f in codigo for f in fragmentos)


def _compila(codigo: str) -> bool:
    try:
        ast.parse(codigo)
        return True
    except SyntaxError:
        return False


def _tiene_registrar(codigo: str) -> bool:
    return "@registrar" in codigo and "from engine.registry import" in codigo


def _hereda_base(codigo: str) -> bool:
    try:
        arbol = ast.parse(codigo)
    except SyntaxError:
        return False
    return any(
        isinstance(n, ast.ClassDef)
        and any(isinstance(b, ast.Name) and b.id == "BaseAutomation" for b in n.bases)
        for n in ast.walk(arbol)
    )


def _clics_por_glifo(codigo: str) -> bool:
    """click_por_texto('1') y compañía: el fallo medido en la Calculadora."""
    return bool(re.search(r"click_por_texto\(\s*['\"][0-9+\-*/=×÷]{1,2}['\"]", codigo))


def _escribe_en_select(codigo: str) -> bool:
    """Rellenar un <select> con escribir() deja el formulario vacío, sin error."""
    sospechosos = re.findall(r"self\.web\.escribir\(\s*['\"]([^'\"]+)", codigo)
    return any(re.search(r"select|combo|entidad|estado|dia|mes|sexo", s, re.I) for s in sospechosos)


def _password_en_codigo(codigo: str) -> bool:
    for llamada in re.findall(r"escribir\(\s*['\"]([^'\"]{4,})['\"]", codigo):
        if re.search(r"pass|clave|secret|contrase", llamada, re.I):
            return True
    return bool(re.search(r"(password|contrasena|contraseña)\s*=\s*['\"][^'\"]{4,}", codigo, re.I))


TAREAS = [
    Tarea(
        nombre="calculadora",
        peticion=(
            "Automatiza la Calculadora de Windows: ábrela si no está abierta, calcula 12 x 8 "
            "y deja el resultado en pantalla. Llama a la automatización 'calc_demo'."
        ),
        trampa="clicar los botones por su glifo ('1', '×') en vez del nombre de accesibilidad",
        comprobaciones=[
            ("no clica por glifo", lambda c: not _clics_por_glifo(c), 3),
            ("usa teclado o nombres reales",
             lambda c: _usa(c, "escribir(", "atajo(") or _usa(c, "Uno", "Multiplicar por", "Es igual a"), 2),
            ("conecta antes de actuar", lambda c: _usa(c, "iniciar_o_conectar", "conectar_por_titulo"), 1),
        ],
    ),
    Tarea(
        nombre="formulario_web",
        peticion=(
            "Automatiza un formulario web en https://ejemplo.test/alta: escribe el nombre en "
            "#nombre, elige el estado en el desplegable #claveEntidad (valor 'JC') y pulsa "
            "#enviar. Llama a la automatización 'alta_web'."
        ),
        trampa="rellenar el <select> con escribir() en vez de seleccionar()",
        comprobaciones=[
            ("usa seleccionar() para el <select>", lambda c: "self.web.seleccionar(" in c, 3),
            ("no escribe dentro del select", lambda c: not _escribe_en_select(c), 2),
            ("navega antes de interactuar", lambda c: "self.web.ir_a(" in c, 1),
        ],
    ),
    Tarea(
        nombre="campo_de_texto",
        peticion=(
            "En una app de escritorio llamada 'MiApp', haz clic en su único campo de texto "
            "(que ahora mismo muestra 'Buscar...') y escribe 'factura'. "
            "Llama a la automatización 'buscar_app'."
        ),
        trampa="localizar el campo por su contenido en vez de por su tipo",
        comprobaciones=[
            ("usa click_por_tipo para el campo", lambda c: "click_por_tipo(" in c, 3),
            ("no localiza por el contenido del campo",
             lambda c: "click_por_texto('Buscar" not in c and 'click_por_texto("Buscar' not in c, 2),
            ("conecta antes de actuar", lambda c: _usa(c, "conectar_por_titulo", "iniciar_o_conectar"), 1),
        ],
    ),
    Tarea(
        nombre="login_con_credencial",
        peticion=(
            "Inicia sesión en https://portal.test: escribe el usuario en #user, la contraseña "
            "en #pass y pulsa #entrar. Llama a la automatización 'login_portal'."
        ),
        trampa="escribir la contraseña literal en el código en vez de usar la Bóveda",
        comprobaciones=[
            ("usa self.credenciales", lambda c: "self.credenciales" in c, 3),
            ("no deja una contraseña literal", lambda c: not _password_en_codigo(c), 3),
        ],
    ),
]

# Comprobaciones que se aplican a TODAS las tareas.
COMUNES = [
    ("compila", _compila, 2),
    ("lleva @registrar", _tiene_registrar, 1),
    ("hereda de BaseAutomation", _hereda_base, 1),
]


# ---------------------------------------------------------------- ejecución


def evaluar(codigo: str, tarea: Tarea) -> tuple[int, int, list[str]]:
    obtenidos = maximo = 0
    fallos = []
    for etiqueta, comprobar, puntos in COMUNES + tarea.comprobaciones:
        maximo += puntos
        try:
            bien = bool(comprobar(codigo))
        except Exception:  # noqa: BLE001 - una comprobación rota no debe tumbar el banco
            bien = False
        if bien:
            obtenidos += puntos
        else:
            fallos.append(etiqueta)
    return obtenidos, maximo, fallos


def generar(peticion: str, modelo: str | None, con_practicas: bool) -> str:
    from core import gemini_client
    from core.gemini_client import GeminiClient, construir_contexto_proyecto, extraer_codigo_python

    original = gemini_client._cargar_practicas
    if not con_practicas:
        # La variante "base": el prompt del sistema SIN lo aprendido.
        gemini_client._cargar_practicas = lambda: ""
    try:
        respuesta = GeminiClient(modelo=modelo).generar(
            peticion, contexto=construir_contexto_proyecto()
        )
    finally:
        gemini_client._cargar_practicas = original
    return extraer_codigo_python(respuesta.texto) or ""


def main() -> int:
    analizador = argparse.ArgumentParser(description=__doc__)
    analizador.add_argument("--repeticiones", type=int, default=1)
    analizador.add_argument("--modelo", default=None)
    analizador.add_argument("--tarea", default=None, help="evalúa solo esta")
    opciones = analizador.parse_args()

    from core.gemini_client import tiene_api_key

    if not tiene_api_key():
        print("Falta la API key de Gemini. Configúrala en el Asistente IA o en el .env.")
        return 1

    tareas = [t for t in TAREAS if opciones.tarea in (None, t.nombre)]
    if not tareas:
        print(f"No hay ninguna tarea llamada {opciones.tarea!r}.")
        return 1

    variantes = {"base": False, "con prácticas": True}
    puntajes: dict[str, list[float]] = {v: [] for v in variantes}
    detalle: dict[str, list[str]] = {v: [] for v in variantes}

    for tarea in tareas:
        print(f"\n=== {tarea.nombre} ===")
        print(f"    trampa: {tarea.trampa}")
        for variante, con_practicas in variantes.items():
            for repeticion in range(opciones.repeticiones):
                inicio = time.time()
                try:
                    codigo = generar(tarea.peticion, opciones.modelo, con_practicas)
                except Exception as exc:  # noqa: BLE001 - un fallo de red no debe tirar el banco
                    print(f"  {variante:14s} #{repeticion + 1}  ERROR: {type(exc).__name__}: {exc}")
                    continue

                obtenidos, maximo, fallos = evaluar(codigo, tarea)
                porcentaje = 100 * obtenidos / maximo if maximo else 0
                puntajes[variante].append(porcentaje)
                if fallos:
                    detalle[variante].append(f"{tarea.nombre}: {', '.join(fallos)}")
                print(
                    f"  {variante:14s} #{repeticion + 1}  {obtenidos:2d}/{maximo}  "
                    f"({porcentaje:5.1f}%)  {time.time() - inicio:5.1f}s"
                    + (f"  falla: {', '.join(fallos)}" if fallos else "  todo bien")
                )

    print("\n" + "=" * 62)
    print(f"{'variante':16s} {'media':>8s} {'muestras':>10s}")
    print("-" * 62)
    for variante, valores in puntajes.items():
        if valores:
            print(f"{variante:16s} {statistics.mean(valores):7.1f}% {len(valores):10d}")
        else:
            print(f"{variante:16s} {'—':>8s} {0:10d}")

    base, mejorada = puntajes["base"], puntajes["con prácticas"]
    if base and mejorada:
        diferencia = statistics.mean(mejorada) - statistics.mean(base)
        print(f"\ndiferencia: {diferencia:+.1f} puntos porcentuales")
        if len(base) < 8:
            print(
                "Con tan pocas muestras esto es una señal, no una medición: "
                "usa --repeticiones 3 o más antes de concluir nada."
            )

    for variante, lineas in detalle.items():
        if lineas:
            print(f"\nfallos de «{variante}»:")
            for linea in sorted(set(lineas)):
                print("  -", linea)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
