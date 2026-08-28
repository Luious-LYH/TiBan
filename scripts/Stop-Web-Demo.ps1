$ErrorActionPreference = "SilentlyContinue"

try {
  $Host.UI.RawUI.WindowTitle = "Stop Endoscopy Demo"
} catch {
}

$codeRoot = Split-Path -Parent $PSScriptRoot
$logsRoot = Join-Path $codeRoot "runtime_logs"
$ports = @(5173, 5174, 8002)
$pidFiles = @(
  Join-Path $logsRoot "web-demo-frontend.pid",
  Join-Path $logsRoot "web-demo-backend.pid",
  Join-Path $logsRoot "web-demo-factory-worker.pid"
)

foreach ($pidFile in $pidFiles) {
  if (-not (Test-Path -LiteralPath $pidFile)) {
    continue
  }
  $pidText = (Get-Content -Raw -LiteralPath $pidFile).Trim()
  if ($pidText) {
    try {
      Stop-Process -Id ([int]$pidText) -Force
    } catch {
    }
  }
  Remove-Item -LiteralPath $pidFile -Force
}

foreach ($port in $ports) {
  try {
    $connections = Get-NetTCPConnection -LocalAddress "127.0.0.1" -LocalPort $port -State Listen
    foreach ($connection in $connections) {
      try {
        $process = Get-Process -Id $connection.OwningProcess
        if ($process.ProcessName -in @("python", "python3", "node", "npm", "cmd")) {
          Stop-Process -Id $process.Id -Force
        }
      } catch {
      }
    }
  } catch {
  }
}

Write-Host "Demo processes stopped." -ForegroundColor Green
