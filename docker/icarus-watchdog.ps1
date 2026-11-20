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

# docker can hang when the engine is wedged, so every call runs as a direct child process with a
# hard timeout. (A Start-Job per call spawned a whole PowerShell host and took minutes under load,
# which produced a false "engine down" and a run killed by the task's time limit on 2026-11-18.)
$DockerExe = (Get-Command docker -ErrorAction SilentlyContinue).Source
function Invoke-Docker([string[]]$DockerArgs, [int]$TimeoutSeconds = 30) {
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = $DockerExe
  $psi.Arguments = ($DockerArgs | ForEach-Object { if ($_ -match '[\s"]') { '"' + ($_ -replace '"', '\"') + '"' } else { $_ } }) -join ' '
  $psi.UseShellExecute = $false; $psi.CreateNoWindow = $true
  $psi.RedirectStandardOutput = $true; $psi.RedirectStandardError = $true
  $sw = [Diagnostics.Stopwatch]::StartNew()
  $p = [System.Diagnostics.Process]::Start($psi)
  $out = $p.StandardOutput.ReadToEndAsync(); $err = $p.StandardError.ReadToEndAsync()
  if (-not $p.WaitForExit($TimeoutSeconds * 1000)) {
    try { $p.Kill() } catch { }
    return [pscustomobject]@{ Code = 124; Out = 'timeout'; Seconds = [int]$sw.Elapsed.TotalSeconds }
  }
  $p.WaitForExit()
  return [pscustomobject]@{ Code = $p.ExitCode; Out = ($out.Result + $err.Result).Trim(); Seconds = [math]::Round($sw.Elapsed.TotalSeconds, 1) }
}

function Test-Engine { return ((Invoke-Docker @('info', '--format', '{{.ServerVersion}}')).Code -eq 0) }

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  Write-Log 'OWNER ASSISTANCE REQUIRED - docker CLI not on PATH (is Docker Desktop installed?)'; exit 3
}

# 1. Engine (one quick re-check before calling it down, so a single slow reply is not an outage)
$engineUp = Test-Engine
if (-not $engineUp) { Start-Sleep -Seconds 5; $engineUp = Test-Engine }
if (-not $engineUp) {
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
  'running'    { Write-Log "ok $Container running (restarts=$restarts, check $($st.Seconds)s)"; exit 0 }
  'restarting' { Write-Log "WARN $Container is restart-looping (restarts=$restarts); not touching it - check: docker logs --tail 20 $Container"; exit 0 }
  'paused'     { $r = Invoke-Docker @('unpause', $Container) }
  default      { $r = Invoke-Docker @('start', $Container) 60 }
}
Start-Sleep -Seconds 15
$after = (Invoke-Docker @('inspect', '-f', '{{.State.Status}}', $Container)).Out.Trim()
if ($after -eq 'running') { Write-Log "recovered: $Container was '$status', now running"; exit 0 }
Write-Log "FAIL $Container was '$status', start returned code $($r.Code), now '$after'; will retry next run"
exit 2
