# Prompt opcional para generar el flujo desde el asistente

Ya existe una versión funcional llamada comparativo_compras. Este prompt permite mostrar también la generación con IA; usa otro nombre para no reemplazar el flujo probado. Una respuesta nueva de Gemini debe revisarse y probarse por separado.

---

Crea una automatización manual llamada comparativo_compras_ia para LaAutomate. Debe consultar ofertas de productos en un catálogo local de pruebas, usando un Excel como entrada dinámica. No debe comprar, enviar mensajes, ni consultar tiendas reales.

Entrada: BASE_DIR / 'outputs/demo-compras/productos.xlsx', hoja Productos, columnas SKU, Cantidad, Activo y Descripción. Lee el archivo con self.excel.leer al INICIO de cada ejecución. No fijes productos, precios, número de filas ni ganadores en el código. Recorre todas las filas actuales. Procesa Activo=Sí; omite No o filas vacías. Rechaza cantidades no enteras, menores a 1, SKU vacíos y SKU duplicados. No modifiques el archivo de entrada.

Página: (BASE_DIR / 'demos/comparativo/catalogo.html').as_uri(). Ábrela con self.web.ir_a. Para cada SKU usa self.web.escribir('#sku', sku) y self.web.click('#buscar'). Confirma que #ofertas tiene data-sku igual al SKU consultado antes de extraer #ofertas tbody tr. Cada fila contiene seis td en este orden: Proveedor, Producto, SKU, Precio unitario MXN, Envío por pedido MXN y Stock. Usa self.web.driver.find_elements para recorrer todas las filas visibles; no uses índices fijos de ofertas. Los importes usan punto decimal, sin símbolo monetario ni separador de miles. No infieras valores de capturas y no leas el JavaScript de la página como sustituto de la navegación.

Calcula con Decimal: total = precio unitario × cantidad + envío. El envío se cobra una vez por producto y proveedor. Excluye de la elección las ofertas cuyo stock no alcance la cantidad, pero consérvalas con Resultado='Stock insuficiente'. Marca todas las ofertas empatadas en el menor total disponible con Resultado='MEJOR OPCIÓN'. El resto disponible lleva Resultado='Disponible'. Si no hay resultados, escribe una fila con Resultado='Sin resultados' y precios vacíos, no cero. No declares ganador cuando todas las ofertas carecen de stock.

Genera un archivo nuevo en BASE_DIR / 'datos/comparativo_compras', con fecha y sufijo único. Escribe hoja Comparativo con estas columnas y en este orden: SKU, Producto, Proveedor, Cantidad, Precio unitario MXN, Envío por pedido MXN, Total MXN, Stock, Resultado, Fuente, Consultado. Cantidades, importes y stock deben ser números, no textos con '$'. Fuente es la URL consultada y Consultado la fecha de ejecución. Usa self.excel.escribir y después self.excel.formatear_comparativo(ruta), que ya existe en la aplicación y aplica formato y resaltado. El reporte es una fotografía de esa ejecución; no prometas que sus valores cambian sin volver a ejecutar.

Vuelve a leer el reporte para verificar que se guardaron todas las filas. Registra en self.logger los productos procesados, las mejores opciones, las excepciones de disponibilidad y la ruta final. Devuelve AutomationResult(success=True, message=..., data=...) solo después de validar el archivo. No ocultes fallos de lectura, navegación o escritura. No hagas capturas del escritorio completo, ni leas credenciales ni .env como contexto.

Usa BaseAutomation, @registrar, AutomationResult y únicamente APIs e importaciones permitidas por LaAutomate. No ejecutes acciones al importar el módulo. Si una capacidad no está disponible, explícala en vez de inventar métodos.
