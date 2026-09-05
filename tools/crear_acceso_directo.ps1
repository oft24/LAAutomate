# Crea/actualiza el acceso a la copia de desarrollo, sin reinstalar ni empaquetar.
$ErrorActionPreference = 'Stop'
$raizLaAutomate = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$pythonLaAutomate = Join-Path $raizLaAutomate '.venv\Scripts\pythonw.exe'
$iconoLaAutomate = Join-Path $raizLaAutomate 'app\resources\app_icon.ico'
foreach ($archivoLaAutomate in @($pythonLaAutomate, $iconoLaAutomate, (Join-Path $raizLaAutomate 'app\main.py'))) {
    if (-not (Test-Path -LiteralPath $archivoLaAutomate -PathType Leaf)) {
        throw "Falta un archivo necesario: $archivoLaAutomate"
    }
}
$escritorioLaAutomate = [Environment]::GetFolderPath('Desktop')
if (-not $escritorioLaAutomate -or -not (Test-Path -LiteralPath $escritorioLaAutomate -PathType Container)) {
    throw 'No se pudo acceder al escritorio de la sesión de Windows.'
}
$rutaAccesoLaAutomate = Join-Path $escritorioLaAutomate 'LaAutomate.lnk'
if (Test-Path -LiteralPath $rutaAccesoLaAutomate) {
    $carpetaRespaldoLaAutomate = Join-Path $raizLaAutomate 'build\accesos-respaldo'
    New-Item -ItemType Directory -Path $carpetaRespaldoLaAutomate -Force | Out-Null
    $respaldoLaAutomate = Join-Path $carpetaRespaldoLaAutomate ('LaAutomate-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff') + '.lnk')
    Copy-Item -LiteralPath $rutaAccesoLaAutomate -Destination $respaldoLaAutomate
    Write-Output "Acceso anterior respaldado: $respaldoLaAutomate"
}
$shellLaAutomate = New-Object -ComObject WScript.Shell
$accesoLaAutomate = $shellLaAutomate.CreateShortcut($rutaAccesoLaAutomate)
$accesoLaAutomate.TargetPath = $pythonLaAutomate
$accesoLaAutomate.Arguments = '-m app.main'
$accesoLaAutomate.WorkingDirectory = $raizLaAutomate
$accesoLaAutomate.IconLocation = $iconoLaAutomate + ',0'
$accesoLaAutomate.Description = 'LaAutomate — automatización de escritorio (versión del proyecto)'
$accesoLaAutomate.WindowStyle = 1
$accesoLaAutomate.Save()
$verificadoLaAutomate = $shellLaAutomate.CreateShortcut($rutaAccesoLaAutomate)
if ($verificadoLaAutomate.TargetPath -ne $pythonLaAutomate -or $verificadoLaAutomate.WorkingDirectory -ne $raizLaAutomate -or $verificadoLaAutomate.Arguments -ne '-m app.main' -or $verificadoLaAutomate.IconLocation -ne ($iconoLaAutomate + ',0')) {
    throw 'El acceso directo no conservó su configuración; revisa sus propiedades.'
}
Write-Output "Acceso verificado: $rutaAccesoLaAutomate"
Write-Output "Icono: $iconoLaAutomate"
