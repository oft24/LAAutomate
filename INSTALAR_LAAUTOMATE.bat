@echo off
setlocal
cd /d "%~dp0"

echo ==================================================
echo   LaAutomate - instalacion desde el codigo fuente
echo ==================================================
echo.

set "PYTHON_LAAUTOMATE="
where py >nul 2>&1 && py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1 && set "PYTHON_LAAUTOMATE=py -3"
if not defined PYTHON_LAAUTOMATE where python >nul 2>&1 && python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1 && set "PYTHON_LAAUTOMATE=python"
if not defined PYTHON_LAAUTOMATE goto falta_python

if not exist ".venv\Scripts\python.exe" (
    echo [1/4] Creando el entorno privado de LaAutomate...
    %PYTHON_LAAUTOMATE% -m venv .venv
    if errorlevel 1 goto error_instalacion
) else (
    echo [1/4] El entorno privado ya existe.
)

echo [2/4] Instalando dependencias. La primera vez puede tardar varios minutos...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto error_instalacion

echo [3/4] Preparando la configuracion local...
if not exist ".env" copy /y ".env.example" ".env" >nul

echo [4/4] Creando el acceso directo del escritorio...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\crear_acceso_directo.ps1"
if errorlevel 1 goto error_instalacion

echo.
echo ==================================================
echo   Instalacion completada
echo ==================================================
echo Abre LaAutomate desde el acceso directo del escritorio.
echo Esta copia depende de la carpeta actual: no la muevas ni la borres.
echo Gemini es opcional y se configura dentro de Asistente IA.
echo.
pause
exit /b 0

:falta_python
echo ERROR: Python no esta instalado o no aparece en PATH.
echo Descarga Python 3.11 o posterior desde https://www.python.org/downloads/windows/
echo Durante la instalacion activa "Add python.exe to PATH".
goto fin_error

:error_instalacion
echo.
echo ERROR: la instalacion no termino. No se elimino ningun archivo personal.
echo Revisa el mensaje anterior y vuelve a ejecutar este archivo.

:fin_error
echo.
pause
exit /b 1
