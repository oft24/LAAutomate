# Asistente IA con Gemini

La vista **Asistente IA** convierte una descripción y hasta varias capturas de
pantalla en un borrador de `automation.py`. Es una ayuda de autoría: nunca ejecuta
la respuesta ni escribe archivos sin que la persona presione **Crear
automatización**.

## Configuración de la API

La opción recomendada es **Configurar clave** dentro de la vista. La clave se guarda
en el Administrador de credenciales de Windows mediante `keyring`; no aparece en la
base SQLite, logs, código ni historial de conversación.

También se puede definir en el `.env` local:

```dotenv
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.7-flash
```

`GEMINI_MODEL` solo fija cuál sale preseleccionado: el desplegable se rellena con los
modelos que **tu cuenta** tiene de verdad (ver abajo).

El `.env` está ignorado por Git. La petición usa el header `x-goog-api-key`; la clave
no forma parte de la URL.

## Contexto que recibe el modelo

En cada envío se incluyen:

1. El prompt versionado en [`GEMINI_SYSTEM_PROMPT.md`](GEMINI_SYSTEM_PROMPT.md).
2. La arquitectura, la referencia de acciones y la lógica de la grabadora.
3. Opcionalmente, el `automation.py` elegido en el panel de contexto.
4. Las capturas adjuntas a ese turno (PNG, JPG o WEBP; máximo 12 MB en total).
5. Hasta los ocho turnos recientes de la conversación actual.

Nunca se adjuntan `.env`, credenciales ni la base de datos. Una imagen solo sale del
equipo cuando la persona la selecciona y envía el mensaje.

La única excepción, y es a petición explícita: el chip **Explicar un error** carga la
cola del log de la automatización elegida y adjunta la captura que el runner tomó en
el momento del fallo. Las dos cosas quedan a la vista antes de enviar —el log en la
caja de entrada, la captura en la lista de adjuntos— y se pueden quitar.

## Elección de modelo

El desplegable no es una lista escrita a mano: se pregunta a la API qué modelos tiene
esa cuenta y se filtran los que soportan `generateContent` (la lista trae también
embeddings, TTS, imagen y agentes con su propio protocolo, que darían un 400 sin
explicación). Los útiles quedan arriba, ordenados por versión descendente; el resto
sigue disponible más abajo por si quieres probar uno a mano.

**Por qué no hay un modelo fijo en el código.** Un modelo retirado sigue apareciendo
en `/models` y contesta 404 al llamarlo. Se comprobó contra una cuenta real:
`gemini-2.5-pro` y `gemini-2.5-flash` —los dos estaban en la lista fija que ofrecía
esta vista— responden *"no longer available to new users"*. Por eso el preferido se
elige por versión, prefiriendo siempre un modelo estable sobre un `-preview` de la
misma versión, y `pro` sobre `flash` sobre `lite`.

## Cuando la API dice que no

Los códigos 429 (cuota del plan gratuito), 500 y 503 ("high demand") son frecuentes y
casi siempre temporales: se midió que el mismo modelo responde bien unos segundos
después. El cliente reintenta hasta dos veces respetando el `retryDelay` que la propia
API sugiere —adivinar de menos vuelve a chocar con la cuota, y de más deja a la
persona esperando— con un tope de 30 s para no colgar la interfaz.

Los errores que no se arreglan esperando (404 de un modelo retirado, 403 sin permiso,
401 de clave inválida) no se reintentan: solo gastarían tiempo. Cada uno se traduce a
un mensaje que dice qué hacer, no solo el código HTTP.

Las partes que el modelo marca `thought: true` —el borrador interno de los modelos con
razonamiento— se descartan: colarlas en la burbuja rompe la extracción del bloque
`python` cuando el borrador también trae uno.

## Corregir una automatización que falló

El chip **Explicar un error** reúne por ti lo que hace falta para diagnosticar:

1. La cola de `logs/<nombre>.log` (12 000 caracteres; el traceback está al final).
   Es el único sitio donde sobrevive el traceback completo: `guardar_ejecucion` solo
   persiste el mensaje en SQLite.
2. La captura que el runner tomó en el instante del fallo, si existe.
3. Si la automatización ni siquiera importa, ese `ImportError` va **antes** que el
   log: es la causa, y el log sería de la última vez que sí corrió.

El desplegable de código de referencia lista lo que hay **en disco**, no solo lo que
el registry cargó bien — una automatización que no compila no está registrada, y es
justo la que más necesita que la mires. Sale marcada como *(no compila)*.

El prompt incluye además los fallos que se han reproducido de verdad en este
proyecto y su arreglo correcto. El más caro de descubrir: `click_por_texto` busca el
nombre de **accesibilidad** del control, no el texto que se ve. En la Calculadora de
Windows en español los botones `1`, `×` y `=` se llaman `Uno`, `Multiplicar por` y
`Es igual a`, así que un modelo que lee la captura genera clicks que fallan con
`ElementNotFoundError`. Tras poner esa regla en el prompt del sistema, un modelo que
antes producía seis clicks frágiles pasó a resolverlo con
`self.escritorio.escribir("12*8=")`, que funciona.

## De respuesta a automatización

El botón **Crear automatización** solo se habilita si la respuesta contiene un bloque
`python`. Antes de guardar se valida que el texto sea Python válido, que no ejecute
acciones al importar el módulo, que sus imports pertenezcan al conjunto esperado, se
pide un nombre seguro para la carpeta y se rechaza sobrescribir una automatización existente.
Después se importa mediante el mismo registry y se muestra en
**Automatizaciones**, donde el código puede revisarse, editarse y ejecutarse.

El modelo puede equivocarse: una captura no garantiza selectores estables ni revela
estados que no aparecen en pantalla. Los placeholders `CAMBIAR_*`, rutas,
credenciales y selectores siempre deben revisarse antes de ejecutar.
