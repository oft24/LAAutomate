---
tags: [laautomate, ia, prompts, historial]
alias: ["Historial del prompt de reparacion"]
---

# Historial del prompt de reparación

Una entrada por versión. Las versiones completas viven en `docs/prompts/`;
volver atrás es copiar una de ahí sobre `docs/PROMPT_REPARACION.md`.

El optimizador (`engine/optimizador_prompt.py`) añade una entrada cada vez
que crea una versión tras una reparación validada. Las ediciones a mano se
anotan aquí igual.

## repair_prompt_v2 — 2026-09-04

- **Desde**: repair_prompt_v1
- **Origen**: edición a mano, revisando el prompt contra el módulo que lo consume
- **Cambios**:
  - `confidence` declara su escala (entero 0-100). El código la lee así y
    un `0.85` se truncaba a 0.
  - Prohibido cambiar `@registrar(nombre=)`: renombrarlo deja la
    automatización sin credenciales ni historial.
  - Causa raíz externa (captcha, servicio caído, credencial ausente) exige
    `ESCALATE`, no un rodeo en el código.
  - Se explicita el contrato del bloque de código: archivo entero, y que
    devolver el mismo código detiene el ciclo.
  - Se recuerda que `safe_to_execute` ausente se lee como `false`.
- **Riesgo de regresión**: bajo. Solo añade restricciones; no quita ninguna.

---

## Notas relacionadas

- [[prompts]] - como funciona el versionado
- [[autocorreccion]] - el ciclo que genera estas versiones
