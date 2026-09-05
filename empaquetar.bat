@echo off
REM Reconstruye el .exe y deja dist\LaAutomate listo para instalar.
REM PyInstaller BORRA dist\LaAutomate en cada build, por eso los .bat
REM viven en instalador\ (versionados) y se copian aqui al final -- antes
REM habia que recrearlos a mano en cada rebuild y era facil olvidarlos.
setlocal
cd /d "%~dp0"

echo [1/3] Compilando con PyInstaller...
".venv\Scripts\python.exe" -m PyInstaller LaAutomate.spec --noconfirm || exit /b 1

echo [2/3] Copiando archivos auxiliares...
REM Solo entran archivos versionados. Esto evita publicar por accidente
REM automatizaciones creadas localmente, reportes, capturas o datos privados.
powershell -NoProfile -ExecutionPolicy Bypass -File tools\copiar_paquete_publico.ps1 -Destino dist\LaAutomate || exit /b 1

echo [3/3] Listo. Para instalar:
echo    dist\LaAutomate\INSTALL.bat
