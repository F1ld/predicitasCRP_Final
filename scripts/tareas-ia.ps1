#requires -Version 7.0
[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateSet('Preparar', 'Entrenar', 'Probar')]
    [string]$Tarea,
    [Parameter(Mandatory)]
    [string]$Imagen,
    [ValidatePattern('^[a-z0-9][a-z0-9-]{0,39}$')]
    [string]$Ejecucion,
    [ValidatePattern('^[a-z0-9][a-z0-9-]{0,39}$')]
    [string]$DatasetDe,
    [ValidatePattern('^\d{4}-\d{2}-\d{2}$')]
    [string]$FechaCorte
)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$base = Join-Path $root 'runtime/fase-09/tareas-ia'
$imageId = docker image inspect --format '{{.Id}}' $Imagen
$dockerArgs = @('run', '--rm', '--pull', 'never', '--network', 'none', '--read-only',
                '--label', 'com.docker.compose.project=predicitas-tareas-ia',
                '--label', 'com.docker.compose.service=offline',
                '--cpus', '2', '--memory', '2g', '--tmpfs', '/tmp:rw,size=512m')
$cli = @('python', '-B', '-m', 'training.cli', '--contracts-dir', '/contracts')
$now = [DateTimeOffset]::UtcNow.ToString('o')

if ($Tarea -eq 'Probar') {
    $model = Join-Path $root 'artifacts/models/legacy-import'
    $dockerArgs += @('--mount', "type=bind,source=$model,target=/models,readonly")
    & docker @dockerArgs $imageId python -B -m pytest tests -q -p no:cacheprovider
    return
}

if (-not $Ejecucion) { throw 'Indica -Ejecucion con un nombre nuevo de salida.' }
if ($Tarea -eq 'Preparar') {
    if (-not $FechaCorte) { throw 'Preparar requiere -FechaCorte.' }
    $command = $cli + @('generar', '--version-dataset', $Ejecucion, '--semilla', '42',
        '--fecha-corte', $FechaCorte, '--generado-en', $now,
        '--fuente', 'SINTETICO_GENERADO', '--proximas', '80', '--directorio', '/salida')
} else {
    if (-not $DatasetDe) { throw 'Entrenar requiere -DatasetDe, el ID de una preparación previa.' }
    $dataset = Join-Path $base "$DatasetDe/$DatasetDe"
    if (-not (Test-Path -LiteralPath (Join-Path $dataset 'manifest.json') -PathType Leaf)) {
        throw 'No se encontró un dataset preparado con ese ID.'
    }
    $dockerArgs += @('--mount', "type=bind,source=$dataset,target=/dataset,readonly")
    $command = $cli + @('entrenar', '--dataset', '/dataset', '--version-modelo', $Ejecucion,
        '--fecha', $now, '--directorio', '/salida')
}

$output = Join-Path $base $Ejecucion
New-Item -ItemType Directory -Path $output -ErrorAction Stop | Out-Null
$dockerArgs += @('--mount', "type=bind,source=$output,target=/salida")
& docker @dockerArgs $imageId @command
if ($Tarea -eq 'Preparar') {
    & docker @dockerArgs $imageId @cli validar --dataset "/salida/$Ejecucion"
}
