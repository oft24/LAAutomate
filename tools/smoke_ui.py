"""Recorre la interfaz entera sin abrir ventana y comprueba que nada revienta.

    python tools/smoke_ui.py

Complementa a pytest, no lo reemplaza. Las pruebas de tests/ validan
lógica pura a propósito (no arrancan QApplication); esto cubre lo otro:
que cada vista se construya, que la sidebar y el QStackedWidget sigan
alineados, que pulsar cualquier botón no lance una excepción, y que la
interfaz no use ningún color fuera de la paleta de tokens.

Corre con la plataforma "offscreen" de Qt: no aparece ninguna ventana y
no toca el escritorio real. Devuelve 0 si todo va bien, 1 si algo falla
-- sirve tal cual para CI.

Encontró de verdad, la primera vez que se corrió, un AttributeError en los
tres botones del panel de detalle de la tabla del Panel principal.
"""
from __future__ import annotations

import os
import re
import sys
import traceback
from pathlib import Path

# Qt sin ventana: esto corre en una terminal. Tiene que ir antes de
# importar cualquier cosa de PySide6.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
os.chdir(RAIZ)

from PySide6.QtWidgets import QApplication, QPushButton, QToolButton  # noqa: E402

# Botones que NO se pulsan: lanzan un proceso, abren el Explorador, borran
# datos o llaman a la red. Se identifican por su texto visible.
NO_PULSAR = {
    "▶  Ejecutar",
    "■  Cancelar",
    "Ejecutar todo",
    "Eliminar",
    "Abrir carpeta",
    "Guardar",
    "Guardar automatización",
    "Iniciar grabación",
    "Detener",
    "Cancelar",
    "Olvidar",
    "Actualizar modelos",
    "Generar con IA",
    "Diagnosticar y corregir",
    "Capturar pantalla ahora",
    "Ver logs",
    "Ver captura de pantalla",
    "Abrir log completo",
    "Reintentar",
    # Vista Asistente: red, dialogos nativos o escritura en disco.
    "Generar con Gemini",
    "Configurar clave",
    "Adjuntar capturas",
    "Crear automatización",
    "Explicar un error",
}


def _botones(pagina):
    return pagina.findChildren(QPushButton) + pagina.findChildren(QToolButton)


def main() -> int:
    app = QApplication([])

    from app.resources.iconos import nombres_disponibles
    from app.resources.tokens import COLORES, construir_qss
    from app.widgets.sidebar import _GRUPOS, CLAVES
    from app.windows.main_window import MainWindow
    from engine.registry import descubrir, errores_de_descubrimiento
    from engine.runner import Runner
    from engine.scheduler import Scheduler

    fallos: list[str] = []

    descubrir()
    rotas = errores_de_descubrimiento()
    print("automatizaciones que no importan:", rotas or "ninguna")

    ventana = MainWindow(scheduler=Scheduler(Runner()), runner=Runner())
    ventana.show()

    # 1. sidebar y pila de páginas alineadas
    if ventana.paginas.count() != len(CLAVES):
        fallos.append(f"{ventana.paginas.count()} páginas para {len(CLAVES)} entradas de sidebar")

    # 2. cada vista se muestra y sus botones responden
    pulsados = 0
    for indice, clave in enumerate(CLAVES):
        ventana.sidebar.establecer_vista(clave)
        app.processEvents()
        if ventana.paginas.currentIndex() != indice:
            fallos.append(f"la vista {clave!r} no abre la página {indice}")

        pagina = ventana.paginas.currentWidget()
        print(f"  {clave:18s} {type(pagina).__name__:18s} {len(_botones(pagina))} botones")

        # Se vuelven a buscar los botones en cada vuelta y se lleva la
        # cuenta por etiqueta: pulsar uno puede recrear widgets (recargar
        # una lista, repoblar una tabla), y una referencia guardada de
        # antes apunta entonces a un objeto C++ ya destruido.
        ya_pulsados: set[str] = set()
        while True:
            siguiente = None
            for boton in _botones(pagina):
                try:
                    etiqueta = boton.text().strip() or boton.toolTip().strip() or "(icono)"
                    if etiqueta in NO_PULSAR or etiqueta in ya_pulsados or not boton.isEnabled():
                        continue
                except RuntimeError:
                    continue  # widget destruido entre el findChildren y aquí
                siguiente = (boton, etiqueta)
                break
            if siguiente is None:
                break

            boton, etiqueta = siguiente
            ya_pulsados.add(etiqueta)
            try:
                boton.click()
                app.processEvents()
                pulsados += 1
            except Exception:
                fallos.append(f"{clave}/{etiqueta}: {traceback.format_exc(limit=3)}")
            # Volver: el botón pudo navegar a otra vista.
            ventana.sidebar.establecer_vista(clave)
            app.processEvents()
            pagina = ventana.paginas.currentWidget()

    print(f"\n{pulsados} botones pulsados sin excepciones")

    # 3. ningún color escrito a mano fuera de la paleta
    paleta = {v.lower() for v in vars(COLORES).values() if isinstance(v, str)}
    sueltos = {c.lower() for c in re.findall(r"#[0-9A-Fa-f]{6}", construir_qss())} - paleta
    print("colores fuera de la paleta:", sueltos or "ninguno")
    if sueltos:
        fallos.append(f"colores fuera de app/resources/tokens.py: {sorted(sueltos)}")

    # 4. cada icono que la sidebar pide existe de verdad
    faltan = [i for _g, items in _GRUPOS for _c, i, _t in items if i not in nombres_disponibles()]
    print("iconos de sidebar faltantes:", faltan or "ninguno")
    if faltan:
        fallos.append(f"iconos inexistentes: {faltan}")

    if fallos:
        print("\nFALLOS:")
        for fallo in fallos:
            print(" -", fallo)
        return 1
    print("\nTODO OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
