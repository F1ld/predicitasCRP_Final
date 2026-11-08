#requires -Version 7.0
[CmdletBinding()]
param(
    [ValidateSet('Verify', 'Existing', 'FreshDemo')]
    [string]$Mode = 'Verify',
    [string]$EnvFile,
    [string]$ComposeOverride,
    [string]$ConfirmVolume,
    [ValidatePattern('^(predicitas-crp|predicitas-f9-[a-z0-9-]+)$')]
    [string]$Project = 'predicitas-crp'
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$defaultEnv = Join-Path $root '.env'
if (-not $EnvFile) {
    if ($Mode -eq 'FreshDemo') { throw 'FreshDemo requiere -EnvFile de laboratorio.' }
    $EnvFile = $defaultEnv
}

function Resolve-File([string]$Path, [string]$Label) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Falta $Label. Consulta .env.example y la guía de arranque de la fase 9."
    }
    (Resolve-Path -LiteralPath $Path).Path
}

function Invoke-Docker([string[]]$Arguments, [string]$Failure) {
    # Compose puede expandir secretos. Solo se publica información seleccionada.
    $PSNativeCommandUseErrorActionPreference = $false
    $output = & docker @Arguments 2>$null
    if ($LASTEXITCODE -ne 0) { throw $Failure }
    $output
}

if (-not (Get-Command docker -CommandType Application -ErrorAction SilentlyContinue)) {
    throw 'Docker no está disponible en PATH.'
}
$envPath = Resolve-File $EnvFile 'el archivo de entorno'
if ($Mode -eq 'FreshDemo' -and $envPath -ieq $defaultEnv) {
    throw 'FreshDemo requiere un archivo de entorno separado del operativo.'
}
$compose = @('compose', '--project-directory', $root, '--env-file', $envPath, '-p', $Project,
             '-f', (Join-Path $root 'compose.yaml'))
if ($ComposeOverride) {
    $compose += @('-f', (Resolve-File $ComposeOverride 'la capa Compose local'))
}
if ($Mode -eq 'FreshDemo') { $compose += @('--profile', 'seed-manual') }
Invoke-Docker @('info', '--format', '{{.OSType}}') 'Docker no está disponible. Abre Docker Desktop.' |
    ForEach-Object { if ($_ -ne 'linux') { throw 'Selecciona contenedores Linux en Docker Desktop.' } }
$config = (Invoke-Docker ($compose + @('config', '--format', 'json')) `
    'Compose no pudo resolver la configuración. Revisa el archivo de entorno, IA_API_KEY y la versión de Compose.') |
    ConvertFrom-Json -Depth 100
if ($config.name -ne $Project -or -not $config.volumes.pgdata.external) {
    throw 'Se esperaba el proyecto indicado con un volumen PostgreSQL externo.'
}
$volume = $config.volumes.pgdata.name
if ([string]::IsNullOrWhiteSpace($volume)) { throw 'Falta el nombre del volumen PostgreSQL.' }
if ($Mode -ne 'FreshDemo') {
    Invoke-Docker @('volume', 'inspect', '--format', '{{.Name}}', $volume) `
        "No existe el volumen configurado '$volume'. El bootstrap no crea volúmenes en este modo." | Out-Null
}

$key = $config.services.backend.environment.IA_API_KEY
if ([string]::IsNullOrWhiteSpace($key) -or $key -cne $config.services.ia.environment.IA_API_KEY) {
    throw 'Backend e IA deben compartir una clave interna válida.'
}
if ($config.services.ia.ports -or -not $config.networks.inferencia.internal) {
    throw 'IA debe usar una red interna y no publicar puertos.'
}
$modelMount = @($config.services.ia.volumes | Where-Object target -eq '/models')
if ($modelMount.Count -ne 1 -or $modelMount[0].type -ne 'bind' -or -not $modelMount[0].read_only) {
    throw 'Se esperaba un único montaje de modelo de solo lectura.'
}
$model = Join-Path $modelMount[0].source 'modelo_predicitas_v1.joblib'
if (-not (Test-Path -LiteralPath $model -PathType Leaf)) { throw 'Falta el artefacto esperado en IA_MODEL_DIR.' }

if ($Mode -eq 'FreshDemo') {
    if ($Project -notmatch '^predicitas-f9-demo-[a-z0-9-]+$') {
        throw 'FreshDemo exige un proyecto nuevo con prefijo predicitas-f9-demo-.'
    }
}
if ($Mode -ne 'Verify') {
    if ($ConfirmVolume -cne $volume) {
        throw "$Mode requiere -ConfirmVolume '$volume'."
    }
    if ($Project -ne 'predicitas-crp' -and
        ($volume -cne "${Project}_pgdata" -or -not $config.networks.default.internal -or
        ($config.services.PSObject.Properties.Value | Where-Object { $_.ports -or $_.container_name }))) {
        throw 'El proyecto de laboratorio requiere volumen propio, redes internas y servicios sin puertos ni nombres fijos.'
    }
    $dbMount = @($config.services.db.volumes | Where-Object target -eq '/var/lib/postgresql/data')
    $databaseUrl = [uri]$config.services.backend.environment.DATABASE_URL
    $database = $config.services.db.environment.POSTGRES_DB
    if ($dbMount.Count -ne 1 -or $dbMount[0].type -ne 'volume' -or $dbMount[0].source -ne 'pgdata' -or
        $databaseUrl.Host -ne 'db' -or $databaseUrl.AbsolutePath -cne "/$database") {
        throw 'PostgreSQL y backend deben apuntar al volumen y la base configurados.'
    }
}

if ($Mode -eq 'Existing') {
    $dbId = Invoke-Docker ($compose + @('ps', '-a', '-q', 'db')) 'No se pudo identificar PostgreSQL.'
    if ($dbId) {
        $dbId = Invoke-Docker @('inspect', '-f', '{{.Id}}', $dbId) 'No se pudo inspeccionar PostgreSQL.'
        $mounted = Invoke-Docker @('inspect', '-f',
            '{{range .Mounts}}{{if eq .Destination "/var/lib/postgresql/data"}}{{.Name}}{{end}}{{end}}', $dbId) `
            'No se pudo inspeccionar el volumen montado.'
        if ($mounted -cne $volume) { throw 'El contenedor existente monta otro volumen PostgreSQL.' }
    }
    $consumers = @(Invoke-Docker @('ps', '--no-trunc', '-q', '--filter', "volume=$volume") `
        'No se pudieron consultar los consumidores del volumen.')
    if ($consumers | Where-Object { $_ -ne $dbId }) { throw 'El volumen tiene otro consumidor activo.' }

    Invoke-Docker @('run', '--rm', '--pull', 'never', '--network', 'none', '--entrypoint', 'sh',
        '--mount', "type=volume,source=$volume,target=/pgdata,readonly,volume-nocopy", $config.services.db.image,
        '-ec', 'test -s /pgdata/PG_VERSION && test -s /pgdata/global/pg_control && test "$(cat /pgdata/PG_VERSION)" = "$PG_MAJOR"') `
        'El volumen no contiene un clúster inicializado compatible o falta la imagen local de PostgreSQL.' | Out-Null

    $backendImage = $config.services.backend.image
    if (-not $backendImage) { $backendImage = "$Project-backend" }
    $backendImageId = Invoke-Docker @('image', 'inspect', '-f', '{{.Id}}', $backendImage) `
        'Falta la imagen local del backend. Construye o carga la imagen aprobada primero.'
    $backendId = Invoke-Docker ($compose + @('ps', '-a', '-q', 'backend')) 'No se pudo identificar el backend.'
    if ($backendId -and
        (Invoke-Docker @('inspect', '-f', '{{.Image}}', $backendId) 'No se pudo inspeccionar el backend.') -ne $backendImageId) {
        throw 'El backend existente usa otra imagen. Existing no reemplaza contenedores.'
    }
    $heads = @(Invoke-Docker @('run', '--rm', '--pull', 'never', '--network', 'none', '--read-only',
        '--entrypoint', 'alembic', $backendImageId, 'heads') `
        'No se pudo determinar la revisión de la imagen local del backend. Construye o carga la imagen aprobada primero.')
    if ($heads.Count -ne 1 -or $heads[0] -notmatch '^(?<revision>[A-Za-z0-9_]+) \(head\)$') {
        throw 'La imagen debe tener una única revisión Alembic esperada.'
    }
    $head = $Matches.revision
    $running = $dbId -and ($consumers -contains $dbId)
    try {
        Invoke-Docker ($compose + @('up', '-d', '--no-deps', '--no-recreate', '--no-build', '--pull', 'never',
            '--wait', '--wait-timeout', '120', 'db')) 'PostgreSQL no quedó saludable.' | Out-Null
        $revision = @(Invoke-Docker ($compose + @('exec', '-T', 'db', 'psql', '-X', '-v', 'ON_ERROR_STOP=1',
            '-U', $config.services.db.environment.POSTGRES_USER, '-d', $database, '-Atc', 'SELECT version_num FROM alembic_version')) `
            'No se pudo leer la revisión existente. Existing no inicializa ni migra la base.')
        if ($revision.Count -ne 1 -or $revision[0] -cne $head) {
            throw 'La revisión PostgreSQL difiere de la imagen. Existing se detuvo sin migrar. Revisa el respaldo y la aprobación antes de aplicar migraciones por separado.'
        }
    } catch {
        if (-not $running) {
            Invoke-Docker ($compose + @('stop', 'db')) 'No se pudo detener el PostgreSQL iniciado para la comprobación.' | Out-Null
        }
        throw
    }
    Invoke-Docker ($compose + @('up', '-d', '--no-deps', '--no-recreate', '--no-build', '--pull', 'never',
        '--wait', '--wait-timeout', '120', 'backend', 'ia', 'frontend')) `
        'El stack no quedó saludable. Consulta docker compose ps y los logs locales.' | Out-Null
}

if ($Mode -eq 'FreshDemo') {
    $volumes = @(Invoke-Docker @('volume', 'ls', '-q', '--filter', "name=$volume") 'No se pudo inventariar volúmenes.')
    $containers = @(Invoke-Docker @('ps', '-aq', '--filter', "label=com.docker.compose.project=$Project") 'No se pudo inventariar contenedores.')
    $networks = @(Invoke-Docker @('network', 'ls', '-q', '--filter', "name=$Project") 'No se pudo inventariar redes.')
    if (($volumes -contains $volume) -or $containers.Count -or $networks.Count) {
        throw 'FreshDemo exige un proyecto y volumen sin uso previo. Elige un nombre nuevo.'
    }

    $seed = $config.services.seed
    $seedMount = @($seed.volumes | Where-Object target -eq '/seed/input.csv')
    if ($seedMount.Count -ne 1 -or $seedMount[0].type -ne 'bind' -or -not $seedMount[0].read_only -or
        $seedMount[0].bind.create_host_path -ne $false -or
        $seed.environment.SEED_CONFIRMAR_BD -cne $database -or
        $seed.environment.DATABASE_URL -cne $config.services.backend.environment.DATABASE_URL -or
        $seed.environment.DATABASE_URL_MIGRACIONES -or
        [string]::IsNullOrWhiteSpace($seed.environment.SEED_PASSWORD)) {
        throw 'Revisa el montaje del CSV, SEED_CONFIRMAR_BD y la clave de usuarios demo. El seed requiere el rol operativo.'
    }
    $csv = Resolve-File $seedMount[0].source 'el CSV sintético de SEED_CSV_PATH'
    $expected = $seed.environment.SEED_CSV_SHA256
    if ($expected -cnotmatch '^[a-f0-9]{64}$' -or (Get-FileHash -LiteralPath $csv).Hash.ToLowerInvariant() -cne $expected) {
        throw 'El hash del CSV sintético no coincide con SEED_CSV_SHA256.'
    }

    Invoke-Docker ($compose + @('build', 'migraciones', 'seed', 'backend', 'ia', 'frontend')) `
        'No se pudieron construir las imágenes de FreshDemo.' | Out-Null
    $claim = [guid]::NewGuid().ToString('N')
    Invoke-Docker @('volume', 'create', '--label', "com.docker.compose.project=$Project",
        '--label', "predicitas.freshdemo.claim=$claim", $volume) `
        'No se pudo crear el volumen nuevo de FreshDemo.' | Out-Null
    $actualClaim = Invoke-Docker @('volume', 'inspect', '-f', '{{index .Labels "predicitas.freshdemo.claim"}}', $volume) `
        'No se pudo verificar la identidad del volumen nuevo.'
    if ($actualClaim -cne $claim) { throw 'El volumen fue creado por otra ejecución. FreshDemo se detuvo.' }
    try {
        Invoke-Docker ($compose + @('up', '-d', '--no-deps', '--no-build', '--wait', '--wait-timeout', '120', 'db')) `
            'PostgreSQL demo no quedó saludable.' | Out-Null
        Invoke-Docker ($compose + @('run', '--rm', '-T', '--no-deps', '--pull', 'never', 'migraciones')) `
            'Las migraciones de la demo fallaron.' | Out-Null
        Invoke-Docker ($compose + @('run', '--rm', '-T', '--no-deps', '--pull', 'never', 'seed')) `
            'El seed sintético falló. Se conserva el volumen de laboratorio para diagnóstico.' | Out-Null
        Invoke-Docker ($compose + @('up', '-d', '--no-deps', '--no-build', '--wait', '--wait-timeout', '120', 'backend', 'ia')) `
            'Backend o IA no quedaron saludables.' | Out-Null
        Invoke-Docker ($compose + @('up', '-d', '--no-deps', '--no-build', '--wait', '--wait-timeout', '120', 'frontend')) `
            'El frontend de la demo no arrancó.' | Out-Null
        $prediction = @'
from app.modules.ia.dependencias import crear_motor
from app.modules.ia.puerto import FeaturesMotor

features = FeaturesMotor(especialidad="CARDIOLOGIA", tipo_paciente="NUEVO",
    canal_origen="WEB", franja_horaria="MANANA", dia_semana="LUNES",
    antelacion_dias=1, inasistencias_previas=0, asistencias_previas=0,
    reprogramaciones_prev=0)
with crear_motor() as motor:
    version = motor.version()
    result = motor.predecir(features, version=version)
    assert result.version_modelo == version and result.features_snapshot == features.snapshot()
'@
        Invoke-Docker ($compose + @('exec', '-T', 'backend', 'python', '-B', '-c', $prediction)) `
            'La inferencia sintética de FreshDemo falló.' | Out-Null
    } catch {
        Invoke-Docker ($compose + @('stop')) 'No se pudo detener el laboratorio FreshDemo.' | Out-Null
        throw
    }
}

$services = Invoke-Docker ($compose + @('ps', '-a')) 'No se pudo consultar el estado del stack.'
[pscustomobject]@{
    Modo = $Mode
    Proyecto = $config.name
    Volumen = $volume
    Modelo = 'Artefacto presente en montaje de solo lectura'
    Servicios = $services -join [Environment]::NewLine
}
