<#
.SYNOPSIS
    Avengers: Doomsday Booking Alert Bot — Windows Background Runner & Watchdog
.DESCRIPTION
    Launches the application inside the virtual environment with continuous logging
    and automatic recovery if the process terminates.
#>

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$VenvPython = Join-Path $ScriptDir ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Host "[ERROR] Virtual environment python.exe not found at $VenvPython" -ForegroundColor Red
    Write-Host "Please run .\install.ps1 first to setup environment." -ForegroundColor Yellow
    Exit 1
}

$LogDir = Join-Path $ScriptDir "logs"
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

$DateStr = Get-Date -Format "yyyy-MM-dd"
$LogFile = Join-Path $LogDir "bot_$DateStr.log"

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host " 🛡️ Starting Avengers: Doomsday Booking Alert Bot Service " -ForegroundColor Green
Write-Host " Cinema: Ritzy Sha Cinemas (RITM), Madurai" -ForegroundColor White
Write-Host " Dashboard URL: http://localhost:8080" -ForegroundColor Yellow
Write-Host " Log File: $LogFile" -ForegroundColor Gray
Write-Host "=================================================================" -ForegroundColor Cyan

# Continuous execution loop with recovery
while ($true) {
    try {
        $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        Add-Content -Path $LogFile -Value "[$Timestamp] Starting Avengers Booking Bot process..."
        
        & $VenvPython "main.py" 2>&1 | Tee-Object -FilePath $LogFile -Append
        
        $ExitCode = $LASTEXITCODE
        $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        Add-Content -Path $LogFile -Value "[$Timestamp] Process exited with code $ExitCode. Restarting in 10 seconds..."
        Write-Host "Process exited ($ExitCode). Restarting in 10 seconds..." -ForegroundColor DarkYellow
        Start-Sleep -Seconds 10
    }
    catch {
        $ErrMsg = $_.Exception.Message
        Add-Content -Path $LogFile -Value "[ERROR] Watchdog caught error: $ErrMsg"
        Start-Sleep -Seconds 10
    }
}
