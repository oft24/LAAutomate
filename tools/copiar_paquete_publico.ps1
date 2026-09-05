param(
    [Parameter(Mandatory = $true)][string]$Destino
)

$ErrorActionPreference = 'Stop'
$raiz = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$destinoAbsoluto = [System.IO.Path]::GetFullPath($Destino)
$raizConSeparador = $raiz.TrimEnd('\') + '\'
$destinoConSeparador = $destinoAbsoluto.TrimEnd('\') + '\'

if (-not (Test-Path -LiteralPath (Join-Path $raiz '.git'))) {
    throw 'El paquete público debe generarse desde una copia Git para identificar archivos versionados.'
}

$rutas = @(& git -C $raiz ls-files -- README.md .env.example automations demos outputs/demo-compras/productos.xlsx docs/DEMO-COMPARATIVO-COMPRAS.md)
if ($LASTEXITCODE -ne 0 -or -not $rutas) {
    throw 'No se pudo obtener la lista de archivos públicos versionados.'
}

foreach ($relativa in $rutas) {
    $origen = [System.IO.Path]::GetFullPath((Join-Path $raiz $relativa))
    $salida = [System.IO.Path]::GetFullPath((Join-Path $destinoAbsoluto $relativa))
    if (-not $origen.StartsWith($raizConSeparador, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Ruta de origen fuera del proyecto: $origen"
    }
    if (-not $salida.StartsWith($destinoConSeparador, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Ruta de salida fuera del paquete: $salida"
    }
    if (-not (Test-Path -LiteralPath $origen -PathType Leaf)) {
        throw "Falta el archivo versionado: $relativa"
    }
    New-Item -ItemType Directory -Path (Split-Path -Parent $salida) -Force | Out-Null
    Copy-Item -LiteralPath $origen -Destination $salida -Force
}

Copy-Item -LiteralPath (Join-Path $raiz 'instalador\INSTALL.bat') -Destination (Join-Path $destinoAbsoluto 'INSTALL.bat') -Force
Copy-Item -LiteralPath (Join-Path $raiz 'instalador\UNINSTALL.bat') -Destination (Join-Path $destinoAbsoluto 'UNINSTALL.bat') -Force
Write-Output "Paquete público: $($rutas.Count) archivos versionados copiados; archivos locales excluidos."
