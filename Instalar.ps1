$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$trussPython = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\python.exe'
if (-not (Test-Path -LiteralPath $trussPython)) {
    $trussCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $trussCommand) { throw 'Instala Python 3.11 o 3.12 de 64 bits antes de continuar.' }
    $trussPython = $trussCommand.Source
}
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    & $trussPython -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'No fue posible crear el entorno.' }
}
& '.\.venv\Scripts\python.exe' -m pip install -r requirements-lock.txt
if ($LASTEXITCODE -ne 0) { throw 'No fue posible instalar las dependencias.' }
Write-Host 'Listo. Abre TrussLab3D.exe o Abrir_TrussLab.cmd.'
