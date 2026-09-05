# Revisión visual de LaAutomate

Se conserva la identidad actual: fondo oscuro, acentos verde/cian y marca L monocromática.

## Cambios

- Editores compartidos con números de línea y resaltado de la línea actual. El código, sus eventos de edición y la validación existentes se conservan.
- Chat con Markdown legible, texto del usuario literal y altura adaptada al ancho. No carga imágenes remotas/locales ni abre enlaces del contenido generado. Los mensajes largos mantienen desplazamiento interno.
- Sugerencias en una fila; indicación visible de Ctrl+V; adjuntar capturas antes de la lista; acciones de limpieza agrupadas.
- Nombres de automatización sin metadatos que saturen la lista; categoría y disparador disponibles al pasar el cursor.
- Botones de peligro deshabilitados sin borde rojo activo, foco de teclado visible y separadores más fáciles de arrastrar.
- KPI con acentos discretos, estados como etiquetas redondeadas y pista de ejecuciones con fondos suaves.
- Bóveda con etiquetas sobre campos amplios, estados vacíos con menos margen y títulos adaptables.
- Subtítulos adaptables, acción del programador de ancho natural y Wiki con texto de lectura mayor.

## Verificación

`tools/review_ui.py` crea vistas sintéticas de las ocho pantallas en 1360×860 y 1100×700, además de navegación compacta y una respuesta Markdown. Salida: `build/revision-ux/`.

Pruebas: `tests/test_design_components.py`, `tests/test_controles_ui.py`, `tests/test_revision_ux.py`, `tests/test_revision_flujos.py` y `tests/test_adjuntar_capturas.py`.

Estas comprobaciones no llaman a Gemini, no envían mensajes externos y no ejecutan automatizaciones personales. No sustituyen una prueba de integración con los servicios reales. Guardar borradores y reabrir la aplicación para cargar la nueva interfaz.
