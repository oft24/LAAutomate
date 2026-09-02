# Documentación de LaAutomate

Índice de `docs/`. Cada documento tiene un propósito y un momento en el que
conviene leerlo; esta página dice cuál es cuál para no tener que abrirlos todos.

## Por dónde empezar

Elige la fila que describe lo que quieres hacer y sigue esa ruta en orden.

| Quiero… | Ruta |
|---|---|
| **Escribir mi primera automatización** | [`escribir-automatizaciones.md`](escribir-automatizaciones.md) → [`acciones.md`](acciones.md) |
| **Saber qué puede hacer `self.web`, `self.escritorio`…** | [`acciones.md`](acciones.md) |
| **Grabar un proceso en vez de escribirlo** | [`escribir-automatizaciones.md` § La grabadora](escribir-automatizaciones.md#la-grabadora) → [`logica-grabadora.md`](logica-grabadora.md) |
| **Entender cómo encaja todo por dentro** | [`arquitectura.md`](arquitectura.md) → [`logica-grabadora.md`](logica-grabadora.md) |
| **Tocar el código del proyecto** | [`arquitectura.md`](arquitectura.md) → [`desarrollo.md`](desarrollo.md) |
| **Entregar la app a alguien más** | [`empaquetado.md`](empaquetado.md) |

## Los documentos

Ordenados de "para usar" a "para mantener".

### Uso

| Documento | Qué responde |
|---|---|
| [Escribir automatizaciones](escribir-automatizaciones.md) | La clase base, los disparadores, credenciales, la grabadora, errores comunes. |
| [Referencia de acciones](acciones.md) | Todos los métodos de `self.web`, `.excel`, `.http`, `.correo`, `.escritorio`, `.copiloto`. Incluye pestañas del navegador y control de varias apps. |

### Cómo funciona por dentro

| Documento | Qué responde |
|---|---|
| [Arquitectura](arquitectura.md) | Cómo encajan registry, runner, scheduler, acciones y core. Dónde vive cada dato. |
| [Lógica de la Grabadora](logica-grabadora.md) | Flujo Web/Escritorio, máquina de estados, cómo se decide qué se graba y qué no, y las limitaciones conocidas. |

### Mantenimiento

| Documento | Qué responde |
|---|---|
| [Desarrollo](desarrollo.md) | Estructura del repo, cómo correr las pruebas, convenciones, deuda conocida. |
| [Empaquetado e instalación](empaquetado.md) | Generar el `.exe` y el instalador, y cómo cambian las rutas al empaquetar. |

### Histórico

| Documento | Qué responde |
|---|---|
| [Prompt original](CODEX_PROMPT.md) | La especificación con la que nació el proyecto. No describe el estado actual. |

## Convenciones de estos documentos

- **El código y sus pruebas son la fuente de verdad.** Si un documento y el
  código no coinciden, el documento está desactualizado — no al revés.
- Cada documento explica **por qué** una decisión es como es cuando la razón no
  es obvia, normalmente citando el caso real que la motivó. Esa es la parte que
  no se puede reconstruir leyendo el código.
- Las limitaciones conocidas se escriben, no se omiten: viven en la sección
  correspondiente del documento y en [Deuda conocida](desarrollo.md#deuda-conocida).
