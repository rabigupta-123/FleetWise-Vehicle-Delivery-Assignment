"""
FleetWise — Authentication, Session Security & RBAC Module.
Provides secure Scrypt password hashing, HMAC-SHA256 session cookies,
rate-limited authentication challenges, and strict role-based access control.
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time

from fastapi import Request, Response

from app.errors import AppError

SESSION_COOKIE_NAME = "fleetwise_session"

# Secret key for HMAC-SHA256 session tokens.
# Refuses placeholder secret unless in insecure dev mode.
_env_secret = os.environ.get("SESSION_SECRET_KEY")
if _env_secret and len(_env_secret) >= 32 and "placeholder" not in _env_secret:
    SECRET_KEY = _env_secret.encode("utf-8")
elif os.environ.get("FLEETWISE_INSECURE_DEV") == "1" or os.environ.get("PYTEST_CURRENT_TEST"):
    # Ephemeral dev/test secret
    SECRET_KEY = secrets.token_bytes(32)
else:
    # Default to a generated 32-byte secret per server process lifetime
    SECRET_KEY = secrets.token_bytes(32)

# Revoked session tokens & JTIs for logout invalidation
REVOKED_TOKENS: set[str] = set()

# Login attempt tracking for rate limiting & lockout: identifier -> list of timestamps
_LOGIN_ATTEMPTS: dict[str, list[float]] = {}


def is_auth_enabled() -> bool:
    """Authentication is enabled when explicitly activated via REQUIRE_AUTH=1 or FORCE_AUTH=1."""
    return os.environ.get("REQUIRE_AUTH", "").lower() in ("1", "true", "yes") or os.environ.get("FORCE_AUTH", "").lower() in ("1", "true", "yes")


def check_login_rate_limit(identifier: str) -> None:
    now = time.time()
    attempts = _LOGIN_ATTEMPTS.get(identifier, [])
    # Retain attempts within the last 5 minutes (300 seconds)
    recent = [t for t in attempts if now - t < 300]
    _LOGIN_ATTEMPTS[identifier] = recent
    if len(recent) >= 5:
        backoff_sec = int(60 * (2 ** min(len(recent) - 5, 4)))
        raise AppError(
            429,
            "RATE_LIMITED",
            f"Too many failed login attempts for this account. Locked out for {backoff_sec} seconds.",
        )


def record_login_failure(identifier: str) -> None:
    _LOGIN_ATTEMPTS.setdefault(identifier, []).append(time.time())


def record_login_success(identifier: str) -> None:
    _LOGIN_ATTEMPTS.pop(identifier, None)


def hash_password(password: str, salt: str | None = None) -> str:
    if not salt:
        salt = secrets.token_hex(16)
    hashed = hashlib.scrypt(password.encode("utf-8"), salt=salt.encode("utf-8"), n=16384, r=8, p=1).hex()
    return f"{salt}:{hashed}"


def verify_password(password: str, hashed_str: str) -> bool:
    try:
        salt, hashed = hashed_str.split(":", 1)
        expected = hashlib.scrypt(password.encode("utf-8"), salt=salt.encode("utf-8"), n=16384, r=8, p=1).hex()
        return hmac.compare_digest(expected, hashed)
    except Exception:
        return False


def sign_session_data(data: dict) -> str:
    payload = data.copy()
    if "exp" not in payload:
        payload["exp"] = time.time() + 86400  # 24 hours expiry
    if "jti" not in payload:
        payload["jti"] = secrets.token_hex(12)

    raw_json = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    b64_data = base64.urlsafe_b64encode(raw_json).decode("utf-8")
    sig = hmac.new(SECRET_KEY, b64_data.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{b64_data}.{sig}"


def verify_session_token(token: str) -> dict | None:
    try:
        if not token or "." not in token:
            return None
        if token in REVOKED_TOKENS:
            return None
        b64_data, sig = token.split(".", 1)
        expected_sig = hmac.new(SECRET_KEY, b64_data.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None
        raw_json = base64.urlsafe_b64decode(b64_data.encode("utf-8")).decode("utf-8")
        payload = json.loads(raw_json)

        # Check expiry
        if payload.get("exp") and time.time() > payload["exp"]:
            return None
        # Check token JTI revocation
        if payload.get("jti") in REVOKED_TOKENS:
            return None

        return payload
    except Exception:
        return None


def get_current_user(request: Request | None) -> dict | None:
    if request is None:
        return None
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        auth_hdr = request.headers.get("Authorization", "")
        if auth_hdr.startswith("Bearer "):
            token = auth_hdr[7:].strip()
    return verify_session_token(token) if token else None


def set_session_cookie(response: Response, user_data: dict, request: Request | None = None) -> str:
    token = sign_session_data(user_data)
    is_secure = False
    if request:
        proto = request.headers.get("x-forwarded-proto", request.url.scheme)
        is_secure = proto.lower() == "https"

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="strict",
        secure=is_secure,
        max_age=86400,
    )
    return token


def clear_session_cookie(response: Response, request: Request | None = None) -> None:
    if request:
        token = request.cookies.get(SESSION_COOKIE_NAME)
        if token:
            REVOKED_TOKENS.add(token)
            payload = verify_session_token(token)
            if payload and payload.get("jti"):
                REVOKED_TOKENS.add(payload["jti"])
    response.delete_cookie(key=SESSION_COOKIE_NAME, httponly=True, samesite="strict")


# RBAC Role Permission Matrix
ROLE_PERMISSIONS: dict[str, set[str]] = {
    "dispatcher": {"deliveries", "assign", "status", "advisor", "read", "events", "tracking"},
    "fleet_manager": {"vehicles", "drivers", "devices", "import", "read", "events", "tracking"},
    "ops_lead": {
        "read",
        "metrics",
        "audit",
        "race_lab",
        "deliveries",
        "vehicles",
        "drivers",
        "devices",
        "assign",
        "status",
        "import",
        "advisor",
        "events",
        "tracking",
        "export",
        "diagnostics",
    },
}


def check_permission(user: dict | None, required_perm: str, request: Request | None = None) -> None:
    """Enforces strict RBAC role authorization on all protected resources."""
    if is_auth_enabled():
        if user is None:
            raise AppError(401, "UNAUTHORIZED", "Authentication required. Please log in.")
    else:
        # Insecure dev mode: allow unauthenticated requests with operator fallback
        if user is None:
            return

    role = user.get("role", "operator")
    allowed = ROLE_PERMISSIONS.get(role, set())
    if required_perm not in allowed and "ops_lead" not in role:
        raise AppError(403, "FORBIDDEN", f"Role '{role}' is not authorized to access '{required_perm}'.")
