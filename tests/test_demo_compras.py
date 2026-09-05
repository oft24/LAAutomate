import hashlib
import logging
import os
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from automations.comparativo_compras.automation import ComparativoCompras
from engine.comparativo import comparar, solicitudes_validas


def test_cantidad_y_envio_cambian_ganador():
    ofertas = [['Nova','Teclado','TEC-01',399,99,20],['Pixel','Teclado','TEC-01',449,0,15]]
    assert comparar('TEC-01',1,ofertas)[0]['Proveedor'] == 'Pixel'
    resultado = comparar('TEC-01',2,ofertas)
    assert resultado[0]['Proveedor'] == 'Nova'
    assert resultado[0]['Total MXN'] == 897
    assert resultado[0]['Resultado'] == 'MEJOR OPCIÓN'


def test_stock_empates_y_sin_resultados():
    ofertas = [['A','Monitor','MON-24',10,0,0],['B','Monitor','MON-24',20,0,2],['C','Monitor','MON-24',20,0,4]]
    filas = comparar('MON-24',2,ofertas)
    assert len([f for f in filas if f['Resultado']=='MEJOR OPCIÓN']) == 2
    assert filas[-1]['Resultado'] == 'Stock insuficiente'
    assert comparar('MON-24',5,ofertas)[0]['Resultado'] == 'Stock insuficiente'
    assert comparar('XYZ',1,[])[0]['Total MXN'] is None


@pytest.mark.parametrize('cantidad',[0,-1,1.5,'error',float('nan'),float('inf')])
def test_cantidades_invalidas(cantidad):
    with pytest.raises(ValueError):
        solicitudes_validas([{'SKU':'MON-24','Cantidad':cantidad,'Activo':'Sí'}])


def test_duplicados_y_filas_inactivas():
    fila={'SKU':'MON-24','Cantidad':1,'Activo':'Sí'}
    assert solicitudes_validas([fila, {'Activo':'No'}]) == [('MON-24',1)]
    with pytest.raises(ValueError, match='duplicado'):
        solicitudes_validas([fila,fila])


def test_contrato_editor():
    import ast
    from app.windows.assistant_view import _validar_importacion_segura
    _validar_importacion_segura(ast.parse(Path('automations/comparativo_compras/automation.py').read_text(encoding='utf-8')))


@pytest.mark.skipif(os.getenv('LAAUTOMATE_DEMO_BROWSER') != '1', reason='Prueba explícita con navegador local')
def test_navegador_excel_y_segunda_ejecucion(tmp_path, monkeypatch):
    from engine.actions.excel import ExcelActions
    from engine.actions.web import WebActions
    from openpyxl import load_workbook
    logger=logging.getLogger('demo-test')
    excel=ExcelActions(logger)
    web=WebActions(logger,headless=True)
    entrada=tmp_path/'productos.xlsx'
    salida=tmp_path/'reportes'
    monkeypatch.setenv('DEMO_COMPRAS_EXCEL',str(entrada))
    monkeypatch.setenv('DEMO_COMPRAS_SALIDA',str(salida))
    pedidos=[{'SKU':'MON-24','Cantidad':1,'Activo':'Sí'}, {'SKU':'TEC-01','Cantidad':2,'Activo':'Sí'}]
    # Primera ejecución con la plantilla entregada; segunda con filas añadidas.
    shutil.copyfile(Path('outputs/demo-compras/productos.xlsx'), entrada)
    actions=SimpleNamespace(web=web,excel=excel,http=None,correo=None,escritorio=None,copiloto=None)
    instancia=ComparativoCompras(logger,None,actions)
    try:
        antes=hashlib.sha256(entrada.read_bytes()).digest()
        primero=instancia.ejecutar()
        assert primero.success and primero.data['productos']==2 and primero.data['filas']==9
        assert hashlib.sha256(entrada.read_bytes()).digest()==antes
        filas=excel.leer(primero.data['archivo'],hoja='Comparativo')
        mejores={f['SKU']:(f['Proveedor'],f['Total MXN']) for f in filas if f['Resultado']=='MEJOR OPCIÓN'}
        assert mejores=={'MON-24':('Pixel',2599),'TEC-01':('Nova',897)}
        # La misma instancia debe releer el archivo, no usar una lista guardada en memoria.
        pedidos += [{'SKU':'MOU-01','Cantidad':3,'Activo':'Sí'}, {'SKU':'CAM-01','Cantidad':1,'Activo':'Sí'}, {'SKU':'NO-EXISTE','Cantidad':1,'Activo':'Sí'}]
        excel.escribir(entrada,pedidos,hoja='Productos')
        segundo=instancia.ejecutar()
        assert segundo.data['productos']==5
        assert segundo.data['sin_opcion']==['CAM-01','NO-EXISTE']
        assert segundo.data['archivo']!=primero.data['archivo']
        assert Path(primero.data['archivo']).is_file()
        filas=excel.leer(segundo.data['archivo'],hoja='Comparativo')
        mouse=[f for f in filas if f['SKU']=='MOU-01' and f['Resultado']=='MEJOR OPCIÓN']
        assert len(mouse)==1 and mouse[0]['Proveedor']=='Nova' and mouse[0]['Total MXN']==846
        libro=load_workbook(segundo.data['archivo'])
        assert libro['Comparativo']['G2'].data_type=='n'
        assert libro['Comparativo'].auto_filter.ref
        assert len(libro['Comparativo'].conditional_formatting)==1
        libro.close()
        web.escribir('#sku','MON-24')
        web.click('#buscar')
        web.driver.set_window_size(1360, 960)
        web.driver.save_screenshot(str(Path('build')/'demo-compras-browser.png'))
    finally:
        web.cerrar()
