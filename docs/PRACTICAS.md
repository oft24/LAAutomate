# Prácticas de automatización aprendidas

Este archivo **se inyecta en el prompt** cada vez que el autocorrector
intenta reparar una automatización, y el propio autocorrector le añade una
línea cada vez que una reparación funciona. La idea es que el sistema no
vuelva a tropezar dos veces con la misma piedra.

Reglas de la casa:

- Una práctica es **una regla accionable**, no una anécdota. «Usa
  `click_por_tipo('Edit')` en campos de texto» sirve; «a veces falla» no.
- Cada una dice **de dónde salió**: qué error real la motivó. Sin eso nadie
  sabe si sigue vigente ni se atreve a borrarla.
- Si dos prácticas se contradicen, gana la más reciente y **se borra la
  vieja**. Un archivo que solo crece acaba siendo ruido.
- Las que están bajo *Verificadas a mano* no las toca el autocorrector: son
  las que se comprobaron ejecutando código de verdad.

---

## Verificadas a mano

### El texto que ves NO es el que busca `click_por_texto`

`click_por_texto` busca el nombre de **accesibilidad** (UI Automation) del
control, que a menudo no es lo que está dibujado en pantalla.

Comprobado en la Calculadora de Windows en español: los botones que se ven
como `1`, `2`, `×` y `=` se llaman de verdad `Uno`, `Dos`,
`Multiplicar por` y `Es igual a`. Un modelo que lee una captura genera
clics por el glifo y falla con `ElementNotFoundError`.

**Qué hacer:**
1. Si la tarea se puede resolver **por teclado**, hazlo:
   `self.escritorio.escribir("12*8=")` funcionó donde seis clics fallaron.
   No depende del idioma ni de la versión de la app.
2. Para saber los nombres reales:
   `self.escritorio.leer_items_lista("Button")`.
3. `click_por_texto` solo con etiquetas de verdad (un botón «Aceptar», una
   entrada de menú) y siempre con `control_type=`.
4. En un campo de texto, `click_por_tipo('Edit')` — nunca su contenido,
   porque el «texto visible» de un Edit es lo que hay escrito dentro.

### Un `<select>` no se rellena escribiendo

Escribir dentro de un desplegable no cambia la selección y el formulario se
envía vacío, **sin error**. Hay que usar `self.web.seleccionar(selector,
valor=...)`, que dispara el evento `change` que la página escucha.

Prefiere `valor` (el atributo `value` del `<option>`) sobre `texto`: el
value no cambia con el idioma de la página.

### El mensaje de error de una web tiene sitio fijo; el resultado no

Buscar el resultado por su **forma** (una expresión regular sobre el texto)
aguanta rediseños. Buscar el ERROR así no funciona: hay que leer el
elemento donde la página lo pinta.

Comprobado en gob.mx/curp: el error vive en `div.alert-danger`
(«El campo primer apellido: No cumple con el formato especificado»),
mientras que el body no contiene nunca las frases que uno esperaría como
«no se encontró». Leer el body buscando esas frases reportaba *«¿cambió la
página?»* en todos los casos — el peor mensaje posible, porque acusa a la
herramienta cuando el problema está en el dato.

Ojo con los `alert-info` fijos (avisos de privacidad, teléfonos de ayuda):
están siempre y tomarlos por un error diría que fallaron todas las filas.

### Conectar con una ventana: por handle, no por título

`Application(backend="uia").connect(title_re=...)` hace que UI Automation
recorra el escritorio entero. Medido con 389 ventanas abiertas:
`connect(handle=hwnd)` tarda 0,0 s; `connect(title_re=...)` no volvió en
2 minutos. No es lento: se cuelga, y el botón Cancelar no puede sacarte de
ahí porque la excepción asíncrona no interrumpe una llamada C.

Ya lo hace `self.escritorio.conectar_por_titulo` internamente.

### Un doble de prueba más cómodo que el original no prueba nada

`GeminiClient.generar()` devuelve un `RespuestaGemini` (texto + modelo +
tokens), no una cadena. El doble de las pruebas devolvía un `str` porque
era más cómodo de escribir. Resultado: 16 pruebas en verde y la primera
ejecución real murió con

    TypeError: expected string or bytes-like object, got 'RespuestaGemini'

Un doble tiene que respetar el **contrato** del objeto real —los tipos que
devuelve, las excepciones que lanza— aunque cueste tres líneas más. Si no,
lo que se prueba es el doble.

### Valida las filas antes de salir a la red

Descubrir en la fila 300 que el estado estaba mal escrito, con 299
consultas ya gastadas contra un servicio con cuota, es el peor resultado
posible. Comprueba las columnas y el formato de cada fila **antes** de
abrir el navegador.

### Nunca adivines un dato ambiguo

En un Excel real, `M` significa «masculino» para unos y «mujer» para otros.
Adivinar devuelve el resultado de otra persona. Rechaza la fila y di por
qué: una corrección en el Excel cuesta menos que un dato incorrecto que
nadie detecta.

---

## Aprendidas por el autocorrector

<!-- El autocorrector añade aquí una línea por cada reparación que
     funcionó. No edites entre estas marcas a mano: reescribe la sección
     entera si hace falta. -->

<!-- INICIO AUTOCORRECTOR -->
<!-- FIN AUTOCORRECTOR -->
