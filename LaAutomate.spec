# -*- mode: python ; coding: utf-8 -*-
import os

from PyInstaller.utils.hooks import collect_all

datas = [
    ('app/resources/app_icon.ico', 'app/resources'),
    ('app/resources/app_icon.png', 'app/resources'),
    ('docs/GEMINI_SYSTEM_PROMPT.md', 'docs'),
    ('docs/PRACTICAS.md', 'docs'),
    ('docs/arquitectura.md', 'docs'),
    ('docs/acciones.md', 'docs'),
    ('docs/logica-grabadora.md', 'docs'),
]
binaries = []
hiddenimports = ['win32timezone', 'pywintypes', 'pythoncom']
tmp_ret = collect_all('keyring')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('selenium')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('pynput')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['app/main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
# Qt6Core enlaza icuuc.dll y en Windows 10 eso lo resuelve el ICU del propio
# sistema (System32\icuuc.dll, un forwarder de 29 KB). PyInstaller, al rastrear
# dependencias, encuentra OTRO icuuc.dll en el PATH y lo copia junto al .exe:
# esa copia local eclipsa a la del sistema, no exporta los ucnv_* que Qt pide y
# el .exe muere al arrancar con "DLL load failed while importing QtGui"
# (WinError 127) -- sin sintoma alguno durante el build. Se excluyen para que
# Windows resuelva ICU igual que cuando la app corre desde el venv.
a.binaries = [
    b for b in a.binaries
    if not os.path.basename(b[0]).lower().startswith(("icuuc", "icudt", "icuin"))
]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='LaAutomate',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app/resources/app_icon.ico',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='LaAutomate',
)
