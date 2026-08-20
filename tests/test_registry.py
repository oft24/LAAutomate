import pytest

from engine.registry import descubrir, eliminar, listar, obtener, registrar


def test_descubrir_encuentra_las_automatizaciones_registradas() -> None:
    registro = descubrir()

    assert "alerta_diaria_errores" in registro


def test_spec_conserva_metadatos_del_decorador() -> None:
    descubrir()
    spec = obtener("alerta_diaria_errores")

    assert spec.categoria == "notificaciones"
    assert spec.disparador == "cron:0 8 * * *"
    assert spec.cls.__name__ == "AlertaDiariaErrores"


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
