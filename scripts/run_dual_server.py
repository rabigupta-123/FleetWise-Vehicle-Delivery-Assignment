import asyncio
import os
import sys
import uvicorn

# Ensure repository root is in python path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from scripts.generate_ssl_certs import ensure_valid_certs


async def run_dual_servers():
    print("=" * 70)
    print("FleetWise — Dual HTTP & HTTPS Server Launch")
    print("=" * 70)
    
    # 1. Ensure SAN certificates exist and match active LAN IPs
    print("1. Checking SSL Certificates for Local Wi-Fi SANs...")
    try:
        cert_status = ensure_valid_certs()
        print(f"   SSL Status: Valid={cert_status['valid']}, IPs={cert_status['san_ips']}")
    except Exception as e:
        print(f"   [Notice] SSL generation check: {e}")

    # 2. Configure HTTP (Port 8000)
    http_config = uvicorn.Config(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
        access_log=False,
    )
    http_server = uvicorn.Server(http_config)

    # 3. Configure HTTPS (Port 8443)
    has_certs = os.path.exists("certs/cert.pem") and os.path.exists("certs/key.pem")
    tasks = [http_server.serve()]

    if has_certs:
        https_config = uvicorn.Config(
            "app.main:app",
            host="0.0.0.0",
            port=8443,
            ssl_certfile="certs/cert.pem",
            ssl_keyfile="certs/key.pem",
            log_level="info",
            access_log=False,
        )
        https_server = uvicorn.Server(https_config)
        tasks.append(https_server.serve())
        print("2. Binding Dual Listeners:")
        print("   -> HTTP  on http://0.0.0.0:8000 (Standard Local/Desktop Access)")
        print("   -> HTTPS on https://0.0.0.0:8443 (Mobile GPS & Secure Context)")
    else:
        print("2. Binding HTTP on http://0.0.0.0:8000 (SSL certs not found)")

    print("=" * 70)
    print("Ready. Access from your smartphone via HTTPS port 8443 for real GPS.")
    print("=" * 70)

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    try:
        asyncio.run(run_dual_servers())
    except KeyboardInterrupt:
        print("\n[FleetWise] Server stopped by user.")
