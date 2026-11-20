<#
.SYNOPSIS
    Avengers: Doomsday Booking Alert Bot — Windows Background Runner & Watchdog
.DESCRIPTION
    Launches the application inside the virtual environment with continuous watchdog recovery.
#>

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$VenvPython = Join-Path $ScriptDir ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Host "[ERROR] Virtual environment python.exe not found at $VenvPython" -ForegroundColor Red
    Exit 1
}

$ErrorActionPreference = "Continue"

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host " 🛡️ Starting Avengers: Doomsday Booking Alert Bot Service " -ForegroundColor Green
Write-Host " Cinema: Ritzy Sha Cinemas (RITM), Madurai" -ForegroundColor White
Write-Host " Dashboard URL: http://localhost:8080" -ForegroundColor Yellow
Write-Host "=================================================================" -ForegroundColor Cyan

while ($true) {
    try {
        & $VenvPython "main.py"
        $ExitCode = $LASTEXITCODE
        Write-Host "Process exited ($ExitCode). Restarting in 10 seconds..." -ForegroundColor DarkYellow
        Start-Sleep -Seconds 10
    }
    catch {
        $ErrMsg = $_.Exception.Message
        Write-Host "[ERROR] Watchdog caught error: $ErrMsg" -ForegroundColor Red
        Start-Sleep -Seconds 10
    }
}
