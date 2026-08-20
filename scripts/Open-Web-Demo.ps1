$ErrorActionPreference = "SilentlyContinue"

function Test-PortOpen {
  param([int]$Port)
  $client = New-Object System.Net.Sockets.TcpClient
  try {
    $async = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
    if (-not $async.AsyncWaitHandle.WaitOne(500, $false)) {
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

$url = "http://127.0.0.1:5174/report"
$deadline = (Get-Date).AddSeconds(45)

while ((Get-Date) -lt $deadline) {
  if (Test-PortOpen -Port 5174) {
    break
  }
  Start-Sleep -Milliseconds 700
}

$opener = Join-Path $env:SystemRoot "System32\rundll32.exe"
if (Test-Path -LiteralPath $opener) {
  Start-Process -FilePath $opener -ArgumentList @("url.dll,FileProtocolHandler", $url) -WindowStyle Hidden
} else {
  Start-Process $url
}
