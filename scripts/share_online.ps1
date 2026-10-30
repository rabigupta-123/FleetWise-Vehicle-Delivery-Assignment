Write-Host "==============================================================" -ForegroundColor Cyan
Write-Host "FleetWise — Secure Public Web Access (HTTPS Tunnel)" -ForegroundColor Yellow
Write-Host "==============================================================" -ForegroundColor Cyan
Write-Host "Forwarding local port 8000 via secure TLS tunnel..." -ForegroundColor White
Write-Host "Security: Strict RBAC enforced. Press Ctrl+C at any time for safe shutdown." -ForegroundColor Gray
Write-Host "==============================================================" -ForegroundColor Cyan
npx --yes localtunnel --port 8000


