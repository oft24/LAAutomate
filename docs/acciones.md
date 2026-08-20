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
| `screenshot_error(nombre)` | Guarda una captura en `logs/screenshots/`. Lo llama el runner solo. |
| `cerrar()` | Cierra el navegador si estaba abierto. |

Las esperas son explícitas: no hace falta `time.sleep` entre pasos.

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
