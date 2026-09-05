from unittest.mock import MagicMock
import pytest
from engine.actions.desktop import DesktopActions


def test_nombre_sin_path_abre_acceso_exacto(tmp_path, monkeypatch):
    acceso = tmp_path / "Discord.lnk"
    acciones = DesktopActions(MagicMock())
    monkeypatch.setattr("engine.actions.desktop.shutil.which", lambda c: None)
    monkeypatch.setattr(acciones, "_accesos_inicio", lambda n: [acceso])
    abrir = MagicMock()
    monkeypatch.setattr("engine.actions.desktop.os.startfile", abrir)
    acciones._lanzar_aplicacion("discord", "Discord")
    abrir.assert_called_once_with(str(acceso))


@pytest.mark.parametrize("cantidad", [0, 2])
def test_ambiguedad_no_lanza(cantidad, monkeypatch):
    acciones = DesktopActions(MagicMock())
    monkeypatch.setattr("engine.actions.desktop.shutil.which", lambda c: None)
    monkeypatch.setattr(acciones, "_accesos_inicio", lambda n: ["x"] * cantidad)
    abrir = MagicMock()
    monkeypatch.setattr("engine.actions.desktop.os.startfile", abrir)
    with pytest.raises(RuntimeError, match="acceso único"):
        acciones._lanzar_aplicacion("editor", "Editor")


def test_discord_prefiere_lanzador(tmp_path, monkeypatch):
    from pathlib import Path
    ejecutable = tmp_path / "Update.exe"
    ejecutable.touch()
    acciones = DesktopActions(MagicMock())
    monkeypatch.setattr("engine.actions.desktop.shutil.which", lambda c: None)
    monkeypatch.setattr(acciones, "_accesos_inicio", lambda n: [Path("viejo.lnk"), Path("nuevo.lnk")])
    shell = MagicMock()
    shell.CreateShortcut.side_effect = [MagicMock(TargetPath="no-existe.exe", Arguments=""), MagicMock(TargetPath=str(ejecutable), Arguments="--processStart Discord.exe")]
    monkeypatch.setattr("win32com.client.Dispatch", lambda nombre: shell)
    abrir = MagicMock()
    monkeypatch.setattr("engine.actions.desktop.os.startfile", abrir)
    acciones._lanzar_aplicacion("discord", "Discord")
    abrir.assert_called_once_with("nuevo.lnk")


def test_comando_sin_shell(monkeypatch):
    acciones = DesktopActions(MagicMock())
    lanzar = MagicMock()
    monkeypatch.setattr("engine.actions.desktop.subprocess.Popen", lanzar)
    acciones._lanzar_aplicacion('"C:/Apps/Discord/Update.exe" --processStart Discord.exe', "Discord")
    assert lanzar.call_args.kwargs == {"shell": False}


def test_cerrada_lanza_una_vez_y_espera_ventana(monkeypatch):
    acciones = DesktopActions(MagicMock())
    acciones._ventana = MagicMock()
    monkeypatch.setattr(acciones, "_intentar_atajo", MagicMock(side_effect=[False, False, True]))
    monkeypatch.setattr(acciones, "_atajo_tras_despertar", lambda **kw: False)
    monkeypatch.setattr("engine.actions.desktop._hwnds_que_coinciden", lambda *a, **kw: [])
    monkeypatch.setattr("engine.actions.desktop.time.sleep", lambda *a: None)
    lanzar = MagicMock()
    monkeypatch.setattr(acciones, "_lanzar_aplicacion", lanzar)
    assert acciones.iniciar_o_conectar("editor", "Editor") is acciones._ventana
    lanzar.assert_called_once_with("editor", None)


def test_abierta_no_lanza(monkeypatch):
    acciones = DesktopActions(MagicMock())
    monkeypatch.setattr(acciones, "_intentar_atajo", lambda **kw: True)
    lanzar = MagicMock()
    monkeypatch.setattr(acciones, "_lanzar_aplicacion", lanzar)
    acciones.iniciar_o_conectar("editor", "Editor")
    lanzar.assert_not_called()


def test_referencia_llega_a_ambos_prompts():
    from core.gemini_client import construir_contexto_proyecto
    from engine.autocorreccion import Autocorrector, Intento
    generacion = construir_contexto_proyecto()
    reparacion = Autocorrector(MagicMock())._prompt("prueba", "codigo", Intento(numero=1, error="cerrada", acciones=""))
    for texto in (generacion, reparacion):
        assert "nombre_aplicacion=" in texto
        assert "no desde un checkpoint" in texto


def test_lanzamiento_sin_ventana_falla_acotado(monkeypatch):
    acciones = DesktopActions(MagicMock())
    monkeypatch.setattr(acciones, "_intentar_atajo", lambda **kw: False)
    monkeypatch.setattr(acciones, "_atajo_tras_despertar", lambda **kw: False)
    monkeypatch.setattr("engine.actions.desktop._hwnds_que_coinciden", lambda *a, **kw: [])
    monkeypatch.setattr("engine.actions.desktop.time.monotonic", MagicMock(side_effect=[0, 31]))
    lanzar = MagicMock()
    monkeypatch.setattr(acciones, "_lanzar_aplicacion", lanzar)
    with pytest.raises(TimeoutError, match="ventana utilizable"):
        acciones.iniciar_o_conectar("editor", "Editor", tiempo_espera=30)
    lanzar.assert_called_once()


@pytest.mark.parametrize("espera", [0, -1, 121, float("nan")])
def test_espera_invalida_no_lanza(espera, monkeypatch):
    acciones = DesktopActions(MagicMock())
    lanzar = MagicMock()
    monkeypatch.setattr(acciones, "_lanzar_aplicacion", lanzar)
    with pytest.raises(ValueError):
        acciones.iniciar_o_conectar("editor", "Editor", tiempo_espera=espera)
    lanzar.assert_not_called()
