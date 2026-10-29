Write-Host "==============================================================" -ForegroundColor Cyan
Write-Host "FleetWise — Instant Public Web Access (HTTPS Tunnel)" -ForegroundColor Yellow
Write-Host "==============================================================" -ForegroundColor Cyan
Write-Host "Exposing local port 8000 to the public internet..." -ForegroundColor White
Write-Host "Anyone with the generated URL will be able to access FleetWise." -ForegroundColor Green
Write-Host "==============================================================" -ForegroundColor Cyan
npx --yes localtunnel --port 8000

