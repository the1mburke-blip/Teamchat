# Installs (or removes) the scheduled task that runs icarus-watchdog.ps1 for the current user.
#   Install:   powershell -ExecutionPolicy Bypass -File docker\install-icarus-watchdog.ps1
#   Remove:    powershell -ExecutionPolicy Bypass -File docker\install-icarus-watchdog.ps1 -Uninstall
# The watchdog is copied to %USERPROFILE%\.icarus so the task does not depend on any git checkout.
# Runs only while you are logged on (Docker Desktop is a per-user app). No admin rights needed.
param([switch]$Uninstall, [int]$EveryMinutes = 10)
$ErrorActionPreference = 'Stop'
$TaskName = 'IcarusDaemonWatchdog'
$Dest = Join-Path $env:USERPROFILE '.icarus\icarus-watchdog.ps1'
$User = "$env:USERDOMAIN\$env:USERNAME"

if ($Uninstall) {
  Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
  Remove-Item $Dest -ErrorAction SilentlyContinue
  Write-Host "Removed scheduled task $TaskName and $Dest (the log in .icarus is kept)."
  exit 0
}

New-Item -ItemType Directory -Force -Path (Split-Path $Dest) | Out-Null
Copy-Item (Join-Path $PSScriptRoot 'icarus-watchdog.ps1') $Dest -Force

# conhost --headless keeps a console window from flashing up every 10 minutes (Windows 11).
$action = New-ScheduledTaskAction -Execute (Join-Path $env:SystemRoot 'System32\conhost.exe') `
  -Argument "--headless powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$Dest`""
$every = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes $EveryMinutes)
$logon = New-ScheduledTaskTrigger -AtLogOn -User $User
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
  -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 8)
$principal = New-ScheduledTaskPrincipal -UserId $User -LogonType Interactive -RunLevel Limited
$desc = 'Icarus: keeps Docker Desktop and the icarus-primitives container running. Remove with install-icarus-watchdog.ps1 -Uninstall.'

$triggers = 'logon + every ' + $EveryMinutes + ' min'
try {
  Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $every, $logon -Settings $settings `
    -Principal $principal -Description $desc -Force | Out-Null
} catch {
  # Logon triggers can need admin rights; the repeating trigger alone still covers restarts.
  Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $every -Settings $settings `
    -Principal $principal -Description $desc -Force | Out-Null
  $triggers = 'every ' + $EveryMinutes + ' min (logon trigger needs admin; skipped)'
}

$t = Get-ScheduledTask -TaskName $TaskName
Write-Host "Installed $TaskName for $User : $triggers ; state=$($t.State)"
Write-Host "Watchdog copy: $Dest"
Write-Host "Log: $(Join-Path $env:USERPROFILE '.icarus\watchdog.log')"
