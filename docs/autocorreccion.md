---
tags: [laautomate, ia, autocorreccion]
alias: ["Autocorreccion", "Reparacion automatica"]
---

# Autocorrección

Cuando una automatización falla, no termina ahí: se diagnostica con la
captura del momento exacto, se arregla y se reanuda. Hasta **3 intentos**.

No se dispara solo: lo arranca el botón **Corregir código** de la vista
Automatizaciones, cuando una ejecución ha fallado.

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

## Cuándo se para antes de los 3 intentos

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

## El contrato del agente de reparación

El prompt vive en [`PROMPT_REPARACION.md`](PROMPT_REPARACION.md), **versionado
en su primera línea** (`repair_prompt_vN`). Está en un archivo y no en el
código para que se pueda mejorar sin tocar Python y volver atrás copiando un
archivo.

El agente responde JSON con estructura fija: `status`, `root_cause`,
`confidence`, `evidence`, `proposed_correction` (con `risk` y
`safe_to_execute`), `success_validation` y `learning_candidate`. Eso da tres
puertas que un formato libre no daba:

| Condición | Qué pasa |
|---|---|
| `status: "ESCALATE"` | El ciclo se detiene y se marca para revisión humana |
| `safe_to_execute: false` | **No se aplica.** Es la única salvaguarda que el contrato le da al agente para frenar un cambio irreversible |
| `safe_to_execute` ausente | Se trata como NO seguro: la salvaguarda falla cerrada |
| `risk: "HIGH"` | No se aplica; pide revisión |

Cada intento recibe además un resumen de los **anteriores** —qué causa raíz
se propuso, si se aplicó, y con qué volvió a fallar— para que no repita una
corrección que ya falló.

## El optimizador de prompt

Tras una reparación **validada**, [`PROMPT_OPTIMIZADOR.md`](PROMPT_OPTIMIZADOR.md)
extrae la lección generalizable y produce una versión nueva del prompt de
reparación. `engine/optimizador_prompt.py` lo gobierna con tres barandillas:

1. **Solo se aprende de éxitos validados.** `update_prompt: false` es una
   respuesta válida y la más común.
2. **Nunca se sobrescribe una versión.** Cada una se archiva en
   `docs/prompts/repair_prompt_vN.md`; el archivo activo es una copia.
   Volver atrás es copiar un archivo. Cada cambio deja entrada en
   [`PROMPT_CHANGELOG.md`](PROMPT_CHANGELOG.md).
3. **El prompt del optimizador no se toca a sí mismo.** Un sistema que
   reescribe las reglas con las que se juzga no tiene punto de apoyo.

Y tres filtros automáticos sobre la versión propuesta:

- Si crece más de un 60 %, se rechaza: generalizar debería resumir, no
  acumular.
- Si baja de 2 000 caracteres, se rechaza: le faltan secciones.
- Si pierde *Reglas de seguridad*, *Salida obligatoria* o el campo
  `"status"`, se rechaza. «Mejorar» no puede significar quedarse sin las
  reglas de seguridad.

Cuesta una llamada extra; se apaga con `Autocorrector(..., mejorar_prompt=False)`.

## Limitaciones

- **No valida que el arreglo haga lo correcto**, solo que deje de fallar.
  Una automatización puede «repararse» haciendo algo distinto de lo que
  hacía. Por eso el código queda visible en el editor y el relato en el
  chat: revísalo.
- Cada intento **ejecuta de verdad** sobre tus aplicaciones. Cinco intentos
  son tres ejecuciones reales.
- El modelo no ve la pantalla mientras la automatización corre, solo la
  captura del instante del fallo.

---

## Notas relacionadas

- [[prompts]] - el prompt de reparacion y el que lo mejora
- [[PRACTICAS]] - donde queda lo aprendido de cada arreglo
- [[PROMPT_CHANGELOG]] - historial de versiones del prompt
- [[arquitectura]] - el runner que detecta el fallo
