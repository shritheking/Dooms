<#
.SYNOPSIS
    1-Click Manual Booking-Page Verification Fallback for Windows Remote Desktop (RDP)
.DESCRIPTION
    Opens Microsoft Edge or default browser directly to the Ritzy Sha Cinemas BookMyShow venue page
    in an interactive desktop session, allowing instant visual inspection of showtimes.
#>

$Url = "https://in.bookmyshow.com/cinemas/madurai/ritzy-sha-cinemas-4k-rgb-laser-atmos-madurai/buytickets/RZYM"

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host " 🛡️ Opening Ritzy Sha Cinemas BookMyShow Page (RZYM)... " -ForegroundColor Green
Write-Host " Venue: Ritzy Sha Cinemas (RZYM), Madurai" -ForegroundColor White
Write-Host " URL: $Url" -ForegroundColor Yellow
Write-Host "=================================================================" -ForegroundColor Cyan

# Launch in default Windows browser (Edge/Chrome)
Start-Process "msedge.exe" -ArgumentList $Url -ErrorAction SilentlyContinue

if ($LASTEXITCODE -ne 0) {
    Start-Process $Url
}

Write-Host "Browser opened! Check if Avengers: Doomsday showtimes are available." -ForegroundColor Green
Write-Host "Use the Dashboard at http://localhost:8080 to click 'ONE-CLICK CONFIRM' and dispatch alert!" -ForegroundColor Cyan
