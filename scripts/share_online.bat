@echo off
echo ==============================================================
echo FleetWise — Instant Public Web Access (HTTPS Tunnel)
echo ==============================================================
echo Exposing local port 8000 to the public internet...
echo Share the generated URL with anyone on mobile or remote devices.
echo Note: When opening for the first time, localtunnel may ask for
echo your public IP (friendly anti-phishing protection).
echo ==============================================================
npx --yes localtunnel --port 8000
pause

