$ErrorActionPreference = "Stop"

function Join-UnicodeChars {
  param([int[]]$Codes)
  return -join ($Codes | ForEach-Object { [char]$_ })
}

$platformName = Join-UnicodeChars @(28040, 21270, 20869, 38236, 30740, 20462, 19982, 27169, 22411, 35780, 27979, 24179, 21488)
try {
  $Host.UI.RawUI.WindowTitle = $platformName
} catch {
}

$codeRoot = Split-Path -Parent $PSScriptRoot
$backendRoot = Join-Path $codeRoot "backend"
$frontendRoot = Join-Path $codeRoot "frontend"
$frontendDist = Join-Path $frontendRoot "dist"
$logsRoot = Join-Path $codeRoot "runtime_logs"
$backendPidFile = Join-Path $logsRoot "web-demo-backend.pid"
$frontendPidFile = Join-Path $logsRoot "web-demo-frontend.pid"
$factoryWorkerPidFile = Join-Path $logsRoot "web-demo-factory-worker.pid"
$backendPort = if ($env:ARIS_BACKEND_PORT) { [int]$env:ARIS_BACKEND_PORT } else { 8002 }
$frontendPort = if ($env:ARIS_FRONTEND_PORT) { [int]$env:ARIS_FRONTEND_PORT } else { 5174 }
$redisPort = if ($env:ARIS_REDIS_PORT) { [int]$env:ARIS_REDIS_PORT } else { 56379 }
$qdrantPort = if ($env:ARIS_QDRANT_PORT) { [int]$env:ARIS_QDRANT_PORT } else { 6333 }

# The public checkout does not redistribute the optional large QBank source
# files.  Start with the compact, self-contained teaching seed; a developer
# who has locally authorized source files can opt into the full bootstrap.
# Respect an explicit caller override for acceptance runs or local imports.
if (-not $env:ENDO_DEMO_QBANK_BOOTSTRAP) {
  $env:ENDO_DEMO_QBANK_BOOTSTRAP = "false"
}
if (-not $env:ENDO_PROJECT_DATA_ROOT) {
  $env:ENDO_PROJECT_DATA_ROOT = Join-Path $codeRoot "data"
}
$backendUrl = "http://127.0.0.1:$backendPort"
$frontendUrl = "http://127.0.0.1:$frontendPort"

New-Item -ItemType Directory -Force -Path $logsRoot | Out-Null

try {
  [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
} catch {
}

function Write-Step {
  param([string]$Text)
  Write-Host $Text -ForegroundColor Cyan
}

function Open-DemoBrowser {
  param([string]$Url)
  if ($env:ARIS_BROWSER_DEFERRED -eq "1") {
    return
  }
  try {
    $opener = Join-Path $env:SystemRoot "System32\rundll32.exe"
    Start-Process -FilePath $opener -ArgumentList @("url.dll,FileProtocolHandler", $Url) -WindowStyle Hidden | Out-Null
  } catch {
    Write-Host "Open manually: $Url" -ForegroundColor Yellow
  }
}

function Show-LogTail {
  param(
    [string]$Path,
    [int]$Lines = 80
  )
  if (Test-Path -LiteralPath $Path) {
    Write-Host ""
    Write-Host "---- $Path ----" -ForegroundColor Yellow
    $content = Get-Content -LiteralPath $Path -Tail $Lines -ErrorAction SilentlyContinue
    if ($content) {
      $content
    } else {
      Write-Host "(no log output)" -ForegroundColor DarkGray
    }
    Write-Host "----------------" -ForegroundColor Yellow
  }
}

function Show-ServiceLogs {
  param(
    [string]$Name,
    [string]$StdoutPath,
    [string]$StderrPath
  )
  Write-Host ""
  Write-Host "$Name diagnostics:" -ForegroundColor Yellow
  Show-LogTail -Path $StdoutPath
  Show-LogTail -Path $StderrPath
}

function Get-PythonExecutable {
  if ($env:ARIS_PYTHON -and (Test-Path -LiteralPath $env:ARIS_PYTHON)) {
    $envPython = Resolve-Path -LiteralPath $env:ARIS_PYTHON -ErrorAction SilentlyContinue
    if ($envPython -and (Test-PythonUsable -PythonPath $envPython.Path)) {
      return $envPython.Path
    }
  }

  $candidates = New-Object System.Collections.Generic.List[string]
  $knownPaths = @(
    "E:\developer\Anaconda3\python.exe",
    "D:\developer\Anaconda3\python.exe",
    "C:\ProgramData\Anaconda3\python.exe",
    "$env:USERPROFILE\anaconda3\python.exe",
    "$env:USERPROFILE\miniconda3\python.exe"
  )
  foreach ($path in $knownPaths) {
    if ($path -and (Test-Path -LiteralPath $path)) {
      $candidates.Add((Resolve-Path -LiteralPath $path).Path)
    }
  }

  try {
    $whereResults = & where.exe python 2>$null
    foreach ($path in $whereResults) {
      if ($path -and (Test-Path -LiteralPath $path)) {
        $candidates.Add((Resolve-Path -LiteralPath $path).Path)
      }
    }
  } catch {
  }

  try {
    $commands = Get-Command -All python -ErrorAction SilentlyContinue
    foreach ($command in $commands) {
      if ($command.Source -and (Test-Path -LiteralPath $command.Source)) {
        $candidates.Add((Resolve-Path -LiteralPath $command.Source).Path)
      }
    }
  } catch {
  }

  foreach ($candidate in ($candidates | Select-Object -Unique)) {
    if ($candidate -match "\\WindowsApps\\") {
      continue
    }
    if (Test-PythonUsable -PythonPath $candidate) {
      return $candidate
    }
  }
  throw "No usable Python runtime was found. Please install backend dependencies with a real Python, or set ARIS_PYTHON to a Python executable that has fastapi and uvicorn installed."
}

function Test-PythonUsable {
  param([string]$PythonPath)
  if (-not $PythonPath -or -not (Test-Path -LiteralPath $PythonPath)) {
    return $false
  }
  if ($PythonPath -match "\\WindowsApps\\") {
    return $false
  }
  try {
    $probe = & $PythonPath -c "import sys; import fastapi, uvicorn; print(sys.executable)" 2>$null
    return $LASTEXITCODE -eq 0 -and $probe
  } catch {
    return $false
  }
}

function Stop-PidFileProcess {
  param([string]$PidFile)
  if (-not (Test-Path -LiteralPath $PidFile)) {
    return
  }
  $pidText = (Get-Content -Raw -LiteralPath $PidFile -ErrorAction SilentlyContinue).Trim()
  if ($pidText) {
    try {
      $process = Get-Process -Id ([int]$pidText) -ErrorAction Stop
      Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    } catch {
    }
  }
  Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
}

function Stop-DemoPortProcess {
  param([int]$Port)
  try {
    $connections = Get-NetTCPConnection -LocalAddress "127.0.0.1" -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
  } catch {
    $connections = @()
  }
  foreach ($connection in $connections) {
    try {
      $process = Get-Process -Id $connection.OwningProcess -ErrorAction Stop
      if ($process.ProcessName -in @("python", "python3", "node", "npm", "cmd")) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
      }
    } catch {
    }
  }
}

function Test-HttpOk {
  param([string]$Url)
  try {
    $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 2
    return [int]$response.StatusCode -ge 200 -and [int]$response.StatusCode -lt 500
  } catch {
    return $false
  }
}

function Test-PortOpen {
  param(
    [int]$Port,
    [int]$TimeoutMs = 300
  )
  $client = New-Object System.Net.Sockets.TcpClient
  try {
    $async = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
    if (-not $async.AsyncWaitHandle.WaitOne($TimeoutMs, $false)) {
      return $false
    }
    $client.EndConnect($async)
    return $true
  } catch {
    return $false
  } finally {
    try { $client.Close() } catch {}
  }
}

function Wait-PortOpen {
  param(
    [int]$Port,
    [int]$Seconds = 30,
    [int]$ProcessId = 0,
    [string]$LogPath = ""
  )
  $deadline = (Get-Date).AddSeconds($Seconds)
  while ((Get-Date) -lt $deadline) {
    if (Test-PortOpen -Port $Port) {
      return $true
    }
    if ($ProcessId -gt 0) {
      $process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
      if (-not $process) {
        if ($LogPath) {
          Show-LogTail -Path $LogPath
        }
        return $false
      }
    }
    Start-Sleep -Milliseconds 250
  }
  if ($LogPath) {
    Show-LogTail -Path $LogPath
  }
  return $false
}

function Wait-HttpOk {
  param(
    [string]$Url,
    [int]$Seconds = 120,
    [int]$ProcessId = 0,
    [string]$LogPath = ""
  )
  $deadline = (Get-Date).AddSeconds($Seconds)
  while ((Get-Date) -lt $deadline) {
    if (Test-HttpOk -Url $Url) {
      return $true
    }
    if ($ProcessId -gt 0) {
      $process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
      if (-not $process) {
        if ($LogPath) {
          Show-LogTail -Path $LogPath
        }
        return $false
      }
    }
    Start-Sleep -Milliseconds 700
  }
  if ($LogPath) {
    Show-LogTail -Path $LogPath
  }
  return $false
}

function Get-DockerDesktopExecutable {
  $candidates = @(
    (Join-Path $env:LOCALAPPDATA "Programs\DockerDesktop\Docker Desktop.exe"),
    "C:\Program Files\Docker\Docker\Docker Desktop.exe"
  )
  foreach ($candidate in $candidates) {
    if ($candidate -and (Test-Path -LiteralPath $candidate)) {
      return (Resolve-Path -LiteralPath $candidate).Path
    }
  }
  return ""
}

function Test-DockerEngine {
  param([string]$DockerPath)
  try {
    $null = & $DockerPath info --format '{{.ServerVersion}}' 2>$null
    return $LASTEXITCODE -eq 0
  } catch {
    return $false
  }
}

function Wait-DockerEngine {
  param(
    [string]$DockerPath,
    [int]$Seconds = 90
  )
  $deadline = (Get-Date).AddSeconds($Seconds)
  while ((Get-Date) -lt $deadline) {
    if (Test-DockerEngine -DockerPath $DockerPath) {
      return $true
    }
    Start-Sleep -Seconds 2
  }
  return $false
}

function Start-LocalInfrastructure {
  $docker = Get-Command docker -ErrorAction SilentlyContinue
  if (-not $docker) {
    Write-Host "Local infrastructure: Docker CLI not found; semantic retrieval and background generation are unavailable." -ForegroundColor Yellow
    return $false
  }

  if (-not (Test-DockerEngine -DockerPath $docker.Source)) {
    $dockerDesktop = Get-DockerDesktopExecutable
    if (-not $dockerDesktop) {
      Write-Host "Local infrastructure: Docker Desktop was not found; semantic retrieval and background generation are unavailable." -ForegroundColor Yellow
      return $false
    }
    Write-Step "Starting Docker Desktop for local retrieval services..."
    Start-Process -FilePath $dockerDesktop -WindowStyle Hidden | Out-Null
    if (-not (Wait-DockerEngine -DockerPath $docker.Source)) {
      Write-Host "Local infrastructure: Docker Desktop did not become ready; semantic retrieval and background generation are unavailable." -ForegroundColor Yellow
      return $false
    }
  }

  Write-Step "Starting local Redis and Qdrant services..."
  Push-Location $codeRoot
  try {
    & $docker.Source compose up -d redis qdrant
    $composeExit = $LASTEXITCODE
  } finally {
    Pop-Location
  }
  if ($composeExit -ne 0) {
    Write-Host "Local infrastructure: Redis/Qdrant startup failed; Factory generation remains unavailable." -ForegroundColor Yellow
    return $false
  }

  $redisReady = Wait-PortOpen -Port $redisPort -Seconds 30
  $qdrantReady = Wait-HttpOk -Url "http://127.0.0.1:$qdrantPort/collections" -Seconds 60
  if (-not $redisReady) {
    Write-Host "Local infrastructure: Redis did not become ready on 127.0.0.1:$redisPort." -ForegroundColor Yellow
  }
  if (-not $qdrantReady) {
    Write-Host "Local infrastructure: Qdrant did not become ready on 127.0.0.1:$qdrantPort." -ForegroundColor Yellow
  }
  if ($redisReady -and $qdrantReady) {
    Write-Host "Local infrastructure: Redis and Qdrant ready." -ForegroundColor Green
    return $true
  }
  return $false
}

function Start-FactoryWorker {
  if ($env:ARIS_DISABLE_FACTORY_WORKER -eq "1") {
    Write-Host "Factory worker: disabled by ARIS_DISABLE_FACTORY_WORKER=1." -ForegroundColor Yellow
    return
  }
  if (-not (Test-PortOpen -Port $redisPort)) {
    Write-Host "Factory worker: Redis is not reachable on 127.0.0.1:$redisPort; queued jobs will remain visible until Redis/Dramatiq is started." -ForegroundColor Yellow
    return
  }
  if (-not (Wait-HttpOk -Url "http://127.0.0.1:$qdrantPort/collections" -Seconds 2)) {
    Write-Host "Factory worker: Qdrant is not reachable on 127.0.0.1:$qdrantPort; start the local services before generating questions." -ForegroundColor Yellow
    return
  }
  if (Test-Path -LiteralPath $factoryWorkerPidFile) {
    $workerPidText = (Get-Content -Raw -LiteralPath $factoryWorkerPidFile -ErrorAction SilentlyContinue).Trim()
    if ($workerPidText) {
      $existing = Get-Process -Id ([int]$workerPidText) -ErrorAction SilentlyContinue
      if ($existing) {
        Write-Host "Factory worker: already running." -ForegroundColor Green
        return
      }
    }
    Remove-Item -LiteralPath $factoryWorkerPidFile -Force -ErrorAction SilentlyContinue
  }
  $workerErrLog = Join-Path $logsRoot "web-demo-factory-worker.err.log"
  $workerOutLog = Join-Path $logsRoot "web-demo-factory-worker.log"
  Remove-Item -LiteralPath $workerErrLog, $workerOutLog -Force -ErrorAction SilentlyContinue
  Write-Step "Starting Factory Dramatiq worker..."
  $worker = Start-Process -FilePath $pythonExe `
    -ArgumentList @("-m", "dramatiq", "app.workers.factory_worker", "--processes", "1", "--threads", "2") `
    -WorkingDirectory $backendRoot `
    -RedirectStandardOutput $workerOutLog `
    -RedirectStandardError $workerErrLog `
    -WindowStyle Hidden `
    -PassThru
  Set-Content -LiteralPath $factoryWorkerPidFile -Value $worker.Id -Encoding ascii
  Start-Sleep -Milliseconds 1200
  if (-not (Get-Process -Id $worker.Id -ErrorAction SilentlyContinue)) {
    Show-ServiceLogs -Name "Factory worker" -StdoutPath $workerOutLog -StderrPath $workerErrLog
    Remove-Item -LiteralPath $factoryWorkerPidFile -Force -ErrorAction SilentlyContinue
    Write-Host "Factory worker: failed to stay alive; queued jobs remain auditable but will not advance." -ForegroundColor Yellow
  } else {
    Write-Host "Factory worker: ready (Redis/Dramatiq)." -ForegroundColor Green
  }
}

function Read-LocalEnvValue {
  param([string]$Name)
  $rootEnv = Join-Path $codeRoot ".env"
  $backendEnv = Join-Path $backendRoot ".env"
  $envFiles = @($rootEnv, $backendEnv)
  foreach ($envFile in $envFiles) {
    if (-not (Test-Path -LiteralPath $envFile)) {
      continue
    }
    $line = Get-Content -LiteralPath $envFile | Where-Object {
      $_ -match "^\s*$([regex]::Escape($Name))\s*="
    } | Select-Object -First 1
    if ($line) {
      $value = ($line -replace "^\s*$([regex]::Escape($Name))\s*=\s*", "").Trim()
      return $value.Trim('"').Trim("'")
    }
  }
  return ""
}

function Get-ConfiguredBaseUrl {
  if ($env:LLM_BASE_URL) { return $env:LLM_BASE_URL }
  $value = Read-LocalEnvValue -Name "LLM_BASE_URL"
  if ($value) { return $value }
  if ($env:OPENAI_BASE_URL) { return $env:OPENAI_BASE_URL }
  $value = Read-LocalEnvValue -Name "OPENAI_BASE_URL"
  if ($value) { return $value }
  foreach ($name in @("LLM_FALLBACK_BASE_URL", "OPENROUTER_BASE_URL", "LLM_FINAL_FALLBACK_BASE_URL", "BIGMODEL_BASE_URL")) {
    $value = [Environment]::GetEnvironmentVariable($name)
    if ($value) { return $value }
    $value = Read-LocalEnvValue -Name $name
    if ($value) { return $value }
  }
  # Cloudflare Workers AI derives its endpoint from account ID, so it has no
  # standalone base URL in many normal .env configurations.
  if ($env:CLOUDFLARE_ACCOUNT_ID -or (Read-LocalEnvValue -Name "CLOUDFLARE_ACCOUNT_ID")) { return "cloudflare-workers-ai" }
  return ""
}

function Get-ConfiguredApiKey {
  if ($env:LLM_API_KEY) { return $env:LLM_API_KEY }
  $value = Read-LocalEnvValue -Name "LLM_API_KEY"
  if ($value) { return $value }
  if ($env:OPENAI_API_KEY) { return $env:OPENAI_API_KEY }
  $value = Read-LocalEnvValue -Name "OPENAI_API_KEY"
  if ($value) { return $value }
  foreach ($name in @("CLOUDFLARE_API_TOKEN", "LLM_FALLBACK_API_KEY", "OPENROUTER_API_KEY", "LLM_FINAL_FALLBACK_API_KEY", "BIGMODEL_API_KEY")) {
    $value = [Environment]::GetEnvironmentVariable($name)
    if ($value) { return $value }
    $value = Read-LocalEnvValue -Name $name
    if ($value) { return $value }
  }
  return ""
}

function Test-DemoProviderConfigured {
  return Test-Path -LiteralPath (Join-Path $codeRoot ".demo_llm_providers.json")
}

function Get-ProviderHost {
  $baseUrl = Get-ConfiguredBaseUrl
  if (-not $baseUrl) {
    return ""
  }
  try {
    $uri = [System.Uri]$baseUrl
    return $uri.Host
  } catch {
    return ""
  }
}

if (-not (Test-Path -LiteralPath (Join-Path $backendRoot "app\main.py"))) {
  throw "Backend source not found. Please run this script from the packaged code directory."
}
if (-not (Test-Path -LiteralPath (Join-Path $frontendDist "index.html"))) {
  throw "Frontend dist not found. Please use the latest package, or run npm run build before starting."
}

Start-LocalInfrastructure | Out-Null

Write-Host ""
Write-Step "Starting platform..."
Write-Host "Platform: $platformName"
Write-Host "Frontend: $frontendUrl"
Write-Host "Backend : $backendUrl"

$providerHost = Get-ProviderHost
if (-not $env:LLM_PROVIDER_PRIVATE_HOST_ALLOWLIST -and -not $env:LLM_ALLOWED_PRIVATE_HOSTS -and $providerHost) {
  $env:LLM_PROVIDER_PRIVATE_HOST_ALLOWLIST = $providerHost
}

# A configured local Provider is an explicit developer opt-in for the Tutor
# path. Keep offline/test runs on the deterministic adapter when no Provider
# credentials are present, while making the normal local start command match
# the configured Provider acceptance state.
if (-not $env:TUTOR_PROVIDER_ENABLED) {
  if ((Test-DemoProviderConfigured) -or ((Get-ConfiguredBaseUrl) -and (Get-ConfiguredApiKey))) {
    $env:TUTOR_PROVIDER_ENABLED = "true"
  } else {
    $env:TUTOR_PROVIDER_ENABLED = "false"
  }
}

if (Test-DemoProviderConfigured) {
  Write-Host "Agent: local demo provider configured." -ForegroundColor Green
} elseif ((Get-ConfiguredBaseUrl) -and (Get-ConfiguredApiKey)) {
  Write-Host "Agent: default provider chain configured." -ForegroundColor Green
} else {
  Write-Host "Agent: no default provider detected; teaching workflow can still run." -ForegroundColor Yellow
}

$backendAlreadyReady = Test-PortOpen -Port $backendPort
$frontendAlreadyReady = Test-PortOpen -Port $frontendPort

if ($backendAlreadyReady -and $frontendAlreadyReady) {
  Write-Host "Backend: already running." -ForegroundColor Green
  Write-Host "Frontend: already running." -ForegroundColor Green
  $pythonExe = Get-PythonExecutable
  Start-FactoryWorker
  Open-DemoBrowser -Url "$frontendUrl/report"
  Write-Host ""
  Write-Host "Ready: $frontendUrl/report" -ForegroundColor Green
  Write-Host "Stop: double-click Stop-Web-Demo.bat" -ForegroundColor Yellow
  return
}

if ($env:ARIS_KEEP_RUNNING -ne "1") {
  if (-not $frontendAlreadyReady) {
    Stop-PidFileProcess -PidFile $frontendPidFile
    Stop-DemoPortProcess -Port 5173
    Stop-DemoPortProcess -Port $frontendPort
  }
  if (-not $backendAlreadyReady) {
    Stop-PidFileProcess -PidFile $backendPidFile
    Stop-DemoPortProcess -Port $backendPort
  }
  Start-Sleep -Milliseconds 250
}

$backendErrLog = Join-Path $logsRoot "web-demo-backend.err.log"
$backendOutLog = Join-Path $logsRoot "web-demo-backend.log"
$frontendErrLog = Join-Path $logsRoot "web-demo-frontend.err.log"
$frontendOutLog = Join-Path $logsRoot "web-demo-frontend.log"
$pythonExe = Get-PythonExecutable

if (-not (Test-PortOpen -Port $backendPort)) {
  Stop-PidFileProcess -PidFile $backendPidFile
  Remove-Item -LiteralPath $backendErrLog, $backendOutLog -Force -ErrorAction SilentlyContinue
  Write-Step "Starting backend service..."
  Write-Host "Python : $pythonExe" -ForegroundColor DarkGray
  $backend = Start-Process -FilePath $pythonExe `
    -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$backendPort") `
    -WorkingDirectory $backendRoot `
    -RedirectStandardOutput $backendOutLog `
    -RedirectStandardError $backendErrLog `
    -WindowStyle Hidden `
    -PassThru
  Set-Content -LiteralPath $backendPidFile -Value $backend.Id -Encoding ascii
} else {
  Write-Host "Backend: already running." -ForegroundColor Green
}

$backendPidText = ""
if (Test-Path -LiteralPath $backendPidFile) {
  $backendPidText = (Get-Content -Raw -LiteralPath $backendPidFile -ErrorAction SilentlyContinue).Trim()
}
$backendPid = if ($backendPidText) { [int]$backendPidText } else { 0 }
$backendReady = Wait-PortOpen -Port $backendPort -Seconds 45 -ProcessId $backendPid -LogPath $backendErrLog
if (-not $backendReady) {
  Show-ServiceLogs -Name "Backend" -StdoutPath $backendOutLog -StderrPath $backendErrLog
  Write-Host "Backend did not become healthy. The frontend will still be opened; Agent/API features need the backend." -ForegroundColor Yellow
} else {
  Write-Host "Backend: ready at $backendUrl" -ForegroundColor Green
}

$env:VITE_API_BASE_URL = $backendUrl

if (-not (Test-PortOpen -Port $frontendPort)) {
  Stop-PidFileProcess -PidFile $frontendPidFile
  Remove-Item -LiteralPath $frontendErrLog, $frontendOutLog -Force -ErrorAction SilentlyContinue
  Write-Step "Starting frontend static server..."
  Write-Host "Python : $pythonExe" -ForegroundColor DarkGray
  $frontend = Start-Process -FilePath $pythonExe `
    -ArgumentList @((Join-Path $PSScriptRoot "static_frontend_server.py"), "--host", "127.0.0.1", "--port", "$frontendPort", "--root", $frontendDist, "--backend-url", $backendUrl) `
    -WorkingDirectory $codeRoot `
    -RedirectStandardOutput $frontendOutLog `
    -RedirectStandardError $frontendErrLog `
    -WindowStyle Hidden `
    -PassThru
  Set-Content -LiteralPath $frontendPidFile -Value $frontend.Id -Encoding ascii
} else {
  Write-Host "Frontend: already running." -ForegroundColor Green
}

$frontendPidText = ""
if (Test-Path -LiteralPath $frontendPidFile) {
  $frontendPidText = (Get-Content -Raw -LiteralPath $frontendPidFile -ErrorAction SilentlyContinue).Trim()
}
$frontendPid = if ($frontendPidText) { [int]$frontendPidText } else { 0 }
if (-not (Wait-PortOpen -Port $frontendPort -Seconds 25 -ProcessId $frontendPid -LogPath $frontendErrLog)) {
  Show-ServiceLogs -Name "Frontend" -StdoutPath $frontendOutLog -StderrPath $frontendErrLog
  throw "Frontend did not start. Check code\runtime_logs\web-demo-frontend.err.log"
}

Write-Host "Frontend: ready at $frontendUrl" -ForegroundColor Green
Start-FactoryWorker
Open-DemoBrowser -Url "$frontendUrl/report"

Write-Host ""
Write-Host "Ready: $frontendUrl/report" -ForegroundColor Green
Write-Host "Stop: double-click Stop-Web-Demo.bat" -ForegroundColor Yellow
