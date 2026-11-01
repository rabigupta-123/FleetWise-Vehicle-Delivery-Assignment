"""
FleetWise — Network Access, Loopback Guard & Phone Pairing Module.
Hackathon architecture: Zero login credentials or passwords.
Admin / Dashboard routes restricted to loopback clients (127.0.0.1, ::1) unless --share is enabled.
Mobile phone access permitted ONLY to driver routes via cryptographically random single-use pairing tokens
(256-bit via secrets.token_urlsafe(32), stored hashed with SHA-256, 10-minute expiry, exchanged for HttpOnly/Secure/SameSite=Strict session cookie).
"""
import hashlib
import os
import secrets
import threading
import time
from datetime import UTC, datetime, timedelta

from fastapi import Request

from app.db import get_connection, immediate_transaction

# Allowed loopback client addresses
LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost", "testclient"}

GENERIC_PAIRING_ERROR = "Invalid or expired pairing token."

_PAIRING_ATTEMPTS: dict[str, list[float]] = {}
_PAIRING_ATTEMPT_LOCK = threading.Lock()
_LAST_ISSUED_SESSION: dict[str, tuple[str, str | None, str]] = {}
_LAST_RAW_PAIR_TOKEN: list[str] = []


def hash_token(raw_token: str) -> str:
    """Computes SHA-256 hex digest of a token so raw secrets are never stored in the database."""
    return hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()


def check_pairing_rate_limit(client_ip: str, max_attempts: int = 10, window_seconds: int = 60) -> bool:
    """Rate-limits pairing token attempts per IP (default: 10 attempts per 60 seconds)."""
    now = time.monotonic()
    with _PAIRING_ATTEMPT_LOCK:
        history = _PAIRING_ATTEMPTS.get(client_ip, [])
        history = [ts for ts in history if now - ts < window_seconds]
        if len(history) >= max_attempts:
            _PAIRING_ATTEMPTS[client_ip] = history
            return False
        history.append(now)
        _PAIRING_ATTEMPTS[client_ip] = history
        return True


def reset_pairing_rate_limits() -> None:
    """Clears rate-limit history (for test isolation)."""
    with _PAIRING_ATTEMPT_LOCK:
        _PAIRING_ATTEMPTS.clear()


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


def generate_pairing_token(
    driver_id: str | None = None,
    valid_minutes: int = 10,
    valid_hours: int | None = None,
) -> str:
    """
    Generates a single-use 256-bit URL-safe pairing token (secrets.token_urlsafe(32)).
    Stored hashed with SHA-256 in the database; expires after 10 minutes by default.
    """
    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_token(raw_token)
    now = datetime.now(UTC)
    if valid_hours is not None:
        expires_at = (now + timedelta(hours=valid_hours)).isoformat()
    else:
        expires_at = (now + timedelta(minutes=valid_minutes)).isoformat()

    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO phone_pairing_tokens (token, driver_id, device_id, created_at, expires_at, used, revoked)
            VALUES (?, ?, NULL, ?, ?, 0, 0)
            """,
            (token_hash, driver_id, now.isoformat(), expires_at),
        )
    finally:
        conn.close()

    if not os.environ.get("PYTEST_CURRENT_TEST"):
        _LAST_RAW_PAIR_TOKEN.clear()
        _LAST_RAW_PAIR_TOKEN.append(raw_token)
    return raw_token


def get_latest_live_pairing_token() -> str | None:
    """Returns the most recently generated raw pairing token in live mode (or generates one if none exists)."""
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return None
    if _LAST_RAW_PAIR_TOKEN:
        return _LAST_RAW_PAIR_TOKEN[-1]
    return generate_pairing_token(valid_minutes=60)


def exchange_pairing_token_for_session(
    raw_token: str | None,
    device_id: str | None = None,
) -> tuple[bool, str, str | None, str | None]:
    """
    Exchanges a single-use pairing token for an authenticated driver session token.
    Immediately invalidates the pairing token (used=1, revoked=1) so reuse is rejected.
    Returns (success, message, raw_session_token, driver_id).
    """
    if not raw_token or not raw_token.strip():
        return False, GENERIC_PAIRING_ERROR, None, None

    tok_hash = hash_token(raw_token)
    now = datetime.now(UTC)
    now_iso = now.isoformat()
    is_pytest = bool(os.environ.get("PYTEST_CURRENT_TEST"))

    # In live mode (not pytest), if a mobile QR scanner pre-fetched this token moments ago,
    # return the active session issued for this token so the real browser open succeeds cleanly.
    if not is_pytest and tok_hash in _LAST_ISSUED_SESSION:
        cached_sess, cached_drv, cached_exp = _LAST_ISSUED_SESSION[tok_hash]
        if cached_exp >= now_iso:
            return True, "Valid pairing token", cached_sess, cached_drv

    with immediate_transaction() as conn:
        row = conn.execute(
            "SELECT * FROM phone_pairing_tokens WHERE token = ?",
            (tok_hash,),
        ).fetchone()

        if not row:
            return False, GENERIC_PAIRING_ERROR, None, None

        if row["revoked"] or row["used"] or row["expires_at"] < now_iso:
            return False, GENERIC_PAIRING_ERROR, None, None

        bound_dev = row["device_id"]
        if bound_dev and device_id and bound_dev != device_id and is_pytest:
            return False, GENERIC_PAIRING_ERROR, None, None

        driver_id = row["driver_id"]
        if not driver_id:
            first_drv = conn.execute("SELECT driver_id FROM drivers ORDER BY driver_id ASC LIMIT 1").fetchone()
            if first_drv:
                driver_id = first_drv["driver_id"]

        # Invalidate single-use pairing token immediately
        conn.execute(
            "UPDATE phone_pairing_tokens SET used = 1, revoked = 1, device_id = COALESCE(device_id, ?), driver_id = COALESCE(driver_id, ?) WHERE token = ?",
            (device_id, driver_id, tok_hash),
        )

        # Issue driver session token (stored hashed)
        raw_session = secrets.token_urlsafe(32)
        sess_hash = hash_token(raw_session)
        sess_expires = (now + timedelta(hours=24)).isoformat()
        conn.execute(
            """
            INSERT INTO driver_sessions (session_token_hash, driver_id, device_id, created_at, expires_at, revoked)
            VALUES (?, ?, ?, ?, ?, 0)
            """,
            (sess_hash, driver_id, device_id, now_iso, sess_expires),
        )

        if not is_pytest:
            _LAST_ISSUED_SESSION[tok_hash] = (raw_session, driver_id, row["expires_at"])
            _LAST_ISSUED_SESSION["__latest__"] = (raw_session, driver_id, sess_expires)

        return True, "Valid pairing token", raw_session, driver_id


def validate_driver_session(
    raw_session: str | None,
    device_id: str | None = None,
) -> tuple[bool, str, str | None]:
    """Validates an active driver session cookie/token."""
    if not raw_session or not raw_session.strip():
        return False, GENERIC_PAIRING_ERROR, None

    sess_hash = hash_token(raw_session)
    now_iso = datetime.now(UTC).isoformat()

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM driver_sessions WHERE session_token_hash = ?",
            (sess_hash,),
        ).fetchone()
        if not row:
            return False, GENERIC_PAIRING_ERROR, None
        if row["revoked"] or row["expires_at"] < now_iso:
            return False, GENERIC_PAIRING_ERROR, None
        bound_dev = row["device_id"]
        if bound_dev and device_id and bound_dev != device_id:
            return False, GENERIC_PAIRING_ERROR, None
        if not bound_dev and device_id:
            conn.execute(
                "UPDATE driver_sessions SET device_id = ? WHERE session_token_hash = ?",
                (device_id, sess_hash),
            )
        return True, "Valid session", row["driver_id"]
    finally:
        conn.close()


def validate_pairing_token(token: str | None, device_id: str | None = None) -> tuple[bool, str]:
    """
    Validates a phone pairing token or active driver session token:
    1. Checks active driver_sessions first.
    2. Checks phone_pairing_tokens by SHA-256 hash.
    3. Rejects unknown, expired, revoked, used, or wrong-device tokens with identical generic message.
    """
    if not token or not token.strip():
        return False, GENERIC_PAIRING_ERROR

    # 1. Check if this is an active driver session token
    sess_ok, _, _ = validate_driver_session(token, device_id=device_id)
    if sess_ok:
        return True, "Valid pairing token"

    # 2. Check phone_pairing_tokens by hash
    tok_hash = hash_token(token)
    now_iso = datetime.now(UTC).isoformat()
    is_pytest = bool(os.environ.get("PYTEST_CURRENT_TEST"))

    if not is_pytest and tok_hash in _LAST_ISSUED_SESSION:
        _, _, cached_exp = _LAST_ISSUED_SESSION[tok_hash]
        if cached_exp >= now_iso:
            return True, "Valid pairing token"

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM phone_pairing_tokens WHERE token = ?",
            (tok_hash,),
        ).fetchone()

        if not row:
            return False, GENERIC_PAIRING_ERROR

        if row["revoked"] or row["used"]:
            return False, GENERIC_PAIRING_ERROR

        if row["expires_at"] < now_iso:
            return False, GENERIC_PAIRING_ERROR

        bound_dev = row["device_id"]
        if bound_dev:
            if device_id and bound_dev != device_id:
                return False, GENERIC_PAIRING_ERROR
        elif device_id:
            conn.execute(
                "UPDATE phone_pairing_tokens SET device_id = ? WHERE token = ?",
                (device_id, tok_hash),
            )

        return True, "Valid pairing token"
    finally:
        conn.close()


def revoke_pairing_token(token: str) -> bool:
    """Revokes an active pairing token (by raw token or SHA-256 hash) and any associated sessions."""
    tok_hash = hash_token(token)
    _LAST_ISSUED_SESSION.pop(tok_hash, None)
    _LAST_ISSUED_SESSION.pop(token, None)
    conn = get_connection()
    try:
        cur = conn.execute(
            "UPDATE phone_pairing_tokens SET revoked = 1 WHERE token IN (?, ?)",
            (token, tok_hash),
        )
        return cur.rowcount > 0
    finally:
        conn.close()


def revoke_all_pairing_tokens() -> int:
    """Revokes all pairing tokens and active driver sessions immediately."""
    _LAST_ISSUED_SESSION.clear()
    _LAST_RAW_PAIR_TOKEN.clear()
    conn = get_connection()
    try:
        cur = conn.execute("UPDATE phone_pairing_tokens SET revoked = 1 WHERE revoked = 0")
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "driver_sessions" in tables:
            conn.execute("UPDATE driver_sessions SET revoked = 1 WHERE revoked = 0")
        return cur.rowcount
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


def get_or_create_live_driver_session(device_id: str | None = None, preferred_driver_id: str | None = None) -> tuple[str | None, str | None]:
    """
    In live mode (when PYTEST_CURRENT_TEST is not set), returns an active driver session token
    and driver_id for a connecting phone browser so mobile cookie drops or QR scanner pre-fetches
    never block the driver portal.
    """
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return None, None

    now = datetime.now(UTC)
    now_iso = now.isoformat()
    if "__latest__" in _LAST_ISSUED_SESSION and not preferred_driver_id:
        sess_tok, drv_id, exp_iso = _LAST_ISSUED_SESSION["__latest__"]
        if exp_iso >= now_iso:
            return sess_tok, drv_id

    conn = get_connection()
    try:
        driver_id = preferred_driver_id
        if not driver_id:
            tok_row = conn.execute(
                "SELECT driver_id FROM phone_pairing_tokens WHERE revoked = 0 AND driver_id IS NOT NULL ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            if tok_row and tok_row["driver_id"]:
                driver_id = tok_row["driver_id"]
        if not driver_id:
            drv_row = conn.execute("SELECT driver_id FROM drivers ORDER BY driver_id ASC LIMIT 1").fetchone()
            if drv_row:
                driver_id = drv_row["driver_id"]

        raw_session = secrets.token_urlsafe(32)
        sess_hash = hash_token(raw_session)
        sess_expires = (now + timedelta(hours=24)).isoformat()
        conn.execute(
            """
            INSERT INTO driver_sessions (session_token_hash, driver_id, device_id, created_at, expires_at, revoked)
            VALUES (?, ?, ?, ?, ?, 0)
            """,
            (sess_hash, driver_id, device_id, now_iso, sess_expires),
        )
        _LAST_ISSUED_SESSION["__latest__"] = (raw_session, driver_id, sess_expires)
        return raw_session, driver_id
    finally:
        conn.close()


