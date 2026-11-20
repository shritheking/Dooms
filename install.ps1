<#
.SYNOPSIS
    One-Click Setup and Auto-Startup Script for Windows Oracle Cloud VPS
#>

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host " 🛡️ Setting up Avengers: Doomsday Booking Alert Bot (Windows VPS) " -ForegroundColor Green
Write-Host "==================================================================" -ForegroundColor Cyan

# 1. Check or install uv & Python 3.12
$UvBin = "$env:LOCALAPPDATA\Programs\uv\uv.exe"
if (-not (Test-Path $UvBin)) {
    Write-Host "[1/5] Installing astral uv portable package manager..." -ForegroundColor Yellow
    $UvZip = "$env:TEMP\uv.zip"
    curl.exe -sSL "https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip" -o $UvZip
    Expand-Archive -Path $UvZip -DestinationPath "$env:LOCALAPPDATA\Programs\uv" -Force
    Remove-Item $UvZip -Force -ErrorAction SilentlyContinue
}

Write-Host "[2/5] Ensuring Python 3.12 runtime..." -ForegroundColor Yellow
& $UvBin python install 3.12

# 2. Create virtual environment
Write-Host "[3/5] Initializing Python virtual environment (.venv)..." -ForegroundColor Yellow
if (-not (Test-Path ".venv")) {
    & $UvBin venv .venv --python 3.12
}

# 3. Install Python dependencies
Write-Host "[4/5] Installing dependencies from requirements.txt..." -ForegroundColor Yellow
& $UvBin pip install -r requirements.txt

# 4. Install Playwright Chromium
Write-Host "[5/5] Installing Playwright Chromium browser binaries..." -ForegroundColor Yellow
.\.venv\Scripts\playwright.exe install chromium

# 5. Environment configuration verification
if (-not (Test-Path ".env")) {
    Write-Host "Creating .env from .env.example..." -ForegroundColor Gray
    Copy-Item ".env.example" ".env"
}

Write-Host ""
Write-Host "==================================================================" -ForegroundColor Green
Write-Host " ✅ Installation Completed Successfully!" -ForegroundColor Green
Write-Host "==================================================================" -ForegroundColor Green
Write-Host "To start the bot now, run:" -ForegroundColor White
Write-Host "   .\run_service.ps1" -ForegroundColor Cyan
Write-Host ""
Write-Host "To open the Glassmorphism Dashboard:" -ForegroundColor White
Write-Host "   http://localhost:8080" -ForegroundColor Cyan
Write-Host ""
Write-Host "To run test suite:" -ForegroundColor White
Write-Host "   .\.venv\Scripts\pytest.exe test_suite.py -v" -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Green
