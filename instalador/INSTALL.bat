@echo off
setlocal DisableDelayedExpansion

REM Desde el repositorio solo actualiza el acceso a la version actual.
REM Salir ANTES de la reinstalacion evita borrar una instalacion existente.
if exist "%~dp0..\app\main.py" if exist "%~dp0..\tools\crear_acceso_directo.ps1" goto acceso_proyecto
if not exist "%~dp0LaAutomate.exe" (
    echo ERROR: no se encontro LaAutomate.exe ni una copia del proyecto.
    echo No se modifico la instalacion existente.
    pause
    exit /b 1
)
setlocal enabledelayedexpansion

echo ============================================
echo   Instalando LaAutomate - RPA de codigo
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
set "DESTINO=%LOCALAPPDATA%\LaAutomate"

echo Origen:     %ORIGEN%
echo Destino:    %DESTINO%
echo Escritorio: %ESCRITORIO%
echo.

REM Migracion desde ubicaciones viejas: se conservan las automatizaciones
REM y el .env de donde haya quedado la instalacion anterior.
set "PREVIA="
if exist "%DESTINO%\automations" set "PREVIA=%DESTINO%"
if not defined PREVIA if exist "%USERPROFILE%\Desktop\LaAutomate\automations" set "PREVIA=%USERPROFILE%\Desktop\LaAutomate"
if not defined PREVIA if exist "%ESCRITORIO%\LaAutomate\automations" set "PREVIA=%ESCRITORIO%\LaAutomate"

REM Migracion desde el nombre anterior (Luisautomate -> LaAutomate): la
REM instalacion vieja vive en otra carpeta y con otro acceso directo, asi
REM que hay que traer sus automatizaciones y limpiarla -- si no, quedan
REM dos apps distintas en el equipo y el usuario no sabe cual abrir.
set "VIEJA="
if exist "%LOCALAPPDATA%\Luisautomate" set "VIEJA=%LOCALAPPDATA%\Luisautomate"
if not defined VIEJA if exist "%ESCRITORIO%\Luisautomate\Luisautomate.exe" set "VIEJA=%ESCRITORIO%\Luisautomate"
if not defined PREVIA if defined VIEJA if exist "%VIEJA%\automations" set "PREVIA=%VIEJA%"

echo Cerrando procesos abiertos...
taskkill /IM LaAutomate.exe /F >nul 2>&1
taskkill /IM Luisautomate.exe /F >nul 2>&1
ping -n 2 127.0.0.1 >nul

REM El respaldo va a una carpeta FECHADA que NO se consume al restaurar.
REM Antes se guardaba en %TEMP% y se MOVIA de vuelta: si el restore fallaba
REM a medias, o algo vaciaba %TEMP% entre medias, no quedaba copia de nada
REM y las automatizaciones del usuario se perdian sin rastro.
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value 2^>nul') do set "AHORA=%%I"
if not defined AHORA set "AHORA=manual"
set "RESPALDO=%LOCALAPPDATA%\LaAutomate_respaldos\%AHORA:~0,8%_%AHORA:~8,6%"

if defined PREVIA (
    echo Respaldando automatizaciones de: !PREVIA!
    xcopy "!PREVIA!\automations" "%RESPALDO%\automations\" /E /I /Q /Y >nul
    if exist "!PREVIA!\.env" copy "!PREVIA!\.env" "%RESPALDO%\.env" >nul
    REM El historial, los logs y lo aprendido tambien viven dentro de la
    REM carpeta que se borra. Sin esto, cada reinstalacion dejaba el
    REM historial en blanco sin dar ningun error.
    if exist "!PREVIA!\core\rpa.db" (
        mkdir "%RESPALDO%\core" 2>nul
        copy "!PREVIA!\core\rpa.db" "%RESPALDO%\core\rpa.db" >nul
        echo   Historial de ejecuciones respaldado.
    )
    if exist "!PREVIA!\logs" xcopy "!PREVIA!\logs" "%RESPALDO%\logs\" /E /I /Q /Y >nul
    REM datos\ son los Excel de entrada y salida de las automatizaciones.
    REM Es lo mas irreemplazable de la instalacion: el codigo se vuelve a
    REM empaquetar, una lista de personas escrita a mano no.
    if exist "!PREVIA!\datos" (
        xcopy "!PREVIA!\datos" "%RESPALDO%\datos\" /E /I /Q /Y >nul
        echo   Carpeta datos respaldada.
    )
    REM La memoria del autocorrector vive junto al .exe, fuera de
    REM _internal\, justo para que no se la lleve este borrado. El
    REM PRACTICAS.md de _internal\ es el que trae la version: ese NO se
    REM respalda, tiene que ganar el del paquete nuevo.
    if exist "!PREVIA!\practicas_aprendidas.md" (
        copy "!PREVIA!\practicas_aprendidas.md" "%RESPALDO%\practicas_aprendidas.md" >nul
        echo   Practicas aprendidas respaldadas.
    )
    REM Instalaciones anteriores las guardaban dentro de _internal\. Se
    REM conservan para que la app las mude sola, pero con OTRO nombre: el
    REM PRACTICAS.md del paquete no se pisa nunca, o se perderian las
    REM practicas nuevas que traiga la version.
    if not exist "!PREVIA!\practicas_aprendidas.md" (
        if exist "!PREVIA!\_internal\docs\PRACTICAS.md" (
            copy "!PREVIA!\_internal\docs\PRACTICAS.md" "%RESPALDO%\practicas_por_migrar.md" >nul
            echo   Practicas del formato anterior conservadas para migrarlas.
        )
    )
    set "ANTES=0"
    for /d %%D in ("!PREVIA!\automations\*") do set /a ANTES+=1
    echo   !ANTES! carpeta^(s^) respaldadas en: %RESPALDO%
)

if exist "%DESTINO%" rmdir /s /q "%DESTINO%"

echo Copiando archivos nuevos...
mkdir "%DESTINO%"
xcopy "%ORIGEN%\*" "%DESTINO%\" /E /I /Q /Y >nul

if exist "%RESPALDO%\automations" (
    echo Restaurando tus automatizaciones...
    REM xcopy, no move: el respaldo se queda donde esta. Si algo sale mal
    REM aqui, la copia sigue existiendo y se puede recuperar a mano.
    REM Las nuevas que trae el paquete no se borran; las tuyas las pisan
    REM porque son las que tienen tus cambios.
    xcopy "%RESPALDO%\automations" "%DESTINO%\automations\" /E /I /Q /Y >nul
    set "DESPUES=0"
    for /d %%D in ("%DESTINO%\automations\*") do set /a DESPUES+=1
    echo   !DESPUES! carpeta^(s^) de automatizaciones en la instalacion.
    if !DESPUES! LSS !ANTES! (
        echo.
        echo   *** AVISO: habia !ANTES! y quedaron !DESPUES!.
        echo   *** Tu respaldo intacto esta en: %RESPALDO%\automations
        echo.
    )
)

if exist "%RESPALDO%\.env" (
    echo Restaurando tu configuracion .env...
    copy "%RESPALDO%\.env" "%DESTINO%\.env" >nul
)

if exist "%RESPALDO%\core\rpa.db" (
    echo Restaurando el historial de ejecuciones...
    mkdir "%DESTINO%\core" 2>nul
    copy "%RESPALDO%\core\rpa.db" "%DESTINO%\core\rpa.db" >nul
)

if exist "%RESPALDO%\logs" (
    echo Restaurando los logs...
    xcopy "%RESPALDO%\logs" "%DESTINO%\logs\" /E /I /Q /Y >nul
)

if exist "%RESPALDO%\datos" (
    echo Restaurando tus datos...
    xcopy "%RESPALDO%\datos" "%DESTINO%\datos\" /E /I /Q /Y >nul
)

REM Las practicas del paquete son la base; las aprendidas aqui son las que
REM importan. Se restauran encima, no al reves.
if exist "%RESPALDO%\practicas_aprendidas.md" (
    echo Restaurando las practicas aprendidas...
    copy "%RESPALDO%\practicas_aprendidas.md" "%DESTINO%\practicas_aprendidas.md" >nul
)

REM Formato viejo: se deja aparte y la app lo muda al arrancar. El
REM PRACTICAS.md del paquete queda intacto.
if not exist "%DESTINO%\practicas_aprendidas.md" (
    if exist "%RESPALDO%\practicas_por_migrar.md" (
        echo Dejando las practicas del formato anterior para migrarlas...
        copy "%RESPALDO%\practicas_por_migrar.md" "%DESTINO%\practicas_por_migrar.md" >nul
    )
)

echo Creando acceso directo en el escritorio...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference = 'Stop';" ^
  "$desktop = [Environment]::GetFolderPath('Desktop');" ^
  "if (-not $desktop -or -not (Test-Path -LiteralPath $desktop -PathType Container)) { throw 'No se pudo localizar el escritorio real' };" ^
  "$target = Join-Path $env:DESTINO 'LaAutomate.exe';" ^
  "if (-not (Test-Path -LiteralPath $target -PathType Leaf)) { throw 'No se copio LaAutomate.exe' };" ^
  "$icon = $target + ',0';" ^
  "$ico = Join-Path $env:DESTINO '_internal\app\resources\app_icon.ico';" ^
  "if (Test-Path -LiteralPath $ico -PathType Leaf) { $icon = $ico + ',0' };" ^
  "$link = Join-Path $desktop 'LaAutomate.lnk';" ^
  "$w = New-Object -ComObject WScript.Shell;" ^
  "$s = $w.CreateShortcut($link);" ^
  "$s.TargetPath = $target;" ^
  "$s.Arguments = '';" ^
  "$s.WorkingDirectory = $env:DESTINO;" ^
  "$s.IconLocation = $icon;" ^
  "$s.Description = 'LaAutomate - RPA de codigo';" ^
  "$s.WindowStyle = 1; $s.Save();" ^
  "$v = $w.CreateShortcut($link);" ^
  "if ($v.TargetPath -ne $target -or $v.WorkingDirectory -ne $env:DESTINO -or $v.Arguments -ne '' -or $v.IconLocation -ne $icon) { throw 'El acceso directo no conservo su configuracion' };" ^
  "Write-Output ('Acceso verificado: ' + $link)"
if errorlevel 1 (
    echo ERROR: no se pudo crear o verificar el acceso directo.
    echo Los archivos instalados y respaldos se conservaron.
    pause
    exit /b 1
)

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

if exist "%USERPROFILE%\Desktop\LaAutomate\LaAutomate.exe" (
    echo.
    echo NOTA: quedo una instalacion anterior en:
    echo   %USERPROFILE%\Desktop\LaAutomate
    echo Ya se copiaron sus automatizaciones. Puedes borrar esa carpeta.
)

echo.
echo ============================================
echo   Instalacion completada
echo ============================================
echo.
echo LaAutomate quedo instalado en:
echo   %DESTINO%
echo.
echo Y su acceso directo en el escritorio:
echo   %ESCRITORIO%\LaAutomate.lnk
if defined PREVIA (
    echo.
    echo Respaldo de tus automatizaciones anteriores ^(no se borra solo^):
    echo   %RESPALDO%
)
echo.
pause
exit /b 0

:acceso_proyecto
echo Creando acceso a la version actual del proyecto...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\tools\crear_acceso_directo.ps1"
if errorlevel 1 (
    echo.
    echo ERROR: no se pudo crear el acceso. Revisa el mensaje anterior.
    echo El proyecto requiere .venv\Scripts\pythonw.exe y su icono.
    pause
    exit /b 1
)
echo.
echo Listo. Abre LaAutomate desde el acceso directo del escritorio.
echo No muevas ni borres esta copia del proyecto: el acceso depende de ella.
pause
exit /b 0
