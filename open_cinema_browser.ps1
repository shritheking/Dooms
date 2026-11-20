<#
.SYNOPSIS
    1-Click Manual Booking-Page Verification Fallback for Windows Remote Desktop (RDP)
.DESCRIPTION
    Opens Microsoft Edge directly to the Ritzy Sha Cinemas BookMyShow venue page
    in an interactive desktop browser session, allowing visual inspection.
#>

$Url = "https://in.bookmyshow.com/madurai/cinemas/ritzy-sha-cinemas-4k-rgb-laser-atmos-madurai/RITM"

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host " 🛡️ Launching Interactive Booking Verification Browser... " -ForegroundColor Green
Write-Host " Venue: Ritzy Sha Cinemas (RITM), Madurai" -ForegroundColor White
Write-Host " URL: $Url" -ForegroundColor Yellow
Write-Host "=================================================================" -ForegroundColor Cyan

# Launch in default Windows browser (Edge/Chrome)
Start-Process "msedge.exe" -ArgumentList $Url -ErrorAction SilentlyContinue

if ($LASTEXITCODE -ne 0) {
    # Fallback to start URL
    Start-Process $Url
}

Write-Host "Browser opened! Verify if Avengers: Doomsday showtimes are bookable." -ForegroundColor Green
Write-Host "To record a confirmed live showtime, use the Dashboard at http://localhost:8080" -ForegroundColor Cyan
