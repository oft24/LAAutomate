"""Configuracion global: rutas y variables desde .env (nunca credenciales aqui)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

if getattr(sys, "frozen", False):
    # Empaquetado con PyInstaller: BASE_DIR es la carpeta donde vive el
    # .exe (no la carpeta temporal de extraccion), para que automations/,
    # logs/ y la base de datos queden junto al ejecutable instalado.
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

# El nombre de la app vive aqui y no repetido por la UI: renombrarla es
# cambiar esta linea (titulo de ventana, marca de la sidebar, etc.).
NOMBRE_APP = "LaAutomate"
DESCRIPCION_APP = "RPA de código"
MARCA_CORTA = "LA"  # sidebar colapsada


def var(nombre: str, por_defecto: str = "") -> str:
    """Lee una variable de entorno (o del .env) con valor por defecto.

    Las automatizaciones la usan en vez de os.getenv directo para dos
    cosas: importar este modulo garantiza que el .env ya se cargo (pase
    lo que pase con el orden de imports), y deja obvio que ese dato es
    configuracion del equipo -- no algo que deba quedar escrito en el
    codigo ni subido al repositorio.
    """
    return os.getenv(nombre, por_defecto)


LOGS_DIR = BASE_DIR / "logs"
DB_PATH = BASE_DIR / "core" / "rpa.db"
AUTOMATIONS_PACKAGE = "automations"

LOGS_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
