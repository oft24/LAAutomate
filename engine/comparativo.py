"""Validación y comparación de ofertas para el flujo de compras."""
from decimal import Decimal, InvalidOperation


def solicitudes_validas(filas):
    solicitudes = []
    vistos = set()
    for numero, fila in enumerate(filas, 2):
        activo = str(fila.get('Activo', '')).strip().casefold()
        sku = str(fila.get('SKU', '')).strip().upper()
        if activo in ('no', 'nan', ''):
            continue
        if activo not in ('si', 'sí'):
            raise ValueError(f'Fila {numero}: Activo debe ser Sí o No.')
        if not sku or sku == 'NAN' or not all(c.isascii() and (c.isalnum() or c == '-') for c in sku):
            raise ValueError(f'Fila {numero}: SKU vacío o inválido.')
        if sku in vistos:
            raise ValueError(f'Fila {numero}: SKU duplicado {sku}; usa una sola fila con la cantidad total.')
        try:
            cantidad = Decimal(str(fila.get('Cantidad')))
        except InvalidOperation:
            raise ValueError(f'Fila {numero}: cantidad inválida.') from None
        if not cantidad.is_finite() or cantidad <= 0 or cantidad != cantidad.to_integral_value():
            raise ValueError(f'Fila {numero}: Cantidad debe ser un entero positivo.')
        vistos.add(sku)
        solicitudes.append((sku, int(cantidad)))
    if not solicitudes:
        raise ValueError('No hay productos activos. Agrega SKU, Cantidad y Activo=Sí al Excel.')
    return solicitudes


def comparar(sku, cantidad, ofertas):
    filas = []
    for oferta in ofertas:
        if len(oferta) != 6 or oferta[2] != sku:
            raise ValueError(f'La página devolvió una oferta inválida para {sku}.')
        try:
            precio, envio, stock = (Decimal(str(x)) for x in oferta[3:])
        except InvalidOperation:
            raise ValueError(f'Precio, envío o stock inválido para {sku}.') from None
        if not all(n.is_finite() and n >= 0 for n in (precio, envio, stock)) or stock != stock.to_integral_value():
            raise ValueError(f'Precio, envío o stock fuera de rango para {sku}.')
        total = (precio * cantidad + envio).quantize(Decimal('0.01'))
        filas.append({'SKU': sku, 'Producto': oferta[1], 'Proveedor': oferta[0],
                      'Cantidad': cantidad, 'Precio unitario MXN': float(precio),
                      'Envío por pedido MXN': float(envio), 'Total MXN': float(total),
                      'Stock': int(stock), 'Resultado': 'Disponible' if stock >= cantidad else 'Stock insuficiente'})
    elegibles = [fila['Total MXN'] for fila in filas if fila['Resultado'] == 'Disponible']
    if elegibles:
        menor = min(elegibles)
        for fila in filas:
            if fila['Resultado'] == 'Disponible' and fila['Total MXN'] == menor:
                fila['Resultado'] = 'MEJOR OPCIÓN'
    if not filas:
        filas.append({'SKU': sku, 'Producto': '', 'Proveedor': '', 'Cantidad': cantidad,
                      'Precio unitario MXN': None, 'Envío por pedido MXN': None,
                      'Total MXN': None, 'Stock': None, 'Resultado': 'Sin resultados'})
    return sorted(filas, key=lambda f: (f['Resultado'] == 'Stock insuficiente', f['Total MXN'] or 0, f['Proveedor']))
