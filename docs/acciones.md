# Referencia de acciones

Todo lo que sigue está disponible como atributo de `self` dentro de `ejecutar()`. Lo
inyecta el runner al instanciar la automatización (`engine/actions/__init__.py`), y
cada acción escribe en el log de esa ejecución.

La app trae esta misma referencia en la pestaña **Wiki**, buscable.

---

## `self.web` — navegador (Selenium)

`engine/actions/web.py`. Chrome, con reserva automática a Edge si Chrome no está
disponible. El driver se crea la primera vez que se usa y el runner lo cierra siempre
al terminar, falle o no.

| Método | Qué hace |
|---|---|
| `ir_a(url)` | Navega a la URL. |
| `click(selector, by=By.CSS_SELECTOR)` | Espera a que el elemento sea clickeable y hace clic. |
| `escribir(selector, texto, by=By.CSS_SELECTOR)` | Espera visibilidad, limpia el campo y escribe. |
| `leer_texto(selector, by=By.CSS_SELECTOR)` | Espera visibilidad y devuelve el texto. |
| `seleccionar(selector, valor=..., texto=..., by=...)` | Elige una opción de un `<select>`. **Un desplegable no se automatiza escribiendo dentro**: hay que usar esto o el formulario se envía vacío, sin error. Prefiere `valor` (el `value` del `<option>`), que no cambia con el idioma. |
| `descargar_en(carpeta)` | Manda las descargas del navegador a esa carpeta. Hay que llamarlo **antes** del primer `ir_a()`: Chrome fija las preferencias de descarga al arrancar y no las relee. |
| `esperar_descarga(carpeta, extension=".pdf", timeout=30)` | Espera a que la descarga termine de verdad. Chrome escribe primero un `.crdownload` y lo renombra al acabar, así que mirar solo "hay un archivo nuevo" devuelve a veces un PDF a medio escribir. Devuelve `None` si se agota el tiempo. |
| `screenshot_error(nombre)` | Guarda una captura en `logs/screenshots/`. Lo llama el runner solo. |
| `cerrar()` | Cierra el navegador entero, con todas sus pestañas. |

Las esperas son explícitas: no hace falta `time.sleep` entre pasos.

### Pestañas

| Método | Qué hace |
|---|---|
| `pestanas()` | Títulos de las pestañas abiertas, en el orden del navegador. Deja el foco donde estaba. |
| `cambiar_a_pestana(referencia)` | Cambia de pestaña por índice (`0`, `1`…) o por un fragmento de su título o URL. Devuelve el título. |
| `cambiar_a_pestana_nueva(timeout=None)` | Espera a que aparezca una pestaña que no existía y cambia a ella. **Es el método a usar justo después del click que la abre.** |
| `nueva_pestana(url=None)` | Abre una pestaña, cambia a ella y opcionalmente navega. |
| `cerrar_pestana()` | Cierra la pestaña actual y deja el foco en otra válida. |

**Por qué cambiar de pestaña tiene que ser explícito.** Selenium no sigue a una
pestaña nueva por su cuenta. Cuando un click abre una (`target="_blank"`,
`window.open`, un "abrir en pestaña nueva"), el navegador se la muestra al
usuario pero el driver se queda apuntando a la pestaña **vieja**: los pasos
siguientes se ejecutan contra la página anterior y fallan con
`NoSuchElementException` — o peor, encuentran un elemento con el mismo selector
y hacen algo en la página equivocada, sin error y sin aviso.

```python
self.web.ir_a("https://portal.interno/facturas")
self.web.click("#ver-comprobante")        # esto abre una pestaña
self.web.cambiar_a_pestana_nueva()        # sin esta línea, lo de abajo
folio = self.web.leer_texto("#folio")     # se leería de la pestaña anterior
self.web.cerrar_pestana()                 # vuelve a la pestaña del portal
```

Prefiere `cambiar_a_pestana("factur")` sobre `cambiar_a_pestana(1)`: el índice de
una pestaña depende del orden en que se abrieron, que no es estable entre
corridas cuando la aplicación abre pestañas sola. La búsqueda por texto mira el
título **y** la URL, y la URL suele ser lo más estable de los dos (el título de
una SPA cambia solo: `"(3) Bandeja de entrada"`).

Dos pestañas del mismo navegador comparten sesión y cookies; dos navegadores
distintos no. Por eso, para trabajar dos sistemas en paralelo con la misma
sesión, `nueva_pestana()` es lo correcto y abrir un segundo `WebActions` no.

La Grabadora web ya genera estas llamadas sola: si durante la grabación un click
abre una pestaña, la grabadora la sigue y emite `cambiar_a_pestana_nueva()` en el
código generado.

---

## `self.excel` — Excel

`engine/actions/excel.py`.

| Método | Qué hace |
|---|---|
| `leer(ruta, hoja=0)` | Lee con pandas y devuelve las filas como lista de diccionarios. |
| `escribir(ruta, filas, hoja="Sheet1")` | Escribe una lista de diccionarios a un `.xlsx`. |
| `com()` | Devuelve `Excel.Application` por COM, para controlar Excel en vivo. |

`leer`/`escribir` no necesitan que Excel esté instalado; `com()` sí.

---

## `self.http` — APIs REST

`engine/actions/http_client.py`. Sesión de `requests` compartida y timeout puesto.

| Método | Qué hace |
|---|---|
| `get(url, **kwargs)` | GET con la sesión compartida. |
| `post(url, **kwargs)` | POST con la sesión compartida. |
| `con_token(token)` | Agrega el header `Authorization: Bearer …` y devuelve `self` (encadenable). |

```python
datos = self.http.con_token(self.credenciales.token).get(url).json()
```

---

## `self.correo` — correo

`engine/actions/email_actions.py`. Dos caminos: Outlook instalado (COM) o SMTP.

| Método | Qué hace |
|---|---|
| `enviar_outlook(para, asunto, cuerpo)` | Manda desde el Outlook de la máquina. |
| `buscar_outlook_por_remitente(...)` | Busca correos en Outlook filtrando por remitente. |
| `enviar_smtp(host, puerto, usuario, password, para, asunto, cuerpo)` | Manda por SMTP. |

---

## `self.escritorio` — apps de escritorio

`engine/actions/desktop.py`. pywinauto sobre UI Automation, con pyautogui como
respaldo para apps sin árbol de accesibilidad usable.

| Método | Qué hace |
|---|---|
| `iniciar_o_conectar(comando, titulo_regex, tiempo_espera=20)` | Conecta con la app si ya está abierta; si no, la lanza. |
| `conectar_por_titulo(titulo_regex, tiempo_espera=10)` | Conecta **solo** con una ventana ya abierta. |
| `conectar_por_clase(clase, tiempo_espera=10)` | Igual, pero por clase de ventana (`Shell_TrayWnd`, etc.). |
| `click_por_texto(texto, control_type=...)` | Clic en el control con ese texto visible. Lo preferido: sobrevive a que la ventana se mueva. |
| `click_en(x, y, pausa=0.08)` | Clic por coordenadas, relativas a la ventana conectada. |
| `click_por_imagen(ruta_imagen, confianza=0.9)` | Busca una imagen en pantalla y hace clic. Último recurso. |
| `escribir(texto)` | Escribe en el control con foco. |
| `atajo(teclas)` | Combinación de teclas (`"^s"`, `"%{F4}"`…). |
| `esperar(segundos)` | Pausa explícita. |
| `leer_items_lista(control_type="ListItem")` | Devuelve los textos de una lista. |
| `capturar_pantalla(nombre)` | Guarda una captura en `logs/screenshots/`. |

Los `titulo_regex` son **expresiones regulares**, no texto literal: pywinauto empareja
con `title_re`. Si el título trae espacios, paréntesis o puntos, escápalos —
`re.escape()` es la forma segura de armarlos cuando el título depende de una variable.

### Varias aplicaciones en una misma automatización

`self.escritorio` mantiene **una** ventana conectada a la vez. Cambiar de
aplicación es volver a conectar: cada `conectar_por_titulo()` /
`conectar_por_clase()` reemplaza la ventana activa, y todo lo que venga después
(`click_por_texto`, `escribir`, `atajo`) va dirigido a esa.

```python
self.escritorio.conectar_por_titulo(re.escape("Calculadora"))
self.escritorio.click_por_texto("5", control_type="Button")

self.escritorio.conectar_por_titulo(r".* - Bloc de notas")   # otra app
self.escritorio.escribir("resultado pegado aquí")            # va al Bloc de notas
```

No hace falta cerrar ni "desconectar" la anterior: sigue abierta y se puede
volver a ella con otro `conectar_por_titulo()`. El estado que se pierde al
cambiar es solo cuál es la ventana activa.

**Una app recién lanzada acepta la conexión antes de aceptar teclas.** Conectar
solo espera a que la ventana *exista*; escribir de inmediato hace que las
primeras teclas se pierdan mientras la app termina de inicializarse. Comprobado
con el Bloc de notas: `"hola desde LaAutomate"` llegó como `"holae LaAutomate"`.
Si acabas de lanzar la aplicación, pon un `self.escritorio.esperar(2)` antes de
la primera escritura. Conectar a una app **ya abierta** no tiene este problema.

**Si la app está minimizada o en segundo plano**, `conectar_por_titulo()` la
despierta sola. Vale la pena saber por qué: Windows "encoge" (*cloak*) las
ventanas de apps UWP suspendidas, y una ventana así es invisible para UI
Automation aunque `IsWindowVisible()` diga que sí — `connect()` se quedaba
esperando hasta agotar el tiempo, con un `TimeoutError` sin pistas, sobre una app
que estaba perfectamente abierta. Ambos métodos reintentan tras restaurarla.

**El texto de la captura no es el localizador.** `click_por_texto` busca el nombre
de ACCESIBILIDAD del control, que a menudo no es lo que está dibujado. En la
Calculadora de Windows en español, los botones `1`, `×` y `=` se llaman `Uno`,
`Multiplicar por` y `Es igual a`. Si dudas, lee los nombres reales con
`self.escritorio.leer_items_lista("Button")`, o resuélvelo por teclado con
`escribir(...)`/`atajo(...)`, que no dependen del idioma.

**Conectar es instantáneo, aunque tengas medio escritorio abierto.** Los tres
métodos de conexión buscan primero la ventana con `EnumWindows` de Win32 y luego
conectan por *handle*; solo caen a la búsqueda por título/clase de pywinauto si hay
más de una ventana que coincide (ahí se prefiere que pywinauto lance su
`ElementAmbiguousError` antes que elegir una por nuestra cuenta y teclear en la
equivocada). El motivo es medido, en un equipo con 389 ventanas de nivel superior:

| | |
|---|---|
| `connect(handle=hwnd)` | 0,0 s |
| `connect(title_re="Calculadora")` | no volvió en 2 minutos |

No es que fuera lento: se colgaba, porque UI Automation recorre el escritorio
entero. Y de ese cuelgue no se sale: el botón **Cancelar** inyecta una excepción con
`PyThreadState_SetAsyncExc`, que solo surte efecto en el siguiente *bytecode* de
Python — dentro de una llamada C larga, nunca.

Para **grabar** un proceso que toca varias apps, la vista Grabadora tiene la
casilla *"Cualquier ventana (sin candado)"*; sin ella solo se graba la ventana
del primer click. Ver [Lógica de la Grabadora](logica-grabadora.md#modo-escritorio)
para por qué el candado existe y cuándo conviene quitarlo.

---

## `self.copiloto` — Microsoft 365 Copilot y Teams

`engine/actions/copilot_teams.py`. Maneja las apps de escritorio de Copilot y Teams por
UI Automation. Requiere ambas abiertas y con sesión iniciada.

| Método | Qué hace |
|---|---|
| `abrir_copilot()` / `abrir_teams()` | Trae la app al frente. |
| `buscar_agente(nombre)` / `clickear_agente(nombre)` | Localiza y abre un agente de Copilot. |
| `enviar_prompt(nombre_agente, texto)` | Escribe el prompt y lo envía. |
| `leer_tabla_de_respuesta()` | Lee la tabla de la respuesta como texto. |
| `copiar_tabla_de_respuesta()` | Usa el botón "Copy" real de la tabla → queda en el portapapeles con su HTML. |
| `esperar_tabla_de_respuesta(tiempo_maximo=60, intervalo=3)` | Espera a que Copilot termine de responder. |
| `esperar_y_copiar_tabla(...)` | Las dos anteriores juntas. |
| `copiar_respuesta_completa()` | Copia toda la respuesta, no solo la tabla. |
| `abrir_chat_propio(correo, nombre_en_lista)` | Abre en Teams tu chat contigo mismo. |
| `pegar_y_enviar(titulo_esperado, contenido_para_escribir=None)` | Verifica que el chat abierto es el esperado **antes** de enviar, pega y manda. |

Devuelven un `ResultadoCopilot` con `tipo`, `contenido` y `detalle`; conviene revisar
`tipo != "tabla"` antes de confiar en el contenido.

Por qué copiar con el botón real en vez de reformatear el texto: así en Teams llega
como una tabla de verdad. Y `pegar_y_enviar` valida el título de la ventana antes de
mandar, porque enviar el mensaje al chat equivocado no se puede deshacer.

---

## Lo que no es una acción

- **Logs**: `self.logger.info(...)`, `.warning(...)`, `.exception(...)` → van a
  `logs/<nombre>.log` y, si corre desde la app, se ven en vivo en la consola de la
  vista Automatizaciones.
- **Credenciales**: `self.credenciales.usuario / .password / .token`.
- **Configuración del equipo**: `from core.config import var`.
