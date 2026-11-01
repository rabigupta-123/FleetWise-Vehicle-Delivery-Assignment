"""
FleetWise — Smartphone Connectivity Diagnostic Doctor.
Performs comprehensive multi-point health checks for mobile telematics ingestion:
1. Enumerates network adapters and detects primary physical LAN IPv4.
2. Checks Wi-Fi connection profile category (Private vs Public).
3. Verifies ports 8000 and 8443 listener status and address bindings.
4. Checks Windows Defender Firewall inbound rules for port 8443.
5. Tests local TCP handshake on <chosen IP>:8443.
6. Verifies TLS certificate Subject Alternative Names (SANs) include chosen IP.
7. Tests public /ping endpoint reachability on port 8443.
8. Prints exact phone pairing instructions, firewall remediation, and diagnostic checklist.
"""
import json
import os
import re
import socket
import ssl
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.run_dual_server import detect_primary_lan_ip, get_all_lan_candidates


def run_powershell(cmd: str) -> tuple[int, str]:
    """Runs a powershell command and returns (code, stdout)."""
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
            capture_output=True,
            text=True,
            timeout=8,
        )
        return proc.returncode, proc.stdout.strip()
    except Exception as e:
        return 1, str(e)


def check_wifi_profile() -> tuple[str, str, str]:
    """Inspects active connection profile category (Private, Public, Domain)."""
    code, out = run_powershell("Get-NetConnectionProfile | Select-Object -First 1 | Format-List Name, InterfaceAlias, NetworkCategory")
    if code != 0 or not out:
        return "UNKNOWN", "Could not query network profile.", "WARN"

    cat_match = re.search(r"NetworkCategory\s*:\s*(\w+)", out)
    category = cat_match.group(1) if cat_match else "Unknown"

    if category.lower() == "public":
        return category, "Wi-Fi is categorized as 'Public'. Windows Firewall silently drops incoming connections on Public networks.", "FAIL"
    elif category.lower() in ("private", "domainauthenticated"):
        return category, f"Wi-Fi profile is '{category}' (inbound traffic permitted with firewall rule).", "PASS"
    return category, f"Wi-Fi profile is '{category}'.", "WARN"


def check_listening_ports() -> dict[str, dict]:
    """Checks whether ports 8000 and 8443 are listening and on which addresses."""
    code, out = run_powershell("Get-NetTCPConnection -LocalPort 8000, 8443 -State Listen -ErrorAction SilentlyContinue | Select-Object LocalAddress, LocalPort, OwningProcess | ConvertTo-Json")
    results = {
        "8000": {"listening": False, "address": None, "pid": None},
        "8443": {"listening": False, "address": None, "pid": None},
    }
    if code == 0 and out:
        try:
            data = json.loads(out)
            if isinstance(data, dict):
                data = [data]
            for item in data:
                p = str(item.get("LocalPort"))
                if p in results:
                    results[p]["listening"] = True
                    results[p]["address"] = item.get("LocalAddress")
                    results[p]["pid"] = item.get("OwningProcess")
        except Exception:
            pass
    return results


def check_firewall_rule() -> tuple[bool, str]:
    """Checks if an inbound firewall rule exists for port 8443."""
    code, out = run_powershell("Get-NetFirewallPortFilter | Where-Object { $_.LocalPort -contains '8443' }")
    if code == 0 and out and "8443" in out:
        return True, "Inbound firewall rule allowing port 8443 is ACTIVE."
    return False, "No active inbound firewall rule found for port 8443."


def check_tls_sans(ip: str) -> tuple[bool, list[str]]:
    """Inspects certs/cert.pem to verify SANs include the selected LAN IP."""
    cert_path = ROOT_DIR / "certs" / "cert.pem"
    if not cert_path.exists():
        return False, []

    try:
        from cryptography import x509
        from cryptography.x509.oid import ExtensionOID
        cert_data = cert_path.read_bytes()
        cert = x509.load_pem_x509_certificate(cert_data)
        san_ext = cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
        san_val = san_ext.value
        if isinstance(san_val, x509.SubjectAlternativeName):
            sans = [str(x.value) for x in san_val]
        else:
            sans = []
        has_ip = ip in sans
        return has_ip, sans
    except Exception:
        return False, []


def test_socket_connection(ip: str, port: int) -> bool:
    """Tests raw TCP connection to IP:port."""
    try:
        with socket.create_connection((ip, port), timeout=2.0):
            return True
    except Exception:
        return False


def test_ping_endpoint(ip: str) -> tuple[bool, str]:
    """Tests https://<ip>:8443/ping."""
    try:
        import urllib.request
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        url = f"https://{ip}:8443/ping"
        req = urllib.request.Request(url, headers={"User-Agent": "FleetWise-Doctor"})
        with urllib.request.urlopen(req, timeout=3.0, context=ctx) as resp:
            body = resp.read().decode().strip()
            if resp.status == 200 and body == "ok":
                return True, "HTTP 200 OK (returned 'ok')"
            return False, f"HTTP {resp.status} (body: '{body[:30]}')"
    except Exception as e:
        return False, str(e)


def main():
    print("=" * 80)
    print(" FLEETWISE SMARTPHONE CONNECTIVITY DOCTOR")
    print("=" * 80)

    # 1. Network Adapter & IP Selection
    candidates = get_all_lan_candidates()
    chosen_ip = detect_primary_lan_ip()
    print(f"\n[1] Network Adapter & IP Selection:")
    print(f"    Available LAN Candidates: {', '.join(candidates) if candidates else 'None'}")
    print(f"    Selected Physical LAN IP: {chosen_ip}")
    is_valid_lan = chosen_ip not in ("127.0.0.1", "0.0.0.0", "localhost") and not chosen_ip.startswith("169.254.")
    status_ip = "PASS" if is_valid_lan else "FAIL"
    print(f"    [{status_ip}] Physical adapter routing selected.")

    # 2. Wi-Fi Profile
    print(f"\n[2] Wi-Fi Connection Profile:")
    wifi_cat, wifi_msg, wifi_status = check_wifi_profile()
    print(f"    Category: {wifi_cat}")
    print(f"    [{wifi_status}] {wifi_msg}")

    # 3. Port Listeners
    print(f"\n[3] Port Listener Status:")
    listeners = check_listening_ports()
    p8000 = listeners["8000"]
    p8443 = listeners["8443"]

    p8000_status = "PASS" if p8000["listening"] else "FAIL"
    p8443_status = "PASS" if p8443["listening"] else "FAIL"

    print(f"    [{p8000_status}] Port 8000 (HTTP Desktop):  {'LISTENING on ' + str(p8000['address']) + ' (PID ' + str(p8000['pid']) + ')' if p8000['listening'] else 'NOT LISTENING (Run scripts/run_dual_server.py)'}")
    print(f"    [{p8443_status}] Port 8443 (HTTPS Mobile): {'LISTENING on ' + str(p8443['address']) + ' (PID ' + str(p8443['pid']) + ')' if p8443['listening'] else 'NOT LISTENING (Run scripts/run_dual_server.py)'}")

    # 4. Windows Firewall
    print(f"\n[4] Windows Defender Firewall:")
    fw_ok, fw_msg = check_firewall_rule()
    fw_status = "PASS" if fw_ok else "WARN"
    print(f"    [{fw_status}] {fw_msg}")
    print("    [!] Least-Privilege Firewall Command (Run once in an Elevated PowerShell terminal if phone cannot connect):")
    print("        New-NetFirewallRule -DisplayName 'FleetWise 8443' -Direction Inbound -LocalPort 8443 -Protocol TCP -Action Allow -Profile Private -RemoteAddress LocalSubnet")

    # 5. Local TCP Handshake
    print(f"\n[5] TCP Handshake on {chosen_ip}:8443:")
    tcp_ok = test_socket_connection(chosen_ip, 8443)
    tcp_status = "PASS" if tcp_ok else "FAIL"
    print(f"    [{tcp_status}] TCP SYN-ACK on {chosen_ip}:8443 -> {'SUCCESS' if tcp_ok else 'FAILED (check server and firewall)'}")

    # 6. TLS SANs
    print(f"\n[6] TLS Certificate SANs Verification:")
    san_ok, sans = check_tls_sans(chosen_ip)
    san_status = "PASS" if san_ok else "FAIL"
    print(f"    Certificate SANs: {sans}")
    print(f"    [{san_status}] Chosen IP {chosen_ip} is {'PRESENT' if san_ok else 'MISSING'} in TLS SANs.")

    # 7. Public /ping Endpoint
    print(f"\n[7] Phone Pre-flight Route Check (GET /ping):")
    ping_ok, ping_msg = test_ping_endpoint(chosen_ip)
    ping_status = "PASS" if ping_ok else "FAIL"
    print(f"    [{ping_status}] https://{chosen_ip}:8443/ping -> {ping_msg}")

    # 8. Instructions & Final URL
    print("\n" + "=" * 80)
    print(" SMARTPHONE ACCESS SUMMARY & REPAIR CHECKLIST")
    print("=" * 80)
    print(f" Phone Pre-Flight URL:  https://{chosen_ip}:8443/ping")
    print(f" Driver Portal Base:    https://{chosen_ip}:8443/driver?pair=<PAIRING_TOKEN>")
    print("-" * 80)
    print(" Common Phone Connection Pitfalls & Recommended Fixes:")
    print(" 1. Untrusted Certificate: Tap 'Advanced' -> 'Proceed' (Android) or 'Show Details' -> 'visit this website' (iOS).")
    print(" 2. Same Network: Ensure smartphone is on the exact same Wi-Fi SSID as laptop.")
    print(" 3. VPN / Private DNS: Temporarily disable iCloud Private Relay, VPNs, or Private DNS (e.g. NextDNS) on phone.")
    print(" 4. Guest / College Wi-Fi: AP Client Isolation blocks communication between Wi-Fi peers. Use phone hotspot as fallback.")
    print("=" * 80 + "\n")

    all_critical_pass = is_valid_lan and p8443["listening"] and san_ok
    return 0 if all_critical_pass else 1


if __name__ == "__main__":
    sys.exit(main())

