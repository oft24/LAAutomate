# Seguridad y alcance de LaAutomate

## Qué se puede subir al repositorio

El repositorio contiene código, documentación, pruebas y una plantilla de Excel con datos ficticios. Los reportes generados, capturas, logs, bases SQLite y archivos de configuración local quedan fuera mediante `.gitignore`.

Antes de cada publicación se revisan:

- `.env`, llaves API, tokens, contraseñas y certificados.
- `logs/`, `build/`, `dist/`, `datos/`, `outputs/` y `core/rpa.db`.
- Imágenes o Excel producidos por una ejecución local.
- El diff preparado y la lista exacta de archivos del commit.

La clave de Gemini se puede guardar desde la aplicación en Windows Credential Manager mediante la Bóveda. `.env.example` solo contiene nombres y valores vacíos; nunca debe copiarse una clave real a ese archivo.

## Modelo de seguridad de la aplicación

- Las credenciales de automatizaciones se resuelven por nombre desde la Bóveda local; no se escriben en `automation.py`.
- El asistente no recibe `.env` ni la Bóveda como contexto. Las capturas y logs se envían al proveedor de IA únicamente cuando el usuario confirma la generación o la corrección.
- El borrador generado se analiza con AST antes de cargarse. Se restringen las importaciones, las expresiones ejecutables a nivel de módulo y los decoradores de clases a `@registrar`.
- Las respuestas de chat se muestran como texto/Markdown de solo lectura. No cargan recursos locales o remotos ni abren enlaces generados por el modelo.
- La página de demostración de compras es local y usa datos ficticios. No compra productos ni envía mensajes.
- Los flujos de Selenium pueden navegar a sitios externos y la automatización de escritorio puede operar aplicaciones abiertas. Ejecuta solo código que hayas revisado y usa cuentas de prueba cuando sea posible.

## Límites importantes

La validación AST evita que el asistente cargue muchos borradores peligrosos, pero no convierte Python en un sandbox de seguridad. Una automatización que el usuario guarda y ejecuta tiene capacidad de operar el equipo mediante las herramientas que se le inyectan. El modelo de confianza es: usuario local autorizado + revisión del código + credenciales aisladas.

Google, Cyberpuerta y cualquier otra tienda externa pueden usar CAPTCHA, cambios de diseño, límites de frecuencia o condiciones de uso. La aplicación debe detenerse y registrar el bloqueo; no se debe intentar evadirlo. Los precios, existencias, envíos y moneda se deben registrar con su URL y fecha de consulta.

## Checklist antes de `main`

1. `git status --short` y revisión del diff.
2. Escaneo de patrones de secretos sobre archivos rastreados y cambios preparados.
3. Confirmar que no entran `.env`, `core/rpa.db`, `logs/`, `datos/`, `build/`, reportes ni capturas.
4. Ejecutar pruebas unitarias y de UI; las pruebas de red/navegador se identifican por separado.
5. Revisar `git diff --cached --name-status` y `git diff --cached --check`.
6. Crear el commit con el usuario Git configurado por el propietario del repositorio y verificar `git show --format=fuller`.
7. Hacer push explícito a `origin main` y comprobar que `origin/main` apunta al commit publicado.
