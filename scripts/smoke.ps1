#requires -Version 7.0
[CmdletBinding()]
param(
    [uri]$ApiUrl = 'http://localhost:8000',
    [uri]$FrontendUrl = 'http://localhost:5173',
    [pscredential]$Credential,
    [ValidateRange(0, 2147483647)]
    [int]$PredictAppointmentId = 0,
    [switch]$AllowWrites
)

$ErrorActionPreference = 'Stop'
foreach ($url in @($ApiUrl, $FrontendUrl)) {
    if (-not $url.IsAbsoluteUri -or -not $url.IsLoopback -or $url.Scheme -notin @('http', 'https') -or
        $url.UserInfo -or $url.AbsolutePath -ne '/' -or $url.Query -or $url.Fragment) {
        throw 'Indica un origen HTTP local sin credenciales ni ruta.'
    }
}
if (($Credential -or $PredictAppointmentId) -and -not $AllowWrites) {
    throw 'Login e inferencia pueden escribir auditoría o datos. Usa -AllowWrites solo en laboratorio o con autorización.'
}
if ($PredictAppointmentId -and -not $Credential) {
    throw 'La inferencia requiere una credencial demo.'
}

$api = $ApiUrl.GetLeftPart([UriPartial]::Authority)
$frontend = $FrontendUrl.GetLeftPart([UriPartial]::Authority)
function Invoke-Probe([string]$Step, [hashtable]$Request) {
    try {
        Invoke-RestMethod @Request -TimeoutSec 15 -MaximumRedirection 0
    } catch {
        $status = if ($_.Exception.Response) { [int]$_.Exception.Response.StatusCode } else { 'sin respuesta HTTP' }
        throw "Smoke falló en ${Step}: $status."
    }
}

foreach ($path in @('/health', '/health/ready')) {
    $health = Invoke-Probe $path @{ Uri = "$api$path" }
    if ($health.estado -ne 'ok') { throw "Respuesta inesperada de $path." }
}
Invoke-Probe 'frontend' @{ Uri = "$frontend/" } | Out-Null
$result = [ordered]@{ Salud = 'OK'; PostgreSQL = 'OK'; Frontend = 'OK'; Login = 'Omitido'; Lectura = 'Omitida'; Inferencia = 'Omitida' }

if ($Credential) {
    $login = Invoke-Probe 'login' @{
        Uri = "$api/auth/login"; Method = 'POST'; ContentType = 'application/x-www-form-urlencoded'
        Body = @{ username = $Credential.UserName; password = $Credential.GetNetworkCredential().Password }
    }
    if (-not $login.access_token) { throw 'El login no devolvió una sesión.' }
    $headers = @{ Authorization = "Bearer $($login.access_token)" }
    $me = Invoke-Probe 'identidad' @{ Uri = "$api/auth/me"; Headers = $headers }
    if ($me.rol -notin @('ADMINISTRADOR', 'RECEPCION', 'TECNICO_IA')) { throw 'Rol inesperado en /auth/me.' }
    Invoke-Probe 'lectura de citas' @{ Uri = "$api/citas?limite=1"; Headers = $headers } | Out-Null
    $result.Login = 'OK'
    $result.Lectura = 'OK'
    if ($PredictAppointmentId) {
        $prediction = Invoke-Probe 'inferencia' @{
            Uri = "$api/ia/predecir/$PredictAppointmentId"; Method = 'POST'; Headers = $headers
        }
        if ($prediction.id_cita -ne $PredictAppointmentId -or -not $prediction.version_modelo) {
            throw 'La inferencia no devolvió la cita solicitada o la versión del modelo.'
        }
        $result.Inferencia = 'OK'
    }
}
[pscustomobject]$result
