---
tags: [laautomate, revision, ux, pruebas]
actualizado: 2026-09-05
---

# Revisión funcional y UX — LaAutomate

## Resultado

Se conservó la interfaz oscura con acentos verde/cian, el icono actual y la
arquitectura Python/PySide6. Los cambios están en el código fuente de esta
copia del proyecto. Se preservaron los cambios que ya tenía el repositorio;
este informe no atribuye toda la diferencia de Git a esta revisión.

## Cambios de lógica y presentación

| Área | Cambio |
|---|---|
| Automatizaciones | Borradores por selección; detección de cambios externos sin sobrescribir; Recargar archivo con confirmación; Ctrl+S; validación de sintaxis, identidad y horario. Guardar recarga código y disparador. Acciones agrupadas y edición bloqueada durante una ejecución. |
| Grabadora | Detener genera un borrador editable; Guardar lo registra explícitamente. Rechaza captura vacía, nombre existente y URL inválida. No permite editar el área vacía mientras graba. |
| Asistente | Contexto lateral desplazable, capturas con miniaturas y eliminación individual, validación real de imágenes antes del envío, resultado de código separado, mensaje conservado tras error. La consulta de modelos no se repite en cada navegación. |
| Gemini / creación | Rechaza respuestas truncadas como código terminado. Comprueba sintaxis, disparador y expresiones que ejecutarían código durante la importación. Estas comprobaciones NO constituyen un sandbox. |
| Programador | Editar disparador lleva al código. Actualiza trabajos tras guardar/crear y detiene observadores de carpeta al reemplazarlos/eliminarlos. Un cron inválido no derriba todo el arranque. |
| Panel | KPIs sobre todo el historial, día local y ventana de 7 días; color de éxito coherente con el porcentaje; fechas y menú sin recorte. La columna de mensajes se llama Resultado porque incluye éxitos y errores. |
| Registros | Búsqueda por archivo y texto; lectura acotada de la cola de logs, incluido el indicador de errores. |
| Bóveda | Campos más amplios; errores de Windows informados sin mostrar secretos; no permite crear credenciales de nombres que no puede recuperar en su lista. Conserva la contraseña al editar sin escribir otra. |
| Wiki | Búsqueda arriba y contenido completo desplazable. Estado sin coincidencias y explicación actualizada del guardado y cron. |
| Cierre | Advierte sobre borradores pendientes; conserva la vida de los hilos de interfaz hasta que terminan y bloquea el cierre mientras están activos. |

## Verificación

- **419 pruebas pasaron; 12 excluidas** por las marcas de red/navegador.
  Comando: `python -m pytest -q -m "not network and not navegador" -p no:cacheprovider`.
  Informe de la corrida: [pytest.xml](../build/revision-ux/pytest.xml).
- **32 regresiones nuevas** en [test_revision_ux.py](../tests/test_revision_ux.py)
  y [test_revision_flujos.py](../tests/test_revision_flujos.py): conflictos del
  editor, guardado explícito, URLs, errores/respuestas Gemini, imágenes
  inválidas, disparadores, cola de logs, KPIs de más de 100 filas y búsqueda Wiki.
- **16 capturas Qt**: las ocho vistas a 1360×860 y 1100×700, con datos
  sintéticos y sin ejecutar las automatizaciones personales.
  Se comprobó el tamaño y se inspeccionaron las ocho vistas; el render
  detiene la transición únicamente para fotografiar el estado estable.
  Reproducible con [review_ui.py](../tools/review_ui.py).
- **Gemini real**: la cuenta devolvió 40 modelos; una petición mínima con
  `gemini-3.8-flash` respondió HTTP 200 y el marcador esperado.
  Solo se envió una frase sintética: no código, documentos, logs ni capturas.
  La clave no se mostró. Esto valida conexión/modelo, no la calidad de una
  automatización completa generada con imágenes.
- Compilación de módulos y comprobación de espacios del diff sin errores.
- El entorno protegido inicialmente impidió capturas y acceso a credenciales
  (WinError 1312). Al repetir las pruebas con acceso a la sesión de Windows,
  las siete comprobaciones de esos módulos pasaron; la corrida final también.

## Privacidad y límites

El diagnóstico incorpora un fragmento del log al mensaje que se enviará.
La interfaz y [[CONTEXTO-COMPLETO]] ahora lo dicen: revisar texto, código e
imágenes antes de generar. No se garantiza anonimización automática ni
protección absoluta frente a instrucciones maliciosas dentro del contexto.

No se ejecutaron los flujos personales de CURP/YouTube ni se probó su operación
completa en las aplicaciones destino. No se auditó ni modificó un Supabase
remoto. No se reconstruyó el ejecutable, no se reemplazó la instalación del
escritorio y no se hizo commit ni push.

Se mantienen pendientes las decisiones de mayor alcance: editor visual de
cron, persistencia/mezcla de borradores entre sesiones, búfer de diez capturas
y cambios del instalador. La programación sigue declarada en código y requiere
la aplicación abierta. Ejecutar o importar Python requiere confiar en ese código.

## Contexto y archivos

- [[CONTEXTO-COMPLETO]]: resumen principal y mapa del proyecto.
- [[logica-grabadora]]: estados y flujo de revisión/guardado.
- `app/windows/`: comportamiento de las vistas.
- `core/gemini_client.py`, `core/database.py`: Gemini y métricas.
- `engine/scheduler.py`: validación y actualización de disparadores.
- [Capturas de revisión](../build/revision-ux/): evidencia visual local.
