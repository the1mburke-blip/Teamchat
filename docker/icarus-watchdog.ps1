# Icarus daemon watchdog (Windows). Keeps Docker Desktop and the icarus-primitives container up.
# Run by the scheduled task IcarusDaemonWatchdog (install-icarus-watchdog.ps1) at logon and every
# 10 minutes. It never reads or prints the env file: it only starts the EXISTING container, and
# `docker start` reuses the container's saved configuration.
#
# Exit codes: 0 healthy or recovered | 2 Docker engine did not come up | 3 owner assistance required
param(
  [string]$Container = 'icarus-primitives',
  [int]$EngineWaitSeconds = 240,
  [string]$LogPath = (Join-Path $env:USERPROFILE '.icarus\watchdog.log')
)
$ErrorActionPreference = 'Continue'

function Write-Log([string]$msg) {
  $line = '{0}Z {1}' -f (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ss'), $msg
  New-Item -ItemType Directory -Force -Path (Split-Path $LogPath) | Out-Null
  Add-Content -Path $LogPath -Value $line -Encoding ascii
  $all = @(Get-Content $LogPath)
  if ($all.Count -gt 2000) { $all | Select-Object -Last 1000 | Set-Content $LogPath -Encoding ascii }
}

# docker can hang when the engine is wedged, so every call runs with a timeout.
function Invoke-Docker([string[]]$DockerArgs, [int]$TimeoutSeconds = 30) {
  $job = Start-Job -ScriptBlock { param($a) $out = & docker @a 2>&1; [pscustomobject]@{ Code = $LASTEXITCODE; Out = ($out -join "`n") } } -ArgumentList (,$DockerArgs)
  if (Wait-Job $job -Timeout $TimeoutSeconds) { $r = Receive-Job $job } else { Stop-Job $job; $r = [pscustomobject]@{ Code = 124; Out = 'timeout' } }
  Remove-Job $job -Force
  return $r
}

function Test-Engine { return ((Invoke-Docker @('info', '--format', '{{.ServerVersion}}')).Code -eq 0) }

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  Write-Log 'OWNER ASSISTANCE REQUIRED - docker CLI not on PATH (is Docker Desktop installed?)'; exit 3
}

# 1. Engine
if (-not (Test-Engine)) {
  $exe = Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'
  if (-not (Get-Process -Name 'Docker Desktop' -ErrorAction SilentlyContinue)) {
    if (-not (Test-Path $exe)) { Write-Log "OWNER ASSISTANCE REQUIRED - Docker Desktop not found at $exe"; exit 3 }
    Start-Process -FilePath $exe | Out-Null
    Write-Log 'engine down; Docker Desktop was not running - started it'
  } else {
    Write-Log 'engine down; Docker Desktop is running - waiting for the engine'
  }
  $deadline = (Get-Date).AddSeconds($EngineWaitSeconds)
  while ((Get-Date) -lt $deadline -and -not (Test-Engine)) { Start-Sleep -Seconds 10 }
  if (-not (Test-Engine)) { Write-Log "FAIL engine still down after ${EngineWaitSeconds}s; will retry next run"; exit 2 }
  Write-Log 'engine up'
}

# 2. Container
$st = Invoke-Docker @('inspect', '-f', '{{.State.Status}} {{.RestartCount}}', $Container)
if ($st.Code -ne 0) {
  Write-Log "OWNER ASSISTANCE REQUIRED - container $Container does not exist; run docker\setup-primitives.ps1"; exit 3
}
$status, $restarts = ($st.Out.Trim() -split ' ', 2)
switch ($status) {
  'running'    { Write-Log "ok $Container running (restarts=$restarts)"; exit 0 }
  'restarting' { Write-Log "WARN $Container is restart-looping (restarts=$restarts); not touching it - check: docker logs --tail 20 $Container"; exit 0 }
  'paused'     { $r = Invoke-Docker @('unpause', $Container) }
  default      { $r = Invoke-Docker @('start', $Container) 60 }
}
Start-Sleep -Seconds 15
$after = (Invoke-Docker @('inspect', '-f', '{{.State.Status}}', $Container)).Out.Trim()
if ($after -eq 'running') { Write-Log "recovered: $Container was '$status', now running"; exit 0 }
Write-Log "FAIL $Container was '$status', start returned code $($r.Code), now '$after'; will retry next run"
exit 2
