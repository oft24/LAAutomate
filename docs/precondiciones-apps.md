# Precondiciones y recuperación de aplicaciones

Contrato compartido por generación y corrección. Una aplicación cerrada no
requiere reescribir el objetivo del flujo ni eliminar pasos.

## Herramienta del motor

`self.escritorio.iniciar_o_conectar(comando, titulo_regex, tiempo_espera=30,
nombre_aplicacion="Nombre instalado exacto")`

1. Busca una ventana existente; evita lanzar otra instancia si ya está abierta.
2. Intenta restaurarla si está minimizada u oculta.
3. Si está cerrada, ejecuta el comando configurado sin shell. Para nombres simples
   ausentes de PATH, busca accesos `.lnk` de nombre exacto en el menú Inicio
   del usuario y del equipo. Es búsqueda de aplicaciones instaladas, no web.
4. Si no existe un acceso único, informa la ambigüedad y requiere configuración;
   no selecciona el primer resultado ni instala nada.
5. Tras lanzar, espera la ventana con un límite de 30 segundos por defecto en
   código generado (el helper tiene valor por defecto 20, configurable hasta 120).
   Si no aparece, lanza TimeoutError con una indicación sobre login/actualizaciones.

No equivale a garantizar sesión iniciada o disponibilidad del servicio. Después
de conectar, comprueba el control/estado necesario para la siguiente acción.
Si falla el foco, no continúes con escritura ciega ni coordenadas de otra ventana.

## Instrucciones para el modelo

- Usa esta herramienta en el código generado; no sustituyas la apertura por
  `conectar_por_titulo`, que solo conecta a algo abierto.
- Los comandos/rutas deben proceder de configuración explícita o de nombres
  instalados reconocibles, no de rutas inventadas en capturas.
- No generes scripts PowerShell, `cmd /c`, descargas o cambios del sistema como
  atajo para abrir una app. El modelo no tiene que importar os/subprocess.
- Usa `from core.config import var` para comandos configurables. Ejemplo:
  `self.escritorio.iniciar_o_conectar(var("DISCORD_COMANDO", "discord"),
  "Discord", tiempo_espera=30, nombre_aplicacion="Discord")`.
- Repara únicamente la precondición: conserva canal, contenido, adjuntos y la
  identidad de la automatización. No omitas la tarea para devolver éxito.
- Si falta login, permiso, instalación o el programa pide intervención real,
  explica el bloqueo; no ocultes el fallo ni prometas resolverlo con más esperas.
- El motor de reparación reejecuta desde el principio, no desde un checkpoint.
  Si ya pudo ocurrir un envío, pago o subida, exige una comprobación de no
  duplicación; si no puede comprobarse, devuelve ESCALATE y safe_to_execute=false.

Esta referencia guía al generador; no transforma automáticamente automatizaciones
existentes. El corrector debe proponer y aplicar un cambio compatible cuando se
solicita «Corregir código». Abrir una app no significa ejecutar su flujo de negocio.
