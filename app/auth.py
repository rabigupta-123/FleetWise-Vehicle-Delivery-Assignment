"""
FleetWise — Network Access, Loopback Guard & Phone Pairing Module.
Hackathon architecture: Zero login credentials or passwords.
Admin / Dashboard routes restricted to loopback clients (127.0.0.1, ::1) unless --share is enabled.
Mobile phone access permitted ONLY to driver routes via cryptographically random pairing tokens (>= 128-bit).
"""
import os
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import Request

from app.db import get_connection

# Allowed loopback client addresses
LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost", "testclient"}


def is_share_lan_active() -> bool:
    """Returns True if the dashboard has been opened to LAN clients via --share."""
    return os.environ.get("FLEETWISE_SHARE_LAN") == "1"


def is_loopback_client(request: Request) -> bool:
    """
    Checks if client originates from loopback (127.0.0.1 / ::1).
    STRICTLY ignores X-Forwarded-For to prevent header spoofing from external networks.
    """
    if not request.client:
        return False
    host = request.client.host
    return host in LOOPBACK_HOSTS


def generate_pairing_token(driver_id: str | None = None, valid_hours: int = 24) -> str:
    """
    Generates a secure 192-bit URL-safe pairing token (>= 128 bits) for phone access.
    Single-device bound upon first telemetry transmission.
    """
    token = secrets.token_urlsafe(24)  # 192 bits of entropy
    now = datetime.now(UTC)
    expires_at = (now + timedelta(hours=valid_hours)).isoformat()

    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO phone_pairing_tokens (token, driver_id, device_id, created_at, expires_at, revoked)
            VALUES (?, ?, NULL, ?, ?, 0)
            """,
            (token, driver_id, now.isoformat(), expires_at),
        )
    finally:
        conn.close()

    return token


def validate_pairing_token(token: str | None, device_id: str | None = None) -> tuple[bool, str]:
    """
    Validates a phone pairing token:
    1. Must exist.
    2. Must not be revoked.
    3. Must not be expired.
    4. Must match bound device_id if previously bound; binds device_id if unbound.
    Returns (is_valid, reason).
    """
    if not token or not token.strip():
        return False, "Missing pairing token"

    token = token.strip()
    now_iso = datetime.now(UTC).isoformat()

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM phone_pairing_tokens WHERE token = ?",
            (token,),
        ).fetchone()

        if not row:
            return False, "Invalid pairing token"

        if row["revoked"]:
            return False, "Pairing token has been revoked"

        if row["expires_at"] < now_iso:
            return False, "Pairing token has expired"

        bound_dev = row["device_id"]
        if bound_dev:
            if device_id and bound_dev != device_id:
                return False, f"Token bound to device '{bound_dev}'; cannot be used by '{device_id}'"
        elif device_id:
            # Bind token to first device that connects
            conn.execute(
                "UPDATE phone_pairing_tokens SET device_id = ? WHERE token = ?",
                (device_id, token),
            )

        return True, "Valid pairing token"
    finally:
        conn.close()


def revoke_pairing_token(token: str) -> bool:
    """Revokes an active pairing token."""
    conn = get_connection()
    try:
        cur = conn.execute(
            "UPDATE phone_pairing_tokens SET revoked = 1 WHERE token = ?",
            (token,),
        )
        return cur.rowcount > 0
    finally:
        conn.close()


# Compatibility helpers for existing handlers
def get_current_user(request: Request | None = None) -> dict | None:
    """In hackathon mode without login, returns self-declared operator metadata."""
    if request:
        op_name = request.headers.get("x-operator-name")
        if op_name:
            return {"username": op_name.strip(), "role": "ops_lead"}
    return {"username": "operator", "role": "ops_lead"}


def check_permission(user: dict | None, required_perm: str, request: Request | None = None) -> None:
    """No-op in open hackathon mode."""
    return None


def is_auth_enabled() -> bool:
    """Always False in hackathon mode (no login required)."""
    return False
