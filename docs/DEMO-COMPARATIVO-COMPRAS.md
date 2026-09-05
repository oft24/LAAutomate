# Demo dinámica: Excel → navegador → comparativo

## Iniciar

1. Guarda tus borradores y reabre LaAutomate para descubrir `comparativo_compras`.
2. Abre `outputs/demo-compras/productos.xlsx`. La hoja **Productos** contiene SKU, Cantidad, Activo y Descripción.
3. Guarda y cierra Excel. En **Automatizaciones**, selecciona **comparativo_compras** y pulsa **Ejecutar**.
4. El navegador abre `demos/comparativo/catalogo.html`, consulta cada SKU y extrae las ofertas visibles. No requiere servidor ni una tienda externa.
5. Abre el nuevo archivo en `datos/comparativo_compras/`. La ruta exacta aparece en la salida de la aplicación. El reporte no se abre automáticamente para no interrumpir otra ventana de Excel.

La primera ejecución requiere Chrome o Edge y su controlador compatible, como el resto de los flujos web de LaAutomate. El catálogo en sí no necesita internet. La prueba local usó Chrome y un controlador ya instalado.

## Demostrar que es dinámico

La lista inicial contiene `MON-24`, cantidad 1, y `TEC-01`, cantidad 2. Añade una fila a **Productos**, inmediatamente debajo de las actuales:

| SKU | Cantidad | Activo | Descripción |
|---|---:|---|---|
| MOU-01 | 3 | Sí | Mouse Claro inalámbrico |

Guarda, cierra el archivo y vuelve a ejecutar **la misma automatización**. No edites Python. El nuevo reporte debe incluir el mouse. Puedes agregar filas incluso fuera de la tabla visual de Excel: se lee la hoja completa, no un rango fijo ni una lista en memoria.

Solo se procesan filas con Activo=Sí. Usa No para excluir una solicitud. No repitas el SKU; cambia su cantidad en la misma fila. Cantidad debe ser un entero positivo. Los códigos nuevos deben existir en el catálogo para obtener ofertas: escribir un producto inexistente no crea una oferta ni inicia una búsqueda en internet.

## Resultados esperados con este catálogo ficticio

| Solicitud | Mejor proveedor | Total MXN |
|---|---|---:|
| MON-24 × 1 | Pixel | 2599.00 |
| TEC-01 × 2 | Nova | 897.00 |
| MOU-01 × 3 | Nova | 846.00 |

Total = precio unitario × cantidad + envío por pedido **y producto**. IVA ya incluido. No se optimizan envíos combinados entre productos ni compras repartidas entre proveedores.

- Las ofertas con stock menor a la cantidad solicitada se conservan, pero se excluyen de la elección.
- Si hay empate, se marcan todas las mejores ofertas.
- `CAM-01` tiene ofertas sin stock: ninguna debe ganar.
- `NO-EXISTE` produce una fila **Sin resultados**, sin precio cero inventado.
- Cada ejecución relee el Excel y la web, y guarda un reporte con nombre único. La entrada y los reportes anteriores se conservan.
- Los totales del reporte son una fotografía calculada por Python en esa ejecución. Para actualizar cantidades o precios se vuelve a ejecutar; el reporte no es un modelo de fórmulas editable.
- Un proceso completado significa que se generó y releyó el reporte; no significa que todos los productos estén disponibles. El log enumera los productos sin opción.

## Guion para el video

1. Muestra el Excel inicial y di: «Esta lista controla qué consulta la automatización».
2. Pulsa Ejecutar y muestra la navegación por las ofertas.
3. Abre el reporte: precios numéricos, filtros y las mejores opciones resaltadas.
4. Agrega MOU-01 al Excel, guarda y ejecuta otra vez.
5. Muestra el mouse en el segundo reporte: «Agregué un producto, no modifiqué el flujo».

Indica que son datos ficticios de una página local de pruebas. Si aceleras la grabación, señálalo; no presentes el tiempo editado como duración real.

## Validación reproducible

Validado el 5 de septiembre de 2026: 12 pruebas aprobadas entre `test_demo_compras.py` y `test_runner_excel.py`. Incluye dos ejecuciones reales de la clase de automatización con Selenium y acciones Excel; no se pulsaron controles de la interfaz durante esa prueba. La verificación del navegador se hizo sin ventana y solo contra el catálogo local.

`tests/test_demo_compras.py` comprueba cantidades, envío, empate, falta de stock, productos inexistentes, duplicados, lectura del Excel entregado y dos ejecuciones sucesivas con navegador real. La prueba de navegador se habilita con `LAAUTOMATE_DEMO_BROWSER=1`. Usa carpetas temporales; no edita tu lista original.

La plantilla se creó siguiendo la guía de hojas de cálculo: cantidades numéricas, validaciones de entrada y una hoja breve de instrucciones. El formato del reporte lo aplica la propia acción Excel de LaAutomate.

Configuración opcional: `DEMO_COMPRAS_EXCEL` cambia la ruta de entrada y `DEMO_COMPRAS_SALIDA` la carpeta de reportes. No es necesario configurarlas para esta demo.
