@echo off
setlocal enabledelayedexpansion

echo ============================================
echo   Instalando LAAutomate - RPA de codigo
echo ============================================
echo.

set "ORIGEN=%~dp0"
set "ORIGEN=%ORIGEN:~0,-1%"

REM El escritorio REAL se lee del registro, no se adivina: con OneDrive
REM corporativo la carpeta puede llamarse "OneDrive - <Empresa>\Desktop",
REM y adivinar "%USERPROFILE%\OneDrive\Desktop" fallaba en silencio --
REM la app terminaba en una carpeta que el usuario nunca ve en pantalla.
set "ESCRITORIO="
for /f "tokens=2,*" %%A in ('reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders" /v Desktop 2^>nul') do set "ESCRITORIO=%%B"
if not defined ESCRITORIO set "ESCRITORIO=%USERPROFILE%\Desktop"

REM La app se instala en una carpeta LOCAL (no sincronizada): son ~200 MB
REM de binarios y meterlos en OneDrive lo sincronizaria eternamente y
REM puede bloquear archivos en pleno uso. En el escritorio visible queda
REM un acceso directo, que es lo que el usuario abre.
set "DESTINO=%LOCALAPPDATA%\LAAutomate"

echo Origen:     %ORIGEN%
echo Destino:    %DESTINO%
echo Escritorio: %ESCRITORIO%
echo.

REM Migracion desde ubicaciones viejas: se conservan las automatizaciones
REM y el .env de donde haya quedado la instalacion anterior.
set "PREVIA="
if exist "%DESTINO%\automations" set "PREVIA=%DESTINO%"
if not defined PREVIA if exist "%USERPROFILE%\Desktop\LAAutomate\automations" set "PREVIA=%USERPROFILE%\Desktop\LAAutomate"
if not defined PREVIA if exist "%ESCRITORIO%\LAAutomate\automations" set "PREVIA=%ESCRITORIO%\LAAutomate"

REM Migracion desde el nombre anterior (Luisautomate -> LAAutomate): la
REM instalacion vieja vive en otra carpeta y con otro acceso directo, asi
REM que hay que traer sus automatizaciones y limpiarla -- si no, quedan
REM dos apps distintas en el equipo y el usuario no sabe cual abrir.
set "VIEJA="
if exist "%LOCALAPPDATA%\Luisautomate" set "VIEJA=%LOCALAPPDATA%\Luisautomate"
if not defined VIEJA if exist "%ESCRITORIO%\Luisautomate\Luisautomate.exe" set "VIEJA=%ESCRITORIO%\Luisautomate"
if not defined PREVIA if defined VIEJA if exist "%VIEJA%\automations" set "PREVIA=%VIEJA%"

echo Cerrando procesos abiertos...
taskkill /IM LAAutomate.exe /F >nul 2>&1
taskkill /IM Luisautomate.exe /F >nul 2>&1
ping -n 2 127.0.0.1 >nul

if defined PREVIA (
    echo Conservando automatizaciones de: !PREVIA!
    if exist "%TEMP%\LAAutomate_automations_backup" rmdir /s /q "%TEMP%\LAAutomate_automations_backup" >nul 2>&1
    xcopy "!PREVIA!\automations" "%TEMP%\LAAutomate_automations_backup\" /E /I /Q /Y >nul
    if exist "!PREVIA!\.env" copy "!PREVIA!\.env" "%TEMP%\LAAutomate_env_backup" >nul
)

if exist "%DESTINO%" rmdir /s /q "%DESTINO%"

echo Copiando archivos nuevos...
mkdir "%DESTINO%"
xcopy "%ORIGEN%\*" "%DESTINO%\" /E /I /Q /Y >nul

if exist "%TEMP%\LAAutomate_automations_backup" (
    echo Restaurando tus automatizaciones...
    if exist "%DESTINO%\automations" rmdir /s /q "%DESTINO%\automations"
    move "%TEMP%\LAAutomate_automations_backup" "%DESTINO%\automations" >nul
)

if exist "%TEMP%\LAAutomate_env_backup" (
    echo Restaurando tu configuracion .env...
    move "%TEMP%\LAAutomate_env_backup" "%DESTINO%\.env" >nul
)

echo Creando acceso directo en el escritorio...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$w = New-Object -ComObject WScript.Shell;" ^
  "$s = $w.CreateShortcut('%ESCRITORIO%\LAAutomate.lnk');" ^
  "$s.TargetPath = '%DESTINO%\LAAutomate.exe';" ^
  "$s.WorkingDirectory = '%DESTINO%';" ^
  "$s.IconLocation = '%DESTINO%\LAAutomate.exe,0';" ^
  "$s.Description = 'LAAutomate - RPA de codigo';" ^
  "$s.Save()" >nul 2>&1

REM La instalacion vieja se borra SOLO si sus automatizaciones ya se
REM migraron (o si no tenia ninguna). Si tenia automatizaciones propias y
REM no se migraron -- porque ya existia una instalacion nueva con las
REM suyas -- no se toca nada y se avisa: perderlas en silencio seria peor
REM que dejar una carpeta de mas.
if defined VIEJA if exist "%VIEJA%" (
    if /i "!PREVIA!"=="%VIEJA%" (
        echo Eliminando la instalacion anterior ^(Luisautomate^)...
        rmdir /s /q "%VIEJA%"
    ) else if not exist "%VIEJA%\automations" (
        echo Eliminando la instalacion anterior ^(Luisautomate^)...
        rmdir /s /q "%VIEJA%"
    ) else (
        echo NOTA: quedo una instalacion anterior con automatizaciones propias en:
        echo   %VIEJA%
        echo Revisala y borrala a mano cuando ya no la necesites.
    )
)
if exist "%ESCRITORIO%\Luisautomate.lnk" del /q "%ESCRITORIO%\Luisautomate.lnk"

if exist "%USERPROFILE%\Desktop\LAAutomate\LAAutomate.exe" (
    echo.
    echo NOTA: quedo una instalacion anterior en:
    echo   %USERPROFILE%\Desktop\LAAutomate
    echo Ya se copiaron sus automatizaciones. Puedes borrar esa carpeta.
)

echo.
echo ============================================
echo   Instalacion completada
echo ============================================
echo.
echo LAAutomate quedo instalado en:
echo   %DESTINO%
echo.
echo Y su acceso directo en el escritorio:
echo   %ESCRITORIO%\LAAutomate.lnk
echo.
pause
