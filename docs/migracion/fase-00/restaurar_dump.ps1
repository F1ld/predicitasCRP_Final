param([Parameter(Mandatory = $true)][string]$PrivateDirectory)
$ErrorActionPreference = 'Stop'
$name = 'predicitas-fase0-20261103-2200-restore'
$volume = "$name-pgdata"
$network = 'predicitas-fase0-20261103-2200-net'
$private = (Resolve-Path -LiteralPath $PrivateDirectory).Path
if ($volume -in @(& docker volume ls --format '{{.Name}}')) { throw 'El volumen de restauracion ya existe; no se sobreescribe.' }
foreach ($filename in @('crp.dump', 'crp_globals_privado.sql')) {
    if (-not (Test-Path -LiteralPath (Join-Path $private $filename) -PathType Leaf)) { throw "Falta $filename" }
}
$envfile = Join-Path $private 'restore-container.env'
if (Test-Path -LiteralPath $envfile) { throw 'Ya existe configuracion de restore.' }
$password = [guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N')
@('POSTGRES_USER=fase0_restore_admin', "POSTGRES_PASSWORD=$password", 'POSTGRES_DB=postgres') | Set-Content -LiteralPath $envfile -Encoding ASCII
& docker volume create --label 'predicitas.purpose=fase0-dump-restore' $volume | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear volumen restore.' }
& docker run -d --name $name --label 'predicitas.purpose=fase0-dump-restore' --network $network --mount "type=volume,source=$volume,target=/var/lib/postgresql/data" --mount "type=bind,source=$private,target=/backup,readonly" --env-file $envfile --health-cmd 'pg_isready -U fase0_restore_admin -d postgres' --health-interval 5s --health-timeout 3s --health-retries 5 postgres:16 | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'No se pudo iniciar restore.' }
'Instancia restore iniciada, sin puertos publicados. Ejecutar la carga solo despues de comprobar readiness.'
