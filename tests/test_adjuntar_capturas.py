import os
import threading
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from PIL import Image
from PySide6.QtWidgets import QApplication, QFileDialog
from PySide6.QtTest import QTest
from core.gemini_client import validar_capturas, ErrorGemini


@pytest.fixture
def vista(monkeypatch):
    import app.windows.assistant_view as modulo
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(modulo, "tiene_api_key", lambda: False)
    v = modulo.AssistantView()
    yield v
    worker = getattr(v, "_worker_capturas", None)
    if worker:
        worker.wait(5000)
    app.processEvents()
    v.close()


def esperar(v):
    limite = time.monotonic() + 15
    while getattr(v, "_worker_capturas", None) and time.monotonic() < limite:
        QTest.qWait(10)
        time.sleep(0.001)  # Cede el GIL al lector Python, ademas de procesar Qt.
    assert getattr(v, "_worker_capturas", None) is None


def test_selector_no_nativo_cancelable(vista):
    vista._adjuntar_capturas()
    dialogo = vista._dialogo_capturas
    assert dialogo.testOption(QFileDialog.Option.DontUseNativeDialog)
    dialogo.reject()
    assert vista._dialogo_capturas is None
    assert not vista._capturas


def test_carga_fuera_del_hilo_ui_y_duplicados(vista, tmp_path, monkeypatch):
    import app.windows.assistant_view as modulo
    ruta = tmp_path / "captura.png"
    Image.new("RGB", (64, 64)).save(ruta)
    hilos = []
    def validar(rutas):
        hilos.append(threading.get_ident())
        return validar_capturas(rutas)
    monkeypatch.setattr(modulo, "validar_capturas", validar)
    vista._cargar_capturas([str(ruta), str(ruta)])
    esperar(vista)
    assert hilos and hilos[0] != threading.get_ident()
    assert vista._capturas == [ruta]
    assert not vista.lista_capturas.item(0).icon().isNull()
    assert vista.boton_adjuntar.isEnabled()


def test_error_conserva_adjuntos_y_texto(vista, tmp_path):
    ruta = tmp_path / "bien.png"
    Image.new("RGB", (4, 4)).save(ruta)
    vista._cargar_capturas([str(ruta)])
    esperar(vista)
    mala = tmp_path / "mal.png"
    mala.write_bytes(b"no imagen")
    vista.entrada.setPlainText("Mi flujo")
    vista._cargar_capturas([str(mala)])
    esperar(vista)
    assert vista._capturas == [ruta]
    assert vista.entrada.toPlainText() == "Mi flujo"
    assert vista.boton_enviar.isEnabled()


def test_limite_de_capturas(tmp_path):
    ruta = tmp_path / "bien.png"
    Image.new("RGB", (4, 4)).save(ruta)
    with pytest.raises(ErrorGemini, match="10 capturas"):
        validar_capturas([ruta] * 11)


def test_pegar_imagenes_acumula_y_conserva_texto(vista):
    from PySide6.QtCore import QMimeData
    from PySide6.QtGui import QImage
    vista.entrada.setPlainText("Automatiza este flujo")
    for color in ("red", "blue"):
        imagen = QImage(20, 20, QImage.Format.Format_RGB32)
        imagen.fill(color)
        mime = QMimeData()
        mime.setImageData(imagen)
        vista.entrada.insertFromMimeData(mime)
        esperar(vista)
    assert len(vista._capturas) == 2
    assert all(r.is_file() for r in vista._capturas)
    assert vista.lista_capturas.count() == 2
    assert vista.entrada.toPlainText() == "Automatiza este flujo"


def test_pegar_texto_sigue_funcionando(vista):
    from PySide6.QtCore import QMimeData
    mime = QMimeData()
    mime.setText("Mi texto pegado")
    vista.entrada.insertFromMimeData(mime)
    assert vista.entrada.toPlainText() == "Mi texto pegado"
    assert not vista._capturas


def test_pegar_imagen_no_modifica_entrada_bloqueada(vista):
    from PySide6.QtCore import QMimeData
    from PySide6.QtGui import QImage
    mime = QMimeData()
    mime.setImageData(QImage(4, 4, QImage.Format.Format_RGB32))
    vista.entrada.setReadOnly(True)
    vista.entrada.insertFromMimeData(mime)
    assert not vista._capturas
    assert getattr(vista, "_worker_capturas", None) is None
