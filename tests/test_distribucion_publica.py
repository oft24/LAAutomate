"""El camino público de instalación debe existir y no empaquetar datos locales."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_instalador_desde_codigo_es_autocontenido():
    contenido = (ROOT / 'INSTALAR_LAAUTOMATE.bat').read_text(encoding='utf-8')
    assert '-m venv .venv' in contenido
    assert '-r requirements.txt' in contenido
    assert 'tools\\crear_acceso_directo.ps1' in contenido
    assert 'Python 3.11' in contenido


def test_paquete_publico_solo_copia_archivos_versionados():
    contenido = (ROOT / 'tools' / 'copiar_paquete_publico.ps1').read_text(encoding='utf-8')
    empaquetar = (ROOT / 'empaquetar.bat').read_text(encoding='utf-8')
    assert 'git -C $raiz ls-files' in contenido
    assert 'copiar_paquete_publico.ps1' in empaquetar
    assert 'xcopy automations' not in empaquetar.lower()


def test_release_de_windows_publica_zip_instalable():
    workflow = (ROOT / '.github' / 'workflows' / 'windows-release.yml').read_text(encoding='utf-8')
    assert 'runs-on: windows-latest' in workflow
    assert 'LaAutomate-Windows-x64.zip' in workflow
    assert 'gh release create' in workflow


def test_readme_explica_release_y_alternativa_desde_codigo():
    readme = (ROOT / 'README.md').read_text(encoding='utf-8')
    assert 'Releases de LaAutomate' in readme
    assert 'INSTALAR_LAAUTOMATE.bat' in readme
    assert 'no contiene `dist/`' in readme
