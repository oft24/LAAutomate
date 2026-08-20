@echo off
setlocal enabledelayedexpansion

echo ============================================
echo   Desinstalando LAAutomate - RPA de codigo
echo ============================================
echo.

set "ESCRITORIO="
for /f "tokens=2,*" %%A in ('reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders" /v Desktop 2^>nul') do set "ESCRITORIO=%%B"
if not defined ESCRITORIO set "ESCRITORIO=%USERPROFILE%\Desktop"

set "DESTINO=%LOCALAPPDATA%\LAAutomate"
if not exist "%DESTINO%" if exist "%USERPROFILE%\Desktop\LAAutomate" set "DESTINO=%USERPROFILE%\Desktop\LAAutomate"

if not exist "%DESTINO%" (
    echo No se encontro ninguna instalacion.
    pause
    exit /b 1
)

echo Se eliminara: %DESTINO%
set /p CONFIRMAR="Escribe SI para confirmar: "
if /i not "%CONFIRMAR%"=="SI" (
    echo Cancelado.
    pause
    exit /b 0
)

echo Cerrando procesos abiertos...
taskkill /IM LAAutomate.exe /F >nul 2>&1
ping -n 2 127.0.0.1 >nul

set /p CONSERVAR="Deseas conservar tus automatizaciones? (S/N): "
if /i "%CONSERVAR%"=="S" (
    if exist "%DESTINO%\automations" (
        echo Copiando tus automatizaciones al escritorio...
        xcopy "%DESTINO%\automations" "%ESCRITORIO%\LAAutomate_automations_respaldo\" /E /I /Q /Y >nul
        echo   %ESCRITORIO%\LAAutomate_automations_respaldo
    )
)

echo Eliminando LAAutomate...
rmdir /s /q "%DESTINO%"
if exist "%ESCRITORIO%\LAAutomate.lnk" del /q "%ESCRITORIO%\LAAutomate.lnk"

REM Restos del nombre anterior (Luisautomate), por si se desinstala en un
REM equipo donde nunca corrio el INSTALL.bat nuevo.
if exist "%ESCRITORIO%\Luisautomate.lnk" del /q "%ESCRITORIO%\Luisautomate.lnk"
if exist "%LOCALAPPDATA%\Luisautomate" rmdir /s /q "%LOCALAPPDATA%\Luisautomate"

echo.
echo ============================================
echo   Desinstalacion completada
echo ============================================
pause
