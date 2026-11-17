# One-time setup of the Icarus daemon executor container on Windows (Docker Desktop).
# Asks for the two secrets (input hidden), checks both work, writes them OUTSIDE the repo,
# then builds and starts the container. The container restarts with Docker, so it runs
# whenever the laptop is on; jobs queued by the pulse wait in icarus/ledger/queue until then.
#
# Run from PowerShell:
#   powershell -ExecutionPolicy Bypass -File docker\setup-primitives.ps1
#
# Where to get the two values (both already exist in the Apps Script project):
#   Apps Script editor -> Project Settings (gear) -> Script Properties
#     GITHUB_PAT      -> paste when asked for the GitHub token
#     GEMINI_API_KEY  -> paste when asked for the Gemini key
#     OPENROUTER_API_KEY (optional) -> adds OpenRouter :free models to the switcher; Enter to skip
#
# The daemon rotates models with the model switcher (icarus/primitives/switcher.py) over
# icarus/runtime/approved-routes.json: rate limited -> next model, task intact.
$ErrorActionPreference = 'Stop'
$Repo   = 'the1mburke-blip/Teamchat'
$Model  = 'gemini-3.5-flash-lite'   # switcher start model (first approved route); used for the key check
$ApiUrl = 'https://generativelanguage.googleapis.com/v1beta/openai'
$Here   = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root   = Split-Path -Parent $Here
$EnvDir = Join-Path $env:USERPROFILE '.icarus'
$EnvFile = Join-Path $EnvDir 'primitives.env'

function Read-Secret($prompt) {
  $s = Read-Host -AsSecureString $prompt
  $b = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($s)
  try { return ([Runtime.InteropServices.Marshal]::PtrToStringBSTR($b)).Trim() }
  finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($b) }
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  Write-Host 'OWNER ASSISTANCE REQUIRED - start Docker Desktop, then run this again'
  Write-Host 'Evidence: docker not found on PATH'; exit 3
}
docker info *> $null
if ($LASTEXITCODE -ne 0) {
  Write-Host 'OWNER ASSISTANCE REQUIRED - start Docker Desktop, then run this again'
  Write-Host 'Evidence: docker info failed (engine not running)'; exit 3
}

$gh = Read-Secret 'GitHub token (GITHUB_PAT from Apps Script Script Properties)'
$gk = Read-Secret 'Gemini key (GEMINI_API_KEY from Apps Script Script Properties)'
$ok = Read-Secret 'OpenRouter key (optional, press Enter to skip)'

# Check 1: token can push to the repo
try {
  $r = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo" -Headers @{ Authorization = "Bearer $gh"; 'User-Agent' = 'icarus-setup' }
} catch { Write-Host "FAIL: GitHub token rejected ($($_.Exception.Message)). Nothing written."; exit 1 }
if (-not $r.permissions.push) { Write-Host 'FAIL: GitHub token has no push access to Teamchat. Nothing written.'; exit 1 }
Write-Host 'OK  GitHub token: push access confirmed'

# Check 2: the model answers JSON through the OpenAI-compatible endpoint
$body = @{ model = $Model; temperature = 0; response_format = @{ type = 'json_object' };
  messages = @(@{ role = 'user'; content = 'Reply with the JSON object {"ok": true} only.' }) } | ConvertTo-Json -Depth 5
try {
  $m = Invoke-RestMethod -Method Post -Uri "$ApiUrl/chat/completions" -ContentType 'application/json' `
    -Headers @{ Authorization = "Bearer $gk" } -Body $body
  $ans = $m.choices[0].message.content | ConvertFrom-Json
} catch { Write-Host "FAIL: Gemini call failed ($($_.Exception.Message)). Nothing written."; exit 1 }
if ($ans.ok -ne $true) { Write-Host "FAIL: model did not return the expected JSON. Nothing written."; exit 1 }
Write-Host "OK  Model $Model answered JSON"

# Write secrets outside the repo (never committed)
New-Item -ItemType Directory -Force -Path $EnvDir | Out-Null
@(
  "GH_TOKEN=$gh",
  "TARGET_REPO=$Repo",
  'ICARUS_LEDGER_BRANCH=main',
  "GEMINI_API_KEY=$gk",
  "OPENROUTER_API_KEY=$ok",
  'ICARUS_RUNNER_ID=laptop-daemon',
  'ICARUS_POLL_SECONDS=60'
) | Set-Content -Path $EnvFile -Encoding ascii
icacls $EnvFile /inheritance:r /grant:r "$($env:USERNAME):(R,W)" *> $null
Write-Host "OK  Settings written to $EnvFile (your user only)"

# Build and (re)start the container
docker build -f (Join-Path $Here 'Dockerfile.primitives') -t icarus-primitives $Root
if ($LASTEXITCODE -ne 0) { Write-Host 'FAIL: docker build failed'; exit 1 }
docker rm -f icarus-primitives *> $null
docker run -d --name icarus-primitives --restart unless-stopped --env-file $EnvFile `
  -v icarus-ledger:/data/ledger -v icarus-work:/data/work `
  --cap-drop ALL --security-opt no-new-privileges:true icarus-primitives | Out-Null
if ($LASTEXITCODE -ne 0) { Write-Host 'FAIL: docker run failed'; exit 1 }

Start-Sleep -Seconds 20
$state = docker inspect -f '{{.State.Status}}' icarus-primitives
Write-Host "Container state: $state"
docker logs --tail 5 icarus-primitives
if ($state -ne 'running') { Write-Host 'FAIL: container is not running (see logs above)'; exit 1 }
Write-Host 'DONE: icarus-primitives is running and restarts with Docker Desktop.'
