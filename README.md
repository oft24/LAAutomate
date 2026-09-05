# LaAutomate

<img src="app/resources/app_icon.png" alt="Logo de LaAutomate: una L blanca sobre fondo oscuro" width="80">

**Describe una tarea. Convierte el proceso en Python. Ejecútalo desde tu equipo.**

LaAutomate es una aplicación de escritorio para Windows que reúne automatización
web, automatización de escritorio y un asistente de IA en una misma interfaz.
Puedes crear flujos con instrucciones y capturas de pantalla, grabar tus acciones
o escribir el código directamente.

**[Descargar para Windows](https://github.com/oft24/LAAutomate/releases/latest/download/LaAutomate-Windows-x64.zip)** ·
[Ver Releases](https://github.com/oft24/LAAutomate/releases) ·
[Probar la demo](#prueba-la-demo-excel--navegador--comparativo) ·
[Documentación técnica](docs/README.md)

> Proyecto personal en evolución. Ya puedes descargarlo y probarlo.
> El código de cada automatización queda visible y editable; los flujos generados
> por IA requieren revisión y pruebas.

## Por qué nació

La idea surgió mientras llenaba un Excel para un emprendimiento personal.
Un proceso sencillo terminaba consumiendo tiempo entre capturar datos, consultar
información y repetir los mismos pasos.

Después de haber desarrollado flujos con Selenium, quise convertir esa experiencia
en una aplicación que pudiera usar desde mi equipo. También quería explorar cómo
las instrucciones en lenguaje natural y las capturas de pantalla podían ayudar a
crear automatizaciones sin escribir cada paso desde cero.

Así nació LaAutomate: un proyecto para dedicar menos tiempo a tareas repetitivas
y aprender construyendo con Python, Selenium, automatización de Windows e IA.

## Qué puedes hacer

- **Automatizar páginas web:** navegar, completar campos, hacer clic, consultar
  información, descargar archivos y trabajar con varias pestañas.
- **Trabajar con aplicaciones de Windows:** localizar ventanas, escribir,
  utilizar atajos e interactuar con controles del escritorio.
- **Procesar Excel:** leer listas de entrada, transformar datos y generar reportes.
- **Crear flujos con ayuda de IA:** describir el proceso y adjuntar capturas
  para obtener un borrador de código Python.
- **Grabar acciones:** capturar pasos en el navegador o escritorio como punto
  de partida para una automatización.
- **Ejecutar y diagnosticar:** consultar historial, logs y capturas de errores;
  solicitar correcciones cuando un flujo falla.
- **Programar tareas:** ejecutar manualmente, por horario o ante cambios en
  una carpeta, mientras la aplicación permanece abierta.

La ejecución normal utiliza el código guardado. No necesita consultar un modelo
de IA en cada paso. Gemini interviene al generar código o solicitar una reparación;
las páginas, APIs y aplicaciones que use cada flujo tienen sus propios requisitos.

## Prueba la demo: Excel → navegador → comparativo

La demo incluida muestra un proceso completo y fácil de repetir:

1. Lee los productos y cantidades desde un Excel.
2. Abre un catálogo local de pruebas con Selenium.
3. Extrae ofertas y disponibilidad.
4. Calcula **precio × cantidad + envío**.
5. Genera un Excel con las opciones más económicas resaltadas.

**La lista es dinámica:** agrega un producto al Excel y vuelve a ejecutar el mismo
flujo. No necesitas modificar Python.

### Cómo probarla

Después de instalar LaAutomate:

1. Abre la carpeta de la aplicación. Con el instalador está en
   `%LOCALAPPDATA%\LaAutomate`; desde código, es la carpeta del repositorio.
2. Abre `outputs/demo-compras/productos.xlsx`. La hoja **Productos** contiene
   `SKU`, `Cantidad`, `Activo` y `Descripción`.
3. Guarda y cierra el libro.
4. En **Automatizaciones**, selecciona **comparativo_compras** y pulsa **Ejecutar**.
5. Abre el reporte nuevo en `datos/comparativo_compras/`. La aplicación también
   muestra su ruta en la salida.

Para comprobar que se adapta a los datos, agrega esta fila y repite la ejecución:

| SKU | Cantidad | Activo | Descripción |
|---|---:|---|---|
| MOU-01 | 3 | Sí | Mouse Claro inalámbrico |

El siguiente reporte debe incluir el mouse. Las filas inactivas se omiten y los
productos inexistentes se registran como **Sin resultados**.

La demo usa **datos ficticios y un catálogo local**: no busca en Google ni en
Cyberpuerta y no realiza compras. Requiere Chrome o Edge y su controlador compatible.
El catálogo funciona sin internet; la primera preparación del controlador puede
necesitar conexión.

[Ver la guía, los resultados esperados y el guion de demostración →](docs/DEMO-COMPARATIVO-COMPRAS.md)

## Descargar e instalar LaAutomate en Windows

### Opción 1: instalador listo para usar

**Recomendada para probar la aplicación. No requiere Python ni cuenta de GitHub.**

1. Descarga **[LaAutomate-Windows-x64.zip](https://github.com/oft24/LAAutomate/releases/latest/download/LaAutomate-Windows-x64.zip)**.
2. Haz clic derecho sobre el ZIP y elige **Extraer todo**.
3. Abre la carpeta `LaAutomate` extraída. Conserva juntos el ejecutable y
   la carpeta `_internal`.
4. Cierra LaAutomate si estaba abierta y ejecuta **`INSTALL.bat`**.
5. Espera el mensaje de instalación completada y abre el acceso directo
   **LaAutomate** del escritorio.

La instalación se guarda en `%LOCALAPPDATA%\LaAutomate`.

> En [Releases de LaAutomate](https://github.com/oft24/LAAutomate/releases),
> elige **LaAutomate-Windows-x64.zip**, no **Source code (zip)**.
> El repositorio no contiene `dist/` ni un ejecutable precompilado.

El ejecutable todavía no tiene firma digital. Si Windows muestra una advertencia
de SmartScreen, verifica el origen del archivo antes de decidir si lo ejecutas.
No es necesario desactivar el antivirus.

### Opción 2: ejecutar desde el código fuente

Para explorar o modificar el proyecto:

1. Instala Python 3.11 o posterior y habilita su acceso desde la terminal.
2. Descarga **Code → Download ZIP** y extrae el contenido, o clona el repositorio.
3. Abre la carpeta que contiene este README.
4. Ejecuta **`INSTALAR_LAAUTOMATE.bat`**.
5. Espera a que instale las dependencias y cree el acceso directo.

Este script crea un entorno `.venv` dentro del proyecto. El acceso directo
depende de esa carpeta: no la muevas ni la elimines después.

También puedes preparar el entorno manualmente desde PowerShell:

```powershell
git clone https://github.com/oft24/LAAutomate.git
cd LAAutomate
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
.\.venv\Scripts\python.exe -m app.main
```

### Qué necesitas

| Para usar… | Necesitas… |
|---|---|
| Aplicación de escritorio | Windows 10/11 de 64 bits para el paquete publicado. |
| Código fuente | Python 3.11 o posterior y conexión para instalar dependencias. |
| Automatización web y demo | Chrome o Edge; Selenium necesita un controlador compatible. |
| Lectura y escritura de archivos XLSX | Las dependencias incluidas; Excel de Microsoft no es obligatorio para procesar archivos con pandas/openpyxl. |
| Control de Excel u Outlook mediante COM | La aplicación correspondiente instalada en Windows. |
| Asistente IA y autocorrección | Una clave de la API de Gemini y conexión a internet. |
| Flujos con Teams, Copilot u otras aplicaciones | La aplicación, sesión y permisos que requiera ese proceso. |

**Gemini es opcional.** Puedes abrir LaAutomate, ejecutar código y utilizar la
grabadora sin una clave de IA. Las cuotas y posibles costos de Gemini dependen
de tu cuenta con el proveedor; no están incluidos en la descarga.

## Tu primera automatización

Hay tres formas de empezar.

### Con el asistente IA

1. Abre **Asistente IA → Configurar clave**.
2. Pulsa **Actualizar modelos** y elige uno disponible para tu cuenta.
3. Describe los pasos, los datos de entrada y cómo comprobar el resultado.
4. Adjunta capturas o pégalas con **Ctrl+V**. Puedes agregar varias antes de enviar.
5. Pulsa **Generar con Gemini**.
6. Revisa el código y utiliza **Crear automatización** para guardarlo.
7. Abre el flujo en **Automatizaciones** y pruébalo con datos ficticios.

Una solicitud útil especifica el resultado esperado, por ejemplo:

> Lee la hoja Productos de mi Excel. Por cada fila activa, consulta el catálogo
> indicado, extrae precio y disponibilidad y genera un reporte nuevo. Calcula el
> total según la cantidad y señala la opción más económica. Si no encuentras un
> producto, registra Sin resultados. Conserva el archivo de entrada.

Incluye rutas, nombres de hojas, columnas y condiciones de éxito. Una captura
ayuda a interpretar una interfaz, pero no demuestra que un selector siga vigente.

El chat admite hasta **10 capturas**, **12 MB en total** y **25 megapíxeles por
imagen**. Los mensajes se pueden seleccionar y copiar. El selector
**Español / English** cambia los controles de la interfaz y conserva el contenido
del chat y del código.

### Con la grabadora

1. Abre **Grabadora** y elige **Web** o **Escritorio**.
2. Indica el nombre y el destino solicitado.
3. Pulsa **Iniciar grabación** y realiza los pasos.
4. Usa **Detener y generar código**.
5. Revisa el resultado y guarda la automatización.

La grabación web puede seguir pestañas nuevas. En escritorio, el modo de varias
ventanas permite registrar un proceso entre aplicaciones. El resultado necesita
revisión: los textos, controles, tiempos y coordenadas pueden cambiar.

[Cómo funciona la grabadora y cuáles son sus límites →](docs/logica-grabadora.md)

### Escribiendo Python

Desde la raíz del proyecto:

```powershell
.\.venv\Scripts\python.exe manage.py nueva mi_automatizacion
```

Edita `automations/mi_automatizacion/automation.py`. Un ejemplo mínimo que puedes
ejecutar sin servicios externos:

```python
from engine.automation_base import AutomationResult, BaseAutomation
from engine.registry import registrar


@registrar(nombre="mi_automatizacion", disparador="manual", categoria="ejemplos")
class MiAutomatizacion(BaseAutomation):
    def ejecutar(self) -> AutomationResult:
        self.logger.info("Mi primera automatización está funcionando")
        return AutomationResult(success=True, message="Prueba completada")
```

El motor proporciona `self.web`, `self.escritorio`, `self.excel`, `self.http`,
`self.correo` y `self.copiloto`. Mantén el nombre del registro igual al de la
carpeta. Deja que los errores inesperados se propaguen para que el motor capture
su diagnóstico.

[Guía para escribir automatizaciones](docs/escribir-automatizaciones.md) ·
[Referencia de acciones](docs/acciones.md)

## Ejecutar, programar y revisar resultados

| Pantalla | Para qué sirve |
|---|---|
| Panel principal | Consultar actividad reciente y métricas de ejecución. |
| Automatizaciones | Revisar y editar código, ejecutar, cancelar y solicitar correcciones. |
| Grabadora | Capturar pasos web o de escritorio. |
| Programador | Consultar y configurar disparadores. |
| Asistente IA | Generar borradores con instrucciones y capturas. |
| Registros | Revisar el historial y la salida de los procesos. |
| Bóveda de credenciales | Configurar credenciales mediante el almacén de Windows. |
| Wiki | Consultar documentación dentro de la aplicación. |

Los disparadores admitidos son `manual`, `cron:` y `carpeta:`.
Por ejemplo, `cron:0 8 * * *` ejecuta a las 08:00 cada día y
`carpeta:C:/entradas` observa una carpeta existente.

**La aplicación debe permanecer abierta para que funcionen los horarios y
observadores.** La automatización de escritorio también necesita una sesión
interactiva adecuada; el foco y las acciones del usuario pueden interferir.

El historial indica lo que reportó el flujo. Para confirmar un resultado de
negocio, el código debe verificarlo: por ejemplo, comprobar el archivo creado o
el mensaje de confirmación de una página.

## Cuando Gemini o una automatización fallan

### Intentar sondeo

El botón **Intentar sondeo** comprueba hasta 10 modelos disponibles para la cuenta,
ordenados por una estimación de capacidad. Envía una consulta pequeña, sin tu
mensaje ni capturas, y selecciona el primero que responde.

La búsqueda tiene un presupuesto total de 90 segundos, por lo que puede terminar
antes de probar los 10. Una respuesta al sondeo no garantiza que la siguiente
generación tenga capacidad disponible. La estimación de capacidad no es un
benchmark oficial.

Puedes cancelar la generación y conservar el borrador y los adjuntos para
volver a intentarlo. La disponibilidad, las cuotas y los errores de autenticación
dependen del proveedor.

### Corregir código

La autocorrección utiliza código, logs y capturas del fallo para solicitar un
diagnóstico y una propuesta de cambio. Valida la respuesta y puede **aplicar el
arreglo y volver a ejecutar automáticamente** el flujo, hasta tres intentos.

Cada consulta de reparación tiene un presupuesto de 90 segundos. Ese límite no
incluye toda la ejecución de la automatización. Los intentos se documentan en
`logs/reparaciones/`.

Revisa los resultados con datos de prueba antes de usar este mecanismo en procesos
que envíen mensajes o modifiquen información: una ejecución parcial puede haber
completado algunos pasos antes del error.

[Detalles y contrato de autocorrección →](docs/autocorreccion.md)

## Dónde están tus datos

Las rutas siguientes son relativas a la carpeta instalada o a la raíz del
proyecto si ejecutas desde código:

| Ruta o ubicación | Contenido |
|---|---|
| `automations/` | Código editable de los flujos. |
| `.env` | Configuración local; usa `.env.example` como referencia. |
| `datos/` | Entradas y salidas de los procesos que utilicen esta carpeta. |
| `core/rpa.db` | Historial local de ejecuciones. |
| `logs/` | Registros y evidencia de fallos. |
| `outputs/demo-compras/productos.xlsx` | Plantilla pública de la demo. |
| Administrador de credenciales de Windows | Secretos guardados por la Bóveda mediante keyring. |

El historial y los archivos se guardan localmente. Al usar Gemini, se envían a su
API las instrucciones, capturas y el contexto preparado para esa solicitud.
Los flujos web, HTTP o de correo se comunican con los destinos que indique su
código.

No incluyas contraseñas ni datos privados en capturas o instrucciones.
La validación del código generado ayuda a detectar problemas, pero **no convierte
las automatizaciones en un entorno aislado**: se ejecutan con los permisos de
tu usuario de Windows.

[Seguridad, privacidad y publicación responsable →](SECURITY.md)

## Actualizar o desinstalar

Para actualizar el paquete de Windows, cierra la aplicación, descarga y extrae
la nueva Release y ejecuta su `INSTALL.bat`. El instalador contempla respaldo y
restauración de automatizaciones y configuración. Antes de actualizar, guarda
una copia de tus archivos importantes fuera de la carpeta instalada.

Para desinstalar, ejecuta `UNINSTALL.bat` desde la instalación. Ofrece conservar
las automatizaciones, pero esa opción **no respalda todos tus datos**: copia por
separado `datos/`, `.env`, historial y cualquier otro archivo que quieras
conservar antes de confirmar.

Si usas código fuente, actualizar `main` y actualizar el instalador son operaciones
distintas. Una Release contiene el código de su versión, no todos los cambios
posteriores del repositorio.

## Solución de problemas

| Problema | Qué revisar |
|---|---|
| No encuentro `INSTALL.bat` | Descarga el ZIP de Windows de Releases y extráelo completo. |
| Falta una DLL o `_internal` | Conserva la estructura del paquete; no copies solo el ejecutable. |
| No aparece el acceso directo | Revisa el error del instalador. Si la copia terminó, abre `%LOCALAPPDATA%\LaAutomate\LaAutomate.exe`. |
| `No module named ...` desde código | Instala dependencias usando el Python de `.venv`, como en la guía. |
| `NoSuchDriverException` | Comprueba Chrome/Edge, conexión y compatibilidad del controlador de Selenium. |
| No se encuentra un Excel | Revisa la ruta completa, la hoja y los nombres de columnas que espera ese flujo. |
| No puedo guardar un reporte | Cierra el libro en Excel y comprueba los permisos de su carpeta. |
| Gemini devuelve 429/503 | Revisa cuota/disponibilidad, intenta sondeo o vuelve más tarde. |
| No aparece una automatización | Comprueba su registro y errores de importación; guarda los borradores antes de reiniciar la app. |
| El flujo dejó de funcionar | Revisa el log, las capturas y los cambios en la aplicación objetivo. |
| Hay una cruz roja junto a un commit de GitHub | Abre Actions para ver el fallo de construcción. Una Release publicada puede seguir descargándose aunque falle un workflow. |

Para reportar un problema utiliza [Issues](https://github.com/oft24/LAAutomate/issues).
Incluye versión de Windows, versión de LaAutomate, pasos para reproducirlo,
resultado esperado y error observado. Retira claves y datos personales de las
capturas y logs antes de publicarlos.

## Para desarrolladores

**Tecnologías:** Python, PySide6, Selenium, pywinauto, pandas, openpyxl,
APScheduler, watchdog y la API de Gemini. Las dependencias están en
[`requirements.txt`](requirements.txt).

```text
app/          interfaz, vistas y workers
engine/       ejecución, registro, programador, acciones y grabadoras
core/         configuración, historial, bóveda y cliente de IA
automations/  flujos Python
demos/        catálogo y recursos ficticios
instalador/   scripts de instalación y desinstalación
tests/        pruebas unitarias y de integración
docs/         arquitectura, contratos y guías
```

### Usar la terminal

Desde la raíz del repositorio:

```powershell
.\.venv\Scripts\python.exe manage.py listar
.\.venv\Scripts\python.exe manage.py ejecutar mi_automatizacion
.\.venv\Scripts\python.exe manage.py historial mi_automatizacion
```

### Ejecutar pruebas

Una comprobación inicial de distribución e interfaz:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_distribucion_publica.py tests/test_idioma_copia.py
```

Las pruebas de navegador y de integración con Windows necesitan su entorno
correspondiente. Consulta [desarrollo y pruebas](docs/desarrollo.md) para elegir
las pruebas adecuadas; un resultado unitario no valida por sí solo un sitio
externo ni todas las aplicaciones de escritorio.

### Construir y publicar

Con el entorno del proyecto preparado, ejecuta `empaquetar.bat` para generar
`dist/LaAutomate/`. El paquete público incluye los ejemplos versionados y
excluye los flujos personales sin versionar.

El [workflow de Windows](.github/workflows/windows-release.yml) construye el ZIP
al publicar una etiqueta `v*`; también admite ejecución manual para generar
un artefacto. Cada versión debe usar una etiqueta nueva. Si una Release ya
contiene el ZIP, el workflow conserva ese archivo.

[Empaquetado y distribución →](docs/empaquetado.md)

## Documentación y participación

| Si quieres… | Empieza aquí |
|---|---|
| Entender la arquitectura | [Arquitectura](docs/arquitectura.md) |
| Conocer el contexto del proyecto | [Contexto completo](docs/CONTEXTO-COMPLETO.md) |
| Escribir un flujo | [Crear automatizaciones](docs/escribir-automatizaciones.md) |
| Consultar métodos y parámetros | [Referencia de acciones](docs/acciones.md) |
| Entender la generación con IA | [Asistente IA](docs/asistente-ia.md) |
| Revisar la lógica de reparación | [Autocorrección](docs/autocorreccion.md) |
| Repetir la demo | [Comparativo dinámico](docs/DEMO-COMPARATIVO-COMPRAS.md) |

Las sugerencias, errores reproducibles y experiencias de uso son bienvenidos
en [Issues](https://github.com/oft24/LAAutomate/issues). Si propones un cambio,
explica el problema que resuelve y cómo lo probaste.

**Autor:** [Luis Hernández · oft24](https://github.com/oft24)

## Licencia

Este repositorio es público, pero todavía no tiene una licencia de software
declarada. La publicación del código no concede por sí sola permisos generales
para modificarlo o redistribuirlo; consulta al autor para esos usos.
