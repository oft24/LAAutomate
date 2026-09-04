# Autocorrección

Cuando una automatización falla, no termina ahí: se diagnostica con la
captura del momento exacto, se arregla y se reanuda. Hasta **5 intentos**.

```
        ┌──────────────┐
        │   ejecutar   │◄──────────────────────┐
        └──────┬───────┘                       │
               │ falla                         │ recargar módulo
               ▼                               │
    captura del momento  +  bitácora  +  traceback
               │                               │
               ▼                               │
    Gemini  ◄── PRACTICAS.md              guardar arreglo
               │                               ▲
               ▼                               │
    diagnóstico + código + práctica ───────────┘
               │
               ▼  (si funcionó)
      se anota la práctica aprendida
```

## Qué se le manda al modelo

| Pieza | De dónde sale | Por qué |
|---|---|---|
| **Traceback** | `AutomationResult.data["traceback"]` | Dice en qué línea murió. |
| **Bitácora** | `engine/bitacora.py` | Dice qué estaba haciendo ANTES. Es la diferencia entre «`ElementNotFoundError` en la línea 34» y «conectó con la Calculadora, escribió 12, y el clic siguiente no encontró el botón». |
| **Captura del fallo** | El runner, en el instante exacto | Deja ver qué había realmente delante: un diálogo inesperado, otra ventana al frente, un control que se llama distinto. |
| **Código completo** | `automations/<nombre>/automation.py` | |
| **Prácticas** | [`PRACTICAS.md`](PRACTICAS.md) | Lo aprendido en reparaciones anteriores. |

## La bitácora

`ActionBundle.crear(logger, bitacora=...)` envuelve cada objeto de acciones
con `engine.bitacora.Espia`, que anota toda llamada pública. Usa
`__getattr__` en vez de generar métodos uno a uno: **añadir una acción
nueva a `engine/actions/` no requiere tocar `bitacora.py`**.

Sin bitácora no se envuelve nada — la instrumentación no se paga cuando no
se usa.

Los argumentos de `escribir`, `escribir_credencial` y `pegar_y_enviar` no
se anotan: pueden ser una contraseña de la Bóveda. En su lugar queda
`<texto de 22 caracteres, no registrado>`, que basta para diagnosticar y
nunca acaba viajando a un modelo.

## Cuándo se activa

| Origen de la ejecución | Autocorrección |
|---|---|
| **Ejecutar** en Automatizaciones | Sí |
| **Reintentar** en el Panel principal | No — es reintentar tal cual, no reparar |
| Programada (cron, carpeta, webhook) | **No** |
| Sin API key de Gemini | No: se ejecuta, falla y se registra |

Un cron que reescribe código a las 3 de la mañana sin que nadie mire es una
forma excelente de despertarse con una automatización que hace algo
distinto de lo que hacía. La reparación pide una persona delante.

## Cuándo se para antes de los 5 intentos

- **El arreglo es idéntico al código actual.** Insistir solo gasta cuota.
- **La respuesta no trae bloque de código.**
- **El arreglo no carga** (no compila, no importa): se **restaura el código
  anterior**. Un intento fallido no puede dejar la automatización peor que
  antes, con código que ni siquiera importa.
- **No hay API key.**

## Qué queda en disco

`logs/reparaciones/<nombre>_<fecha>_<hora>/`:

- `intento1_0.png`, `intento1_1.png`… — las capturas de cada intento,
  **copiadas**, porque las originales las pisa la ejecución siguiente y
  comparar el antes y el después es justo lo que hace falta
- `intentoN_error.txt` — traceback y bitácora de ese intento

Sobrevive a la sesión a propósito: es lo que permite entender después por
qué la automatización acabó escrita como está.

## PRACTICAS.md

Se inyecta en cada reparación y crece con lo aprendido. Salvaguardas, porque
escribir en un archivo que luego alimenta un prompt merece cuidado:

- Solo se aprende de reparaciones **que funcionaron**. Una «lección» sacada
  de un arreglo que no arregló nada contamina todas las siguientes.
- Una línea, máximo 300 caracteres. Si el modelo se pone a narrar, se
  descarta.
- **No se repiten**: se comparan como conjuntos de palabras significativas
  (70 % de solape = la misma regla). Dos redacciones distintas de lo mismo
  no deben acumularse, y el modelo casi nunca repite la frase palabra por
  palabra.
- Máximo 40 aprendidas; las viejas salen por el principio. Si una regla
  sigue siendo cierta, volverá a aprenderse.
- La sección *Verificadas a mano* no la toca el autocorrector.

## Dónde se ve

En la vista **Automatizaciones**, la consola cuenta el progreso en vivo
(una reparación tarda minutos; el silencio es indistinguible de un
cuelgue). Al terminar, el editor **recarga el código** que quedó — si no,
seguiría enseñando una versión que ya no está en disco y el siguiente
«Guardar» desharía el arreglo sin que nadie se entere.

El relato completo —por qué falló, últimas acciones, qué se cambió— aparece
en el chat del **Asistente IA**, con las capturas de cada intento
adjuntas para poder seguir preguntando sobre ellas.

## Limitaciones

- **No valida que el arreglo haga lo correcto**, solo que deje de fallar.
  Una automatización puede «repararse» haciendo algo distinto de lo que
  hacía. Por eso el código queda visible en el editor y el relato en el
  chat: revísalo.
- Cada intento **ejecuta de verdad** sobre tus aplicaciones. Cinco intentos
  son cinco ejecuciones reales.
- El modelo no ve la pantalla mientras la automatización corre, solo la
  captura del instante del fallo.
