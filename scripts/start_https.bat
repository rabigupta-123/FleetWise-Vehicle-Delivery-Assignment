
@echo off
echo ===================================================================
echo FleetWise — Launching Secure HTTPS Server for Mobile GPS Testing
echo ===================================================================
echo Verifying and auto-regenerating SSL certificate SANs for current LAN IPs...
python scripts\run_dual_server.py
pause

