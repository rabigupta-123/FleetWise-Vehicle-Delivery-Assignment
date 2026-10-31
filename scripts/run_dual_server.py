"""
FleetWise — Dual HTTP & HTTPS Server Launch Script.
Binds HTTP (8000) for local desktop access and HTTPS (8443) with auto-generated SAN certificates
for real-time smartphone GPS telematics ingestion in secure contexts.

Supports:
  --share : Opens dashboard access to LAN (with persistent UI warning banner).
  --ip    : Operator override of primary LAN IPv4 address.
"""
import argparse
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
from app.auth import generate_pairing_token
from scripts.generate_ssl_certs import ensure_valid_certs


def get_all_lan_candidates() -> list[str]:
    """Enumerates candidate IPv4 addresses excluding loopback and link-local."""
    candidates = []
    try:
        hostname = socket.gethostname()
        _, _, host_ips = socket.gethostbyname_ex(hostname)
        for ip in host_ips:
            if ip.startswith("127.") or ip.startswith("169.254."):
                continue
            candidates.append(ip)
    except Exception:
        pass
    return candidates


def detect_primary_lan_ip(override_ip: str | None = None) -> str:
    """
    Selects primary LAN IP, preferring default gateway route and excluding
    known virtual adapters (WSL, Hyper-V, VirtualBox, VMware).
    """
    if override_ip:
        return override_ip

    # 1. Prefer default gateway interface via UDP socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            def_ip = s.getsockname()[0]
            if not def_ip.startswith("127.") and not def_ip.startswith("169.254."):
                return def_ip
    except Exception:
        pass

    # 2. Filter candidates
    candidates = get_all_lan_candidates()
    # Filter known host-only virtual adapter ranges (e.g. 172.18.x, 192.168.84.x, 192.168.152.x)
    physical_candidates = [
        ip for ip in candidates
        if not ip.startswith("172.18.") and not ip.startswith("192.168.84.") and not ip.startswith("192.168.152.")
    ]
    if physical_candidates:
        return physical_candidates[0]

    return candidates[0] if candidates else "127.0.0.1"


def print_qr_code(url: str) -> None:
    """Renders QR code in terminal using safe ASCII characters."""
    try:
        import qrcode
        qr = qrcode.QRCode(border=1)
        qr.add_data(url)
        qr.make(fit=True)
        matrix = qr.get_matrix()
        print("\n Driver Phone Mobile Pairing QR Code:")
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            for row in matrix:
                print("  " + "".join("██" if col else "  " for col in row))
        except Exception:
            for row in matrix:
                print("  " + "".join("##" if col else "  " for col in row))
    except ImportError:
        print(f"\n [i] Open URL on Driver Phone: {url}")


def print_access_table(lan_ip: str, pairing_token: str, share_mode: bool) -> None:
    desktop_url = "http://127.0.0.1:8000"
    phone_driver_url = f"https://{lan_ip}:8443/driver?pair={pairing_token}"
    phone_probe_url = f"https://{lan_ip}:8443/probe"

    candidates = get_all_lan_candidates()

    print("\n" + "=" * 80)
    print(" FLEETWISE DUAL SERVER ACCESS DIRECTORY (HACKATHON ZERO-LOGIN)")
    print("=" * 80)
    print(f" Detected LAN Candidates: {', '.join(candidates) if candidates else 'None'}")
    print(f" Selected Physical LAN IP: {lan_ip}")
    print("-" * 80)
    print(f" {'Client / Device':<20} | {'URL / Endpoint':<45} | {'Protocol'}")
    print("-" * 80)
    print(f" {'Desktop Dashboard':<20} | {desktop_url:<45} | HTTP (Port 8000)")
    print(f" {'Driver Phone Portal':<20} | {phone_driver_url:<45} | HTTPS (Port 8443)")
    print(f" {'Phone GPS Probe':<20} | {phone_probe_url:<45} | HTTPS (Port 8443)")
    print("=" * 80)

    if share_mode:
        print("\n [!] DANGER: --share IS ACTIVE!")
        print("     WARNING: Anyone on this network can control FleetWise without authentication.")
        print("     Do not use this flag on public, campus, or untrusted Wi-Fi.")
    else:
        print("\n [i] Security: Loopback isolation is ACTIVE.")
        print("     Desktop dashboard and control APIs are strictly locked to loopback clients (127.0.0.1 / ::1).")
        print("     Mobile phones can ONLY access /driver, /probe, and /tracking with their pairing token.")

    print("\n [i] Notice for Windows Firewall (if mobile device cannot connect over Wi-Fi):")
    print("     Run in an elevated PowerShell terminal to allow ports 8000 and 8443:")
    print("     New-NetFirewallRule -DisplayName 'FleetWise Server' -Direction Inbound -LocalPort 8000,8443 -Protocol TCP -Action Allow")
    print("-" * 80)

    print_qr_code(phone_driver_url)
    print("-" * 80 + "\n")


async def run_dual_servers(share_mode: bool = False, override_ip: str | None = None):
    if share_mode:
        os.environ["FLEETWISE_SHARE_LAN"] = "1"

    lan_ip = detect_primary_lan_ip(override_ip)
    pairing_token = generate_pairing_token(driver_id=None, valid_hours=48)

    # 1. Ensure SAN certificates exist and include selected LAN IP
    ensure_valid_certs()
    has_certs = os.path.exists("certs/cert.pem") and os.path.exists("certs/key.pem")

    print_access_table(lan_ip, pairing_token, share_mode)

    # 2. HTTP Server (Port 8000)
    # If share mode is on, bind 0.0.0.0; otherwise bind 127.0.0.1 for desktop dashboard
    http_bind = "0.0.0.0" if share_mode else "127.0.0.1"
    http_config = uvicorn.Config(
        "app.main:app",
        host=http_bind,
        port=8000,
        log_level="warning",
        access_log=False,
    )
    http_server = uvicorn.Server(http_config)
    tasks = [http_server.serve()]

    # 3. HTTPS Server (Port 8443) for Phone GPS telematics ingestion
    if has_certs:
        https_config = uvicorn.Config(
            "app.main:app",
            host="0.0.0.0",
            port=8443,
            ssl_certfile="certs/cert.pem",
            ssl_keyfile="certs/key.pem",
            log_level="warning",
            access_log=False,
        )
        https_server = uvicorn.Server(https_config)
        tasks.append(https_server.serve())

    await asyncio.gather(*tasks)


def main():
    parser = argparse.ArgumentParser(description="FleetWise Dual Server Launcher")
    parser.add_argument("--share", action="store_true", help="Open dashboard access to LAN clients (Insecure Hackathon Mode)")
    parser.add_argument("--ip", type=str, default=None, help="Explicitly specify primary LAN IPv4 address")
    args = parser.parse_args()

    try:
        asyncio.run(run_dual_servers(share_mode=args.share, override_ip=args.ip))
    except KeyboardInterrupt:
        print("\n[FleetWise] Server stopped cleanly.")


if __name__ == "__main__":
    main()
