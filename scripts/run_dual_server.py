"""
FleetWise — Dual HTTP & HTTPS Server Launch Script.
Binds HTTP (8000) for local desktop access and HTTPS (8443) with auto-generated SAN certificates
for real-time smartphone GPS telematics ingestion in secure contexts.
"""
import asyncio
import os
import socket
import sys
from pathlib import Path

# Ensure repository root is in python path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import uvicorn
from app.auth import is_auth_enabled
from scripts.generate_ssl_certs import ensure_valid_certs


def get_primary_lan_ip() -> str:
    """Detects primary physical Wi-Fi/LAN IPv4 address, filtering out virtual and link-local adapters."""
    candidate_ips = []
    try:
        hostname = socket.gethostname()
        _, _, host_ips = socket.gethostbyname_ex(hostname)
        for ip in host_ips:
            if ip.startswith("127.") or ip.startswith("169.254."):
                continue
            # Filter standard private IPv4
            if ip.startswith("192.168.") or ip.startswith("10.") or (ip.startswith("172.") and 16 <= int(ip.split(".")[1]) <= 31):
                candidate_ips.append(ip)
            else:
                candidate_ips.append(ip)
    except Exception:
        pass

    # Fallback probe via UDP socket connection
    if not candidate_ips:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                sock_ip = s.getsockname()[0]
                if not sock_ip.startswith("127.") and not sock_ip.startswith("169.254."):
                    candidate_ips.append(sock_ip)
        except Exception:
            pass

    return candidate_ips[0] if candidate_ips else "127.0.0.1"


def print_access_table(lan_ip: str, auth_active: bool, host_bind: str) -> None:
    desktop_url = "http://127.0.0.1:8000"
    phone_url = f"https://{lan_ip}:8443" if lan_ip != "127.0.0.1" else "https://127.0.0.1:8443"
    probe_url = f"{phone_url}/probe"

    print("\n" + "=" * 75)
    print(" FLEETWISE DUAL SERVER ACCESS DIRECTORY")
    print("=" * 75)
    print(f" {'Client / Device':<20} | {'URL / Endpoint':<35} | {'Protocol'}")
    print("-" * 75)
    print(f" {'Desktop Browser':<20} | {desktop_url:<35} | HTTP (Port 8000)")
    print(f" {'Phone Dashboard':<20} | {phone_url:<35} | HTTPS (Port 8443)")
    print(f" {'Phone GPS Probe':<20} | {probe_url:<35} | HTTPS (Port 8443)")
    print("=" * 75)

    if not auth_active:
        print("\n [!] WARNING: FLEETWISE_INSECURE_DEV=1 is active!")
        print("     Server is strictly bound to 127.0.0.1. LAN & Phone access are disabled.")
        print("     To enable LAN access and mobile phone GPS streaming, enable authentication.")
    else:
        print(f"\n [i] Network Listeners bound to: {host_bind}")
        print(" [i] Notice for Windows Firewall (if mobile devices cannot connect):")
        print("     Run in an elevated PowerShell terminal to allow ports 8000 and 8443:")
        print("     New-NetFirewallRule -DisplayName 'FleetWise Server' -Direction Inbound -LocalPort 8000,8443 -Protocol TCP -Action Allow")

    print("-" * 75 + "\n")


async def run_dual_servers():
    auth_active = is_auth_enabled()
    lan_ip = get_primary_lan_ip()

    # Rule: In insecure dev mode, bind ONLY to loopback 127.0.0.1
    if not auth_active:
        host_bind = "127.0.0.1"
    else:
        host_bind = "0.0.0.0"

    # 1. Ensure SAN certificates exist and include detected LAN IPs
    ensure_valid_certs()
    has_certs = os.path.exists("certs/cert.pem") and os.path.exists("certs/key.pem")

    print_access_table(lan_ip, auth_active, host_bind)

    # 2. HTTP Server (Port 8000)
    http_config = uvicorn.Config(
        "app.main:app",
        host=host_bind,
        port=8000,
        log_level="warning",
        access_log=False,
    )
    http_server = uvicorn.Server(http_config)
    tasks = [http_server.serve()]

    # 3. HTTPS Server (Port 8443)
    if has_certs and auth_active:
        https_config = uvicorn.Config(
            "app.main:app",
            host=host_bind,
            port=8443,
            ssl_certfile="certs/cert.pem",
            ssl_keyfile="certs/key.pem",
            log_level="warning",
            access_log=False,
        )
        https_server = uvicorn.Server(https_config)
        tasks.append(https_server.serve())

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    try:
        asyncio.run(run_dual_servers())
    except KeyboardInterrupt:
        print("\n[FleetWise] Server stopped cleanly.")
