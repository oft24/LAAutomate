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
copy /y README.md dist\LaAutomate\ >nul
copy /y .env.example dist\LaAutomate\ >nul
xcopy automations dist\LaAutomate\automations\ /E /I /Q /Y >nul
copy /y instalador\INSTALL.bat dist\LaAutomate\ >nul
copy /y instalador\UNINSTALL.bat dist\LaAutomate\ >nul

echo [3/3] Listo. Para instalar:
echo    dist\LaAutomate\INSTALL.bat
