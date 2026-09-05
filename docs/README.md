---
tags: [laautomate, indice, moc]
alias: ["Mapa de LaAutomate", "Índice de documentación"]
---

# Mapa de LaAutomate

> [!info] Cómo leer esto
> Esta es la puerta de entrada. Cada nota se explica sola y enlaza con las
> demás. Si abres esta carpeta en **Obsidian**, la vista de grafo muestra
> cómo encaja todo y los enlaces entre notas son navegables.

**LaAutomate** es una plataforma de escritorio para escribir automatizaciones
(RPA) **en código Python**, no en un diseñador visual. Programa, ejecuta,
registra y —cuando algo falla— se repara sola con ayuda de un modelo.

---

## Por dónde empezar

Elige la fila que describe lo que quieres hacer.

| Quiero… | Ruta |
|---|---|
| **Todo el proyecto en un solo archivo** | [[CONTEXTO-COMPLETO]] |
| **Entender qué es esto en 5 minutos** | [[vision-general]] |
| **Escribir mi primera automatización** | [[escribir-automatizaciones]] -> [[acciones]] |
| **Saber qué puedo llamar** (`self.web`, `self.escritorio`…) | [[acciones]] |
| **Grabar un proceso en vez de escribirlo** | [[logica-grabadora]] |
| **Que la IA lo escriba por mí** | [[asistente-ia]] |
| **Entender cómo se repara sola** | [[autocorreccion]] |
| **Ver los errores ya aprendidos** | [[PRACTICAS]] |
| **Entender el sistema por dentro** | [[arquitectura]] |
| **Tocar el código** | [[arquitectura]] -> [[desarrollo]] |
| **Entregar la app a alguien** | [[empaquetado]] |

---

## Las notas, por tema

### Para usar

| Nota | Qué responde |
|---|---|
| [[CONTEXTO-COMPLETO]] | El proyecto entero en un archivo: lo pedido, lo hecho, cada botón, lo que falta. Punto de extracción de contexto |
| [[vision-general]] | Qué es LaAutomate, para quién, y qué **no** es |
| [[escribir-automatizaciones]] | La clase base, disparadores, credenciales, errores comunes |
| [[acciones]] | Todos los métodos de `self.web`, `.escritorio`, `.excel`, `.http`, `.correo`, `.copiloto` |
| [[logica-grabadora]] | Grabar clics y teclas, y convertirlos en código |

### La parte de IA

| Nota | Qué responde |
|---|---|
| [[asistente-ia]] | El chat: qué se le manda, cómo elige modelo, qué valida antes de guardar |
| [[autocorreccion]] | Qué pasa cuando algo falla: bitácora, capturas y hasta 3 intentos |
| [[prompts]] | Cómo están construidos los prompts y por qué |
| [[PRACTICAS]] | La memoria del sistema: errores reales y la regla que dejaron |
| [[PROMPT_CHANGELOG]] | Historial de versiones del prompt de reparación. Lo genera el optimizador: no existe hasta la primera mejora |

### Por dentro

| Nota | Qué responde |
|---|---|
| [[arquitectura]] | Cómo encajan registry, runner, scheduler, acciones y core |
| [[desarrollo]] | Estructura del repo, pruebas, convenciones, deuda conocida |
| [[empaquetado]] | Generar el `.exe` y el instalador |

### Histórico

| Nota | Qué responde |
|---|---|
| [[CODEX_PROMPT]] | La especificación con la que nació el proyecto. **No** describe el estado actual |

---

## Cómo se relacionan

```
                    vision-general
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
escribir-…      logica-grabadora   asistente-ia
        │                   │                   │
        └─────────► acciones ◄──────────────┘
                            │
                            ▼
                     arquitectura
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
      autocorreccion            desarrollo
              │                           │
       ┌──────┴──────┐                    ▼
       ▼             ▼             empaquetado
 PRACTICAS  prompts
```

---

## Convenciones de estas notas

> [!warning] El código manda
> Si una nota y el código no coinciden, **la nota está desactualizada** — no
> al revés. Las pruebas son la fuente de verdad ejecutable.

- Cada nota explica **por qué** una decisión es como es cuando la razón no es
  obvia, citando el caso real que la motivó. Esa es la parte que no se puede
  reconstruir leyendo el código.
- Las limitaciones se **escriben**, no se omiten. Viven en su nota y en
  [[desarrollo#Deuda conocida]].
- Los números que aparecen (tiempos, tamaños, porcentajes) están **medidos**.
  Si algo es una estimación, lo dice.
