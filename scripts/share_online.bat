@echo off
echo ==============================================================
echo FleetWise — Secure Public Web Access (HTTPS Tunnel)
echo ==============================================================
echo Forwarding local port 8000 via secure TLS tunnel...
echo Share the generated URL with anyone on mobile or remote devices.
echo.
echo SECURITY NOTICES:
echo 1. Public tunnel traffic terminates TLS at the edge and forwards to 8000.
echo 2. Authentication and RBAC are strictly enforced for write/admin actions.
echo 3. Database files, .env credentials and private keys are never exposed.
echo 4. Press Ctrl+C in this window at any time to immediately close the tunnel.
echo ==============================================================
npx --yes localtunnel --port 8000
pause


