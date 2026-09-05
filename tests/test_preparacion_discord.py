from unittest.mock import MagicMock
import pytest


def test_click_suelta_mouse_si_se_interrumpe(monkeypatch):
    from engine.actions.desktop import DesktopActions
    acciones = DesktopActions(MagicMock())
    control = MagicMock()
    monkeypatch.setattr(acciones, "_resolver_control", lambda **kw: control)
    def interrumpir(*args):
        raise RuntimeError("cancelado")
    monkeypatch.setattr("engine.actions.desktop.time.sleep", interrumpir)
    with pytest.raises(RuntimeError):
        acciones.click_por_tipo("Edit")
    assert control.click_input.call_args.kwargs == {"button_down": False, "button_up": True}


def test_envio_automatico_de_archivo(tmp_path, monkeypatch):
    from PIL import Image
    from automations.buscar_perros_santa_discord.automation import BuscarPerrosSantaDiscord
    archivo = tmp_path / "perro.png"
    Image.new("RGB", (8, 8)).save(archivo)
    monkeypatch.setattr("automations.buscar_perros_santa_discord.automation.var", lambda nombre, defecto="": str(archivo) if nombre == "DISCORD_IMAGEN_LOCAL" else defecto)
    acciones = MagicMock()
    acciones.escritorio.enviar_imagen_discord.return_value = True
    resultado = BuscarPerrosSantaDiscord(MagicMock(), MagicMock(), acciones).ejecutar()
    acciones.escritorio.enviar_imagen_discord.assert_called_once_with(archivo)
    acciones.escritorio.preparar_archivos_dialogo.assert_not_called()
    acciones.escritorio.escribir.assert_called_once_with("chat-general-no-mudae")
    acciones.web.ir_a.assert_not_called()
    assert resultado.data["enviado"] is True
    assert resultado.data["requiere_revision"] is False


def test_sin_imagen_busca_y_no_envia_si_busqueda_falla(monkeypatch):
    from automations.buscar_perros_santa_discord.automation import BuscarPerrosSantaDiscord
    monkeypatch.setattr("automations.buscar_perros_santa_discord.automation.var", lambda nombre: "")
    acciones = MagicMock()
    acciones.web.guardar_imagen_resultado.side_effect = RuntimeError("sin imágenes")
    with pytest.raises(RuntimeError, match="sin imágenes"):
        BuscarPerrosSantaDiscord(MagicMock(), MagicMock(), acciones).ejecutar()
    acciones.escritorio.conectar_por_titulo.assert_not_called()


def test_worker_no_espera_optimizacion_opcional(monkeypatch):
    from app.workers import AutomationWorker
    corrector = MagicMock()
    fabrica = MagicMock(return_value=corrector)
    monkeypatch.setattr("engine.autocorreccion.Autocorrector", fabrica)
    worker = AutomationWorker(MagicMock(), MagicMock(), autocorregir=True)
    worker._correr()
    assert fabrica.call_args.kwargs["mejorar_prompt"] is False


def test_sin_dialogo_no_se_escribe_archivo(tmp_path, monkeypatch):
    from engine.actions.desktop import DesktopActions
    import pywinauto
    acciones = DesktopActions(MagicMock())
    acciones._ventana = MagicMock(handle=123)
    archivo = tmp_path / "imagen.png"
    archivo.write_bytes(b"prueba")
    monkeypatch.setattr("win32process.GetWindowThreadProcessId", lambda hwnd: (1, 2))
    escritorio = MagicMock()
    escritorio.windows.return_value = []
    monkeypatch.setattr(pywinauto, "Desktop", lambda **kwargs: escritorio)
    with pytest.raises(RuntimeError, match="único diálogo"):
        acciones.preparar_archivos_dialogo([archivo])
    escritorio.window.assert_not_called()


@pytest.mark.parametrize("preview", [True, False])
def test_helper_pega_y_envia_solo_con_preview(tmp_path, monkeypatch, preview):
    from engine.actions.desktop import DesktopActions
    from PIL import Image
    import win32clipboard
    archivo = tmp_path / "adjunto.png"
    Image.new("RGB", (8, 8)).save(archivo)
    for nombre in ("OpenClipboard", "EmptyClipboard", "SetClipboardData", "CloseClipboard"):
        monkeypatch.setattr(win32clipboard, nombre, MagicMock())
    acciones = DesktopActions(MagicMock())
    acciones._ventana = MagicMock()
    acciones.atajo = MagicMock()
    item = MagicMock()
    item.window_text.return_value = archivo.name
    acciones._ventana.descendants.side_effect = [[], [item], [item]]
    if preview:
        assert acciones.enviar_imagen_discord(archivo, timeout=1) is True
        assert [c.args[0] for c in acciones.atajo.call_args_list] == ["^v", "{ENTER}"]
    else:
        with pytest.raises(RuntimeError, match="vista previa"):
            acciones.enviar_imagen_discord(archivo, timeout=0)
        acciones.atajo.assert_called_once_with("^v")
