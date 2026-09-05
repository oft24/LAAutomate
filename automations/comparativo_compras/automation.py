"""Lee solicitudes de Excel en cada ejecución y consulta el catálogo por navegador."""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
from time import time_ns

from core.config import BASE_DIR, var
from engine.automation_base import AutomationResult, BaseAutomation
from engine.registry import registrar


from engine.comparativo import comparar, solicitudes_validas


@registrar(nombre='comparativo_compras', disparador='manual', categoria='demostración')
class ComparativoCompras(BaseAutomation):
    def ejecutar(self):
        entrada = Path(var('DEMO_COMPRAS_EXCEL', str(BASE_DIR / 'outputs/demo-compras/productos.xlsx'))).resolve()
        destino = Path(var('DEMO_COMPRAS_SALIDA', str(BASE_DIR / 'datos/comparativo_compras'))).resolve()
        if not entrada.is_file():
            raise FileNotFoundError(f'No existe la lista de productos: {entrada}')
        filas_excel = self.excel.leer(entrada, hoja='Productos')
        if filas_excel and not {'SKU', 'Cantidad', 'Activo'} <= filas_excel[0].keys():
            raise ValueError('La hoja Productos requiere las columnas SKU, Cantidad y Activo.')
        solicitudes = solicitudes_validas(filas_excel)
        self.logger.info('Excel releído: %s productos activos.', len(solicitudes))
        url = (BASE_DIR / 'demos/comparativo/catalogo.html').as_uri()
        self.web.ir_a(url)
        comparativo = []
        for sku, cantidad in solicitudes:
            self.logger.info('Consultando %s: %s unidades.', sku, cantidad)
            self.web.escribir('#sku', sku)
            self.web.click('#buscar')
            # El formulario local actualiza el DOM de forma síncrona.
            if self.web.driver.find_element('css selector', '#ofertas').get_attribute('data-sku') != sku:
                raise RuntimeError(f'No se confirmó la búsqueda de {sku}.')
            ofertas = [[celda.text for celda in fila.find_elements('css selector', 'td')]
                       for fila in self.web.driver.find_elements('css selector', '#ofertas tbody tr')]
            resultado = comparar(sku, cantidad, ofertas)
            comparativo.extend(resultado)
            ganadores = [f['Proveedor'] for f in resultado if f['Resultado'] == 'MEJOR OPCIÓN']
            self.logger.info('%s: %s ofertas; mejor opción: %s.', sku, len(ofertas), ', '.join(ganadores) or 'ninguna disponible')
        destino.mkdir(parents=True, exist_ok=True)
        ruta = destino / f'comparativo_{datetime.now():%Y%m%d_%H%M%S}_{time_ns()}.xlsx'
        for fila in comparativo:
            fila['Fuente'] = url
            fila['Consultado'] = datetime.now().isoformat(timespec='seconds')
        self.excel.escribir(ruta, comparativo, hoja='Comparativo')
        self.excel.formatear_comparativo(ruta)
        verificacion = self.excel.leer(ruta, hoja='Comparativo')
        if len(verificacion) != len(comparativo):
            raise RuntimeError('El reporte guardado no tiene todas las filas esperadas.')
        sin_opcion = [sku for sku, _ in solicitudes if not any(f['SKU'] == sku and f['Resultado'] == 'MEJOR OPCIÓN' for f in comparativo)]
        self.logger.info('Reporte verificado: %s. Sin opción disponible: %s', ruta, sin_opcion or 'ninguno')
        return AutomationResult(success=True, message=f'Comparativo creado y verificado: {ruta}',
                                data={'archivo': str(ruta), 'productos': len(solicitudes), 'filas': len(comparativo), 'sin_opcion': sin_opcion})
