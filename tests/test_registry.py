import pytest

from engine.registry import descubrir, eliminar, listar, obtener, registrar


def test_descubrir_registra_todas_las_carpetas_que_hay_en_disco() -> None:
    """No se nombra ninguna automatizacion concreta a proposito: antes esta
    prueba fijaba `alerta_diaria_errores` y fallaba en cuanto alguien la
    borraba, con un mensaje que no decia nada sobre el registry."""
    from engine.almacen import listar_en_disco

    registro = descubrir()
    en_disco = listar_en_disco()

    assert en_disco, "el repo debe traer al menos una automatizacion de ejemplo"
    faltan = [n for n in en_disco if n not in registro]
    assert not faltan, f"estan en disco pero no en el registry: {faltan}"


def test_spec_conserva_metadatos_del_decorador() -> None:
    """Se apoya en curp_desde_excel, la automatizacion de ejemplo que el
    repo conserva. Si algun dia se borra, cambia el nombre aqui: lo que se
    prueba es que los tres valores del decorador llegan intactos al spec,
    no esta automatizacion en particular."""
    descubrir()
    spec = obtener("curp_desde_excel")

    assert spec.categoria == "tramites"
    assert spec.disparador == "manual"
    assert spec.cls.__name__ == "CurpDesdeExcel"


def test_eliminar_quita_del_registry() -> None:
    from engine.automation_base import BaseAutomation

    @registrar(nombre="prueba_temporal_a_eliminar")
    class _AutomatizacionDePrueba(BaseAutomation):
        def ejecutar(self):
            pass

    assert "prueba_temporal_a_eliminar" in {s.nombre for s in listar()}

    eliminar("prueba_temporal_a_eliminar")

    assert "prueba_temporal_a_eliminar" not in {s.nombre for s in listar()}
    with pytest.raises(KeyError):
        obtener("prueba_temporal_a_eliminar")


def test_eliminar_nombre_inexistente_no_falla() -> None:
    eliminar("esto_no_existe_para_nada")  # no debe lanzar excepcion
