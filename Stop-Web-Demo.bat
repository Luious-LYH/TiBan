@echo off
setlocal

set "SCRIPT=%~dp0scripts\Stop-Web-Demo.ps1"
set "POWERSHELL=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"

if not exist "%SCRIPT%" (
  echo Stop script not found:
  echo %SCRIPT%
  echo.
  pause
  exit /b 1
)

if not exist "%POWERSHELL%" (
  echo PowerShell is required to stop this platform.
  echo.
  pause
  exit /b 1
)

"%POWERSHELL%" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%"
echo.
pause
exit /b 0
