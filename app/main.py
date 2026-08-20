"""Punto de entrada de la app de escritorio (PySide6)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    # Empaquetado con PyInstaller: automations/ vive junto al .exe como
    # carpeta editable de verdad (no compilada dentro del bundle), asi
    # que hay que poner esa carpeta en sys.path y fijar el cwd ahi para
    # que "import automations" y las rutas relativas (logs/, etc.) la
    # encuentren igual que en modo desarrollo.
    _base_dir = Path(sys.executable).resolve().parent
    if str(_base_dir) not in sys.path:
        sys.path.insert(0, str(_base_dir))
    os.chdir(_base_dir)

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.windows.main_window import MainWindow
from engine.registry import descubrir
from engine.runner import Runner
from engine.scheduler import Scheduler

RUTA_ICONO = Path(__file__).resolve().parent / "resources" / "app_icon.ico"


def main() -> None:
    descubrir()  # importa /automations y llena el registry via @registrar

    runner = Runner()
    scheduler = Scheduler(runner)
    scheduler.iniciar()

    app = QApplication(sys.argv)
    if RUTA_ICONO.exists():
        app.setWindowIcon(QIcon(str(RUTA_ICONO)))
    ventana = MainWindow(scheduler=scheduler, runner=runner)
    ventana.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
