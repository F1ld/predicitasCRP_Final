param(
    [Parameter(Mandatory = $true)][string]$PrivateDirectory,
    [Parameter(Mandatory = $true)][string]$RunId
)
$ErrorActionPreference = 'Stop'
if ($RunId -notmatch '^predicitas-fase0-[a-z0-9-]+$') { throw 'RunId invalido.' }
$private = (Resolve-Path -LiteralPath $PrivateDirectory).Path
$root = (Get-Location).Path
if ($private.StartsWith($root, [StringComparison]::OrdinalIgnoreCase)) { throw 'El respaldo privado debe estar fuera del proyecto.' }
$sources = @(
    @{ Volume = 'predicitas-crp_pgdata'; Alias = 'crp' },
    @{ Volume = 'predicitas-backend_pgdata'; Alias = 'backend' },
    @{ Volume = 'predicitas-guia-qa_qa_pgdata'; Alias = 'qa' }
)
$evidence = @()
foreach ($source in $sources) {
    $volume = $source.Volume
    $alias = $source.Alias
    $running = @(& docker ps -q --filter "volume=$volume")
    if ($LASTEXITCODE -ne 0) { throw "No se pudo verificar escritores: $volume" }
    if ($running.Count -gt 0) { throw "Hay contenedores activos usando $volume. No se copia en caliente." }
    $filename = "$volume.tar"
    if (Test-Path -LiteralPath (Join-Path $private $filename)) { throw "Ya existe respaldo: $filename" }
    & docker run --rm --network none --mount "type=volume,source=$volume,target=/source,readonly" --mount "type=bind,source=$private,target=/backup" --entrypoint tar postgres:16 -cpf "/backup/$filename" -C /source .
    if ($LASTEXITCODE -ne 0) { throw "Fallo copia RO de $volume" }
    $running = @(& docker ps -q --filter "volume=$volume")
    if ($LASTEXITCODE -ne 0 -or $running.Count -gt 0) { throw "Revisar consistencia de ${volume}: aparecieron escritores." }
    $clone = "$RunId-$alias"
    $existing = @(& docker volume ls --format '{{.Name}}')
    if ($LASTEXITCODE -ne 0 -or $clone -in $existing) { throw "No se sobreescribe volumen: $clone" }
    & docker volume create --label 'predicitas.purpose=fase0-isolated-copy' $clone | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Fallo al crear $clone" }
    & docker run --rm --network none --mount "type=volume,source=$clone,target=/clone" --mount "type=bind,source=$private,target=/backup,readonly" --entrypoint tar postgres:16 -xpf "/backup/$filename" -C /clone
    if ($LASTEXITCODE -ne 0) { throw "Fallo al restaurar copia fisica: $clone" }
    $file = Get-Item -LiteralPath (Join-Path $private $filename)
    $evidence += [PSCustomObject]@{ Source = $volume; ReadOnlySource = $true; NoActiveWriters = $true; Archive = $filename; Bytes = $file.Length; Sha256 = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash; Clone = $clone; Alias = $alias }
}
$destination = Join-Path $root 'docs\migracion\fase-00\volumenes_respaldados.json'
if (Test-Path -LiteralPath $destination) { throw 'Ya existe evidencia; no se sobreescribe.' }
$evidence | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $destination -Encoding UTF8
$evidence | Format-Table Source, Clone, Bytes, ReadOnlySource
