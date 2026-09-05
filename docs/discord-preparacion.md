# Envío automático de imagen a Discord

El flujo `buscar_perros_santa_discord` vuelve a navegar al canal mediante Ctrl+K
y ahora pega un archivo real y pulsa Enter automáticamente tras detectar su
nombre en la vista previa. No requiere abrir el selector ni confirmar a mano.

Deja Discord abierto y con sesión iniciada. Opcionalmente configura
`DISCORD_IMAGEN_LOCAL` con una imagen PNG/JPG/WEBP de hasta 12 MB. Si está vacío,
el flujo busca perros con gorro de Santa en Brave Search y guarda la primera
imagen visible de tamaño suficiente dentro de `main`. Es una captura del elemento
imagen en su resolución mostrada, no una descarga del original. No comprueba
semánticamente el contenido: el resultado depende del buscador y su estructura.

Solo confirma éxito al detectar un enlace nuevo al nombre del adjunto en la
accesibilidad de Discord. Si no puede confirmar tras Enter, marca resultado
incierto y no reintenta ni autocorrige, para evitar duplicados. El canal mantiene
la navegación anterior por nombre; presupone la sesión y contexto correctos.
El portapapeles se reemplaza por la lista de archivos que se pegará.

Las pruebas son simuladas, sin envíos reales. La detección de vista previa y
enlace depende de la accesibilidad de la versión instalada de Discord; si no
está expuesta, el flujo informa el límite y no inventa una confirmación.

La corrección iniciada desde la interfaz ya no espera a la optimización
opcional del prompt tras terminar. Los clics liberan el botón en `finally`
cuando se interrumpe la pausa entre presionar y soltar.
