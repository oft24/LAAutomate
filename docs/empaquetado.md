---
tags: [laautomate, distribucion]
alias: ["Empaquetado", "Instalador"]
---

# Empaquetado e instalación

La app se distribuye como una carpeta con `LaAutomate.exe` dentro, generada por
PyInstaller, más dos `.bat` que instalan y desinstalan.

## Generar el paquete

```bash
empaquetar.bat
```

Hace tres cosas:

1. `PyInstaller LaAutomate.spec --noconfirm` -> genera `dist/LaAutomate/`.
2. Copia al lado del `.exe` lo que PyInstaller no incluye: `README.md`, `.env.example`,
   la carpeta `automations/`, la demo local (`demos/` y la plantilla Excel), la guía
   de la demo y los dos `.bat` del instalador.
3. Te dice qué correr para instalar.

El paso 2 existe porque **PyInstaller borra `dist/LaAutomate/` en cada build**. Por eso
los `.bat` viven versionados en `instalador/` y se copian al final, en vez de crearse a
mano en cada rebuild.

La copia la realiza `tools/copiar_paquete_publico.ps1` a partir de `git ls-files`.
Por diseño, solo incorpora archivos versionados: una automatización creada en la
instalación local, un reporte o una captura sin seguimiento nunca entra al paquete
público por accidente.

## Instalación sencilla desde el repositorio

`INSTALAR_LAAUTOMATE.bat`, en la raíz, es el camino para una persona que descargó
el código: comprueba Python 3.11+, crea `.venv`, instala `requirements.txt`, prepara
`.env` y genera el acceso directo del escritorio. No construye PyInstaller y la
carpeta descargada debe conservarse.

## GitHub Releases

`.github/workflows/windows-release.yml` se puede ejecutar manualmente para obtener
un artefacto de prueba. Al subir una etiqueta `v*`, el mismo flujo ejecuta las
pruebas deterministas, construye `LaAutomate-Windows-x64.zip` en Windows y lo adjunta
a una GitHub Release. Esa es la distribución recomendada para usuarios sin Python.

`empaquetar.bat` usa `.venv\Scripts\python.exe`: necesitas el entorno virtual del
proyecto creado e instalado (ver [desarrollo](desarrollo.md)), con `pyinstaller` dentro.

## Instalar

```bash
dist\LaAutomate\INSTALL.bat
```

- Instala en **`%LOCALAPPDATA%\LaAutomate`**, no en el escritorio: son ~220 MB de
  binarios, y meterlos en una carpeta sincronizada con OneDrive la sincronizaría
  eternamente y puede bloquear archivos en pleno uso.
- Deja un **acceso directo en el escritorio**, que es lo que el usuario abre.
- El escritorio se lee del registro (`HKCU\…\Shell Folders\Desktop`), no se adivina:
  con OneDrive corporativo la carpeta puede llamarse `OneDrive - Empresa\Desktop`, y
  suponer `%USERPROFILE%\Desktop` fallaba en silencio dejando la app donde el usuario
  nunca la ve.
- **Conserva tus automatizaciones, tu `.env`, el historial, los logs y `datos/`** si ya
  había una instalación previa: los respalda en `%LOCALAPPDATA%\LaAutomate_respaldos`,
  copia la versión nueva y los restaura encima.
- Migra desde el nombre anterior (`Luisautomate`): trae sus automatizaciones, borra su
  acceso directo y elimina la instalación vieja — salvo que tuviera automatizaciones
  propias sin migrar, en cuyo caso no la toca y te avisa dónde quedó.

## Desinstalar

```bash
%LOCALAPPDATA%\LaAutomate\UNINSTALL.bat
```

Pide confirmación escribiendo `SI`, ofrece copiar tus automatizaciones al escritorio
antes de borrar, y limpia también los restos del nombre anterior.

## Rutas cuando corre empaquetado

Este es el detalle que hay que entender antes de tocar el `.spec`:

```python
# core/config.py
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent   # carpeta del .exe
else:
    BASE_DIR = Path(__file__).resolve().parent.parent  # raíz del repo
```

PyInstaller extrae el bundle a una carpeta temporal, pero **`BASE_DIR` apunta a la
carpeta del `.exe` instalado**, no a esa temporal. Así `automations/`, `logs/`,
`core/rpa.db` y `.env` quedan junto al ejecutable, visibles y editables por el usuario.

`app/main.py` refuerza lo mismo al arrancar: mete la carpeta del `.exe` en `sys.path` y
fija ahí el directorio de trabajo, para que `import automations` encuentre la carpeta
editable de verdad y no una copia compilada dentro del bundle. Ese es el motivo de que
puedas editar una automatización desde la app instalada y que funcione.

## El `.spec`

`LaAutomate.spec` incluye a mano lo que PyInstaller no detecta solo:

- `collect_all` de **keyring** (backends que se cargan dinámicamente), **selenium** y
  **pynput** (el listener global de F5 de la grabadora).
- `hiddenimports` de `win32timezone`, `pywintypes` y `pythoncom`, que entran por COM.
- El icono `app/resources/app_icon.ico`, su PNG para la marca de la sidebar y los
  documentos que forman el contexto versionado del Asistente IA.

Si agregas una dependencia que se importe dinámicamente, va a fallar solo en el
`.exe` — no en desarrollo. Ahí es donde hay que agregarla.

## Renombrar la app

El nombre visible sale de `NOMBRE_APP` en `core/config.py` (título de ventana y marca
de la barra lateral). El nombre del ejecutable, la carpeta de instalación y el acceso
directo salen del `.spec` y de los `.bat` del instalador.

---

## Notas relacionadas

- [[desarrollo]] - el entorno desde el que se empaqueta
- [[vision-general]] - los primeros pasos tras instalar
