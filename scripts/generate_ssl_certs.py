"""
Generate self-signed SSL certificates for FleetWise local HTTPS testing on mobile devices.
Uses standard cryptography library to generate an X.509 certificate with Subject Alternative Names (SAN)
including localhost, 127.0.0.1, and all detected LAN IP addresses.
"""
import ipaddress
import os
import socket
from datetime import datetime, timedelta, timezone

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def get_all_lan_ips():
    ips = {"127.0.0.1"}
    try:
        _, _, host_ips = socket.gethostbyname_ex(socket.gethostname())
        for ip in host_ips:
            if not ip.startswith("169.254.") and not ip.startswith("127."):
                ips.add(ip)
    except Exception:
        pass
    return sorted(list(ips))


def generate_certs(cert_dir="certs", cert_name="cert.pem", key_name="key.pem"):
    os.makedirs(cert_dir, exist_ok=True)
    cert_path = os.path.join(cert_dir, cert_name)
    key_path = os.path.join(cert_dir, key_name)

    # 1. Generate private key
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )

    # 2. Build SAN entries
    san_entries = [
        x509.DNSName("localhost"),
        x509.DNSName("fleetwise.local"),
    ]
    for ip_str in get_all_lan_ips():
        try:
            san_entries.append(x509.IPAddress(ipaddress.ip_address(ip_str)))
        except ValueError:
            pass

    # 3. Create certificate
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "IN"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Karnataka"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "Bengaluru"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "FleetWise Development"),
        x509.NameAttribute(NameOID.COMMON_NAME, "FleetWise Local HTTPS Server"),
    ])

    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=365))
        .add_extension(
            x509.SubjectAlternativeName(san_entries),
            critical=False,
        )
        .add_extension(
            x509.BasicConstraints(ca=True, path_length=None),
            critical=True,
        )
        .sign(key, hashes.SHA256(), default_backend())
    )

    # 4. Write key and cert
    with open(key_path, "wb") as f:
        f.write(
            key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )

    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    print(f"SSL certificate generated successfully:")
    print(f"  Certificate: {cert_path}")
    print(f"  Private Key: {key_path}")
    print(f"  SAN IPs: {', '.join(get_all_lan_ips())}")
    return cert_path, key_path


def inspect_cert(cert_path="certs/cert.pem"):
    """
    Parses and verifies an existing X.509 certificate.
    Returns expiration, days remaining, and Subject Alternative Names.
    """
    if not os.path.exists(cert_path):
        return {"exists": False, "valid": False, "reason": "Certificate file not found"}

    try:
        with open(cert_path, "rb") as f:
            cert = x509.load_pem_x509_certificate(f.read(), default_backend())

        now = datetime.now(timezone.utc)
        not_after = cert.not_valid_after_utc if hasattr(cert, "not_valid_after_utc") else cert.not_valid_after.replace(tzinfo=timezone.utc)
        not_before = cert.not_valid_before_utc if hasattr(cert, "not_valid_before_utc") else cert.not_valid_before.replace(tzinfo=timezone.utc)

        days_remaining = (not_after - now).days
        is_expired = now > not_after or now < not_before

        # Extract SANs
        san_ips = []
        san_dns = []
        try:
            ext = cert.extensions.get_extension_for_oid(x509.ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
            for name in ext.value:
                if isinstance(name, x509.IPAddress):
                    san_ips.append(str(name.value))
                elif isinstance(name, x509.DNSName):
                    san_dns.append(name.value)
        except Exception:
            pass

        return {
            "exists": True,
            "valid": not is_expired and days_remaining > 0,
            "is_expired": is_expired,
            "days_remaining": days_remaining,
            "not_after": not_after.isoformat(),
            "not_before": not_before.isoformat(),
            "san_ips": san_ips,
            "san_dns": san_dns,
        }
    except Exception as e:
        return {"exists": True, "valid": False, "error": str(e)}


def ensure_valid_certs(cert_dir="certs", cert_name="cert.pem", key_name="key.pem"):
    """
    Validates existing certificate against expiration and active LAN IPs.
    Regenerates if expired, missing, or if any current LAN IP is missing from SANs.
    """
    cert_path = os.path.join(cert_dir, cert_name)
    key_path = os.path.join(cert_dir, key_name)

    inspection = inspect_cert(cert_path)
    current_lan_ips = set(get_all_lan_ips())

    needs_regen = False
    regen_reason = ""

    if not inspection.get("exists") or not os.path.exists(key_path):
        needs_regen = True
        regen_reason = "Certificate or private key file missing"
    elif not inspection.get("valid") or inspection.get("days_remaining", 0) < 7:
        needs_regen = True
        regen_reason = f"Certificate expired or expiring soon ({inspection.get('days_remaining')} days remaining)"
    else:
        san_ips_in_cert = set(inspection.get("san_ips", []))
        missing_ips = current_lan_ips - san_ips_in_cert
        if missing_ips:
            needs_regen = True
            regen_reason = f"Active LAN IP(s) changed/missing from certificate SAN: {missing_ips}"

    if needs_regen:
        print(f"[SSL Auto-Validation] Regenerating certificate. Reason: {regen_reason}")
        generate_certs(cert_dir=cert_dir, cert_name=cert_name, key_name=key_name)
        inspection = inspect_cert(cert_path)
        inspection["regenerated"] = True
        inspection["regeneration_reason"] = regen_reason
    else:
        inspection["regenerated"] = False

    return inspection


TRUST_INSTRUCTIONS = {
    "android": (
        "1. Transfer certs/cert.pem to device. "
        "2. Settings -> Security -> Encryption & credentials -> Install a certificate -> CA certificate. "
        "3. Select cert.pem and tap Install."
    ),
    "ios": (
        "1. AirDrop or download certs/cert.pem in Safari. "
        "2. Settings -> Profile Downloaded -> Install. "
        "3. Settings -> General -> About -> Certificate Trust Settings -> Enable Full Trust for FleetWise Root."
    ),
    "windows": "In an elevated PowerShell prompt: certutil -addstore -f 'Root' certs\\cert.pem",
    "disclaimer": (
        "A self-signed certificate is NOT automatically trusted. Bypassing a browser warning enables Secure Context "
        "in current session but does NOT register the certificate in system trust stores."
    ),
}


if __name__ == "__main__":
    res = ensure_valid_certs()
    print("Certificate Status:", res)


