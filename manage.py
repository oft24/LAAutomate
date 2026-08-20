"""CLI para crear y probar automatizaciones sin abrir la app de escritorio.

    python manage.py listar
    python manage.py ejecutar alerta_diaria_errores
    python manage.py nueva mi_automatizacion
    python manage.py historial alerta_diaria_errores
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from engine.registry import descubrir, listar as listar_registro
from engine.runner import Runner

_PLANTILLA_AUTOMATION = '''"""Automatizacion {nombre}."""
from __future__ import annotations

from engine.automation_base import AutomationResult, BaseAutomation
from engine.registry import registrar


@registrar(nombre={nombre!r}, disparador="manual", categoria="general")
class {clase}(BaseAutomation):
    def ejecutar(self) -> AutomationResult:
        # self.web / self.excel / self.http / self.correo / self.escritorio / self.copiloto
        raise NotImplementedError("Escribe aqui la logica de {nombre}")
'''


def cmd_listar(_args: argparse.Namespace) -> None:
    descubrir()
    specs = listar_registro()
    if not specs:
        print("No hay automatizaciones registradas en /automations")
        return
    for spec in specs:
        print(f"{spec.nombre:<28} categoria={spec.categoria:<12} disparador={spec.disparador}")


def cmd_ejecutar(args: argparse.Namespace) -> None:
    descubrir()
    try:
        from engine.registry import obtener

        spec = obtener(args.nombre)
    except KeyError:
        print(f"No existe la automatizacion '{args.nombre}'. Usa 'python manage.py listar'.")
        sys.exit(1)

    print(f"Ejecutando {spec.nombre}...")
    resultado = Runner().ejecutar(spec)

    if resultado.success:
        print(f"OK  ({(resultado.finished_at - resultado.started_at).total_seconds():.1f}s)")
        if resultado.data:
            print(f"  datos: {resultado.data}")
    else:
        print(f"FALLO: {resultado.message}")
        sys.exit(1)


def cmd_nueva(args: argparse.Namespace) -> None:
    destino = Path("automations") / args.nombre
    if destino.exists():
        print(f"Ya existe automations/{args.nombre}")
        sys.exit(1)

    clase = _a_clase(args.nombre)
    destino.mkdir(parents=True)
    (destino / "automation.py").write_text(
        _PLANTILLA_AUTOMATION.format(nombre=args.nombre, clase=clase), encoding="utf-8"
    )
    (destino / "__init__.py").write_text(
        f"from automations.{args.nombre}.automation import {clase}\n\n__all__ = [{clase!r}]\n",
        encoding="utf-8",
    )
    print(f"Creada automations/{args.nombre}/ — edita automation.py y corre:")
    print(f"  python manage.py ejecutar {args.nombre}")


def cmd_historial(args: argparse.Namespace) -> None:
    from core.database import historial

    filas = historial(nombre=args.nombre, limite=args.limite)
    if not filas:
        print("Sin ejecuciones registradas todavia.")
        return
    for fila in filas:
        estado = "OK   " if fila["exito"] else "FALLO"
        print(f"[{estado}] {fila['iniciado_en']}  {fila['automatizacion']:<24} {fila['mensaje'] or ''}")


def _a_clase(nombre_snake: str) -> str:
    return "".join(parte.capitalize() for parte in nombre_snake.split("_"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Gestion de automatizaciones RPA por linea de comandos")
    sub = parser.add_subparsers(dest="comando", required=True)

    sub.add_parser("listar", help="Lista las automatizaciones registradas").set_defaults(func=cmd_listar)

    p_ejecutar = sub.add_parser("ejecutar", help="Ejecuta una automatizacion y muestra el resultado")
    p_ejecutar.add_argument("nombre")
    p_ejecutar.set_defaults(func=cmd_ejecutar)

    p_nueva = sub.add_parser("nueva", help="Crea una automatizacion nueva a partir de la plantilla")
    p_nueva.add_argument("nombre")
    p_nueva.set_defaults(func=cmd_nueva)

    p_historial = sub.add_parser("historial", help="Muestra el historial de ejecuciones")
    p_historial.add_argument("nombre", nargs="?", default=None)
    p_historial.add_argument("--limite", type=int, default=20)
    p_historial.set_defaults(func=cmd_historial)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
