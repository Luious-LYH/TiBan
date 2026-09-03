@echo off
setlocal

set "SCRIPT=%~dp0scripts\Start-Web-Demo.ps1"
set "BROWSER_SCRIPT=%~dp0scripts\Open-Web-Demo.ps1"
set "POWERSHELL=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"

if not exist "%SCRIPT%" (
  echo Startup script not found:
  echo %SCRIPT%
  echo.
  pause
  exit /b 1
)

if not exist "%POWERSHELL%" (
  echo PowerShell is required to start this platform.
  echo Please start scripts\Start-Web-Demo.ps1 manually if PowerShell is disabled.
  echo.
  pause
  exit /b 1
)

set "ARIS_BROWSER_DEFERRED=1"
start "TiBan Platform" "%POWERSHELL%" -NoLogo -NoProfile -NoExit -ExecutionPolicy Bypass -File "%SCRIPT%"
if exist "%BROWSER_SCRIPT%" (
  start "Open TiBan Platform" /min "%POWERSHELL%" -NoLogo -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "%BROWSER_SCRIPT%"
)
exit /b 0
