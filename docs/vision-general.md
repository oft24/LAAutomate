---
tags: [laautomate, introduccion]
alias: ["Visión general", "Qué es LaAutomate"]
---

# Qué es LaAutomate

> [!abstract] En una frase
> Un programa de escritorio para Windows que **hace por ti las tareas
> repetitivas del ordenador** —abrir apps, rellenar formularios, leer y
> escribir Excel, navegar por webs— y que, cuando algo se rompe, intenta
> arreglarse solo.

---

## El problema que resuelve

Hay trabajo de oficina que consiste en repetir los mismos clics. Consultar
200 CURP uno por uno. Sacar un reporte del portal cada lunes. Copiar datos
de un Excel a un sistema que no tiene API.

Una persona tarda horas y se equivoca al final del día, cuando se cansa.

Existen herramientas para esto —Power Automate, UiPath— pero todas te
piden dibujar el proceso en un diseñador visual: cajas, flechas, menús.
Funciona hasta que necesitas algo que el diseñador no previó, y entonces
te quedas atascado.

## La apuesta de LaAutomate

**Cada automatización es un archivo de Python normal.** Se lee, se edita,
se depura y se versiona como cualquier otro código.

```python
@registrar(nombre="reporte_diario", disparador="cron:0 8 * * *")
class ReporteDiario(BaseAutomation):
    def ejecutar(self) -> AutomationResult:
        self.web.ir_a("https://portal.interno/login")
        self.web.escribir("#usuario", self.credenciales.usuario)
        self.web.click("#entrar")
        filas = self.excel.leer("C:/reportes/ventas.xlsx")
        return AutomationResult(success=True, data={"filas": len(filas)})
```

No hay que empezar escribiendo código, eso sí. Hay tres caminos:

| Camino | Cómo | Nota |
|---|---|---|
| **Grabarlo** | Das tus clics reales y la app los traduce a Python | [[logica-grabadora]] |
| **Describirlo** | Le cuentas al chat qué quieres y adjuntas una captura | [[asistente-ia]] |
| **Escribirlo** | Directamente, con la referencia de acciones delante | [[escribir-automatizaciones]] |

Los tres producen **el mismo tipo de archivo**: código que puedes abrir y
cambiar. No hay cajas negras.

---

## Qué trae

| | |
|---|---|
| **Grabadora** | Graba clics y teclas —en el navegador o en apps de escritorio— y escribe el código. Nunca graba contraseñas |
| **Asistente IA** | Convierte una descripción y unas capturas en código. Y arregla el que falla |
| **Autocorrección** | Si algo falla, el botón «Corregir código» diagnostica con la captura del momento, corrige y reanuda. Hasta 3 intentos |
| **Programador** | Cron y carpeta vigilada |
| **Historial** | Cada corrida queda registrada: éxito, fallo, mensaje, duración |
| **Bóveda** | Usuarios y contraseñas en el Almacén de credenciales de Windows, nunca en el código |
| **Wiki integrada** | La referencia de acciones, dentro de la app |

---

## Qué NO es

> [!warning] Límites honestos
> Saber qué no hace una herramienta ahorra más tiempo que saber qué hace.

- **No es un diseñador visual.** Si no quieres ver código nunca, esta no es
  tu herramienta.
- **No es un servicio en la nube.** Corre en tu equipo, contra tus
  aplicaciones. Si apagas el ordenador, no corre.
- **No sustituye a una API.** Si el sistema al que quieres llegar tiene API,
  úsala: será más rápida y no se romperá cuando cambien un botón.
- **La autocorrección no garantiza que el arreglo sea correcto**, solo que
  deje de fallar. Una automatización puede «repararse» haciendo algo
  distinto. Por eso el código queda a la vista. Ver
  [[autocorreccion#Limitaciones]].
- **No burla protecciones.** Si una web tiene reCAPTCHA, la automatización
  se detiene y te lo dice; no intenta esquivarlo.

---

## Cómo está hecho

```
┌─────────────┐   @registrar    ┌──────────┐   dispara   ┌───────────┐
│ automations/│ ──────────────► │ registry │ ──────────► │ scheduler │
│  tu código  │                 └──────────┘             └─────┬─────┘
└─────────────┘                                                │
                                                               ▼
┌──────────────────────────────┐   inyecta acciones      ┌──────────┐
│ self.web .excel .http        │ ◄────────────────────── │  runner  │
│ .correo .escritorio .copiloto│                         └─────┬────┘
└──────────────────────────────┘                               │
                                              logs + captura + SQLite
                                                               │
                                                               ▼
                                                   [[autocorreccion]]
```

Los detalles, en [[arquitectura]].

---

## Primeros pasos

1. Instala con `INSTALL.bat` (ver [[empaquetado]]).
2. Abre la app desde el acceso directo del escritorio.
3. Ve a **Asistente IA** -> *Configurar clave* y pega tu API key de
   [Google AI Studio](https://aistudio.google.com/apikey). Es gratis y queda
   cifrada en el Almacén de credenciales de Windows.
4. Pídele algo sencillo y mira el código que genera antes de ejecutarlo.

> [!tip] Empieza pequeño
> Tu primera automatización no debería tocar nada importante. Una que abra
> la Calculadora y sume dos números te enseña más sobre cómo funciona esto
> que una que mueva facturas.
