import hashlib
import hmac
import os
import secrets
import json
import base64
from typing import Optional
from fastapi import Request, Response
from app.errors import AppError

SESSION_COOKIE_NAME = "fleetwise_session"
SECRET_KEY = os.environ.get("SESSION_SECRET_KEY", "fleetwise_default_super_secret_session_key_32bytes").encode("utf-8")

# Default credentials for RBAC if users table is empty
DEFAULT_USERS = {
    "dispatcher": {"password": os.environ.get("DISPATCHER_PASSWORD", "dispatcher_placeholder_password"), "role": "dispatcher"},
    "fleet_manager": {"password": os.environ.get("FLEET_MANAGER_PASSWORD", "fleet_manager_placeholder_password"), "role": "fleet_manager"},
    "ops_lead": {"password": os.environ.get("OPS_LEAD_PASSWORD", "ops_lead_placeholder_password"), "role": "ops_lead"},
}


def hash_password(password: str, salt: Optional[str] = None) -> str:
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
    raw_json = json.dumps(data, separators=(",", ":")).encode("utf-8")
    b64_data = base64.urlsafe_b64encode(raw_json).decode("utf-8")
    sig = hmac.new(SECRET_KEY, b64_data.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{b64_data}.{sig}"


def verify_session_token(token: str) -> Optional[dict]:
    try:
        if not token or "." not in token:
            return None
        b64_data, sig = token.split(".", 1)
        expected_sig = hmac.new(SECRET_KEY, b64_data.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None
        raw_json = base64.urlsafe_b64decode(b64_data.encode("utf-8")).decode("utf-8")
        return json.loads(raw_json)
    except Exception:
        return None


def get_current_user(request: Request) -> Optional[dict]:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        # Also check Authorization: Bearer <token>
        auth_hdr = request.headers.get("Authorization", "")
        if auth_hdr.startswith("Bearer "):
            token = auth_hdr[7:].strip()
    return verify_session_token(token) if token else None


def set_session_cookie(response: Response, user_data: dict) -> None:
    token = sign_session_data(user_data)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="strict",
        secure=False,  # Set False so it functions in standard HTTP localhost/demo environments
        max_age=86400,
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=SESSION_COOKIE_NAME, httponly=True, samesite="strict")


# Permission Matrix
ROLE_PERMISSIONS = {
    "dispatcher": {"deliveries", "assign", "status", "advisor", "read"},
    "fleet_manager": {"vehicles", "drivers", "import", "read"},
    "ops_lead": {"read", "metrics", "audit", "race_lab", "deliveries", "vehicles", "drivers", "assign", "status", "import", "advisor"},
}


def check_permission(user: Optional[dict], required_perm: str, request: Optional[Request] = None) -> None:
    # If request originates from a public tunnel or FORCE_AUTH is active, authentication is strictly mandatory
    if request:
        host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
        is_tunnel = any(d in host.lower() for d in [".loca.lt", ".ngrok-free.app", ".trycloudflare.com"])
        force_auth = os.environ.get("FORCE_AUTH", "").lower() in ("1", "true", "yes")
        if (is_tunnel or force_auth) and user is None:
            raise AppError(401, "UNAUTHORIZED", "Authentication required for external network access. Please log in.")

    # If no auth is provided in local developer mode, default to allowing operator
    if user is None:
        if os.environ.get("FORCE_AUTH", "").lower() in ("1", "true", "yes"):
            raise AppError(401, "UNAUTHORIZED", "Authentication required.")
        return

    role = user.get("role", "operator")
    allowed = ROLE_PERMISSIONS.get(role, set())
    if required_perm not in allowed and "ops_lead" not in role:
        raise AppError(403, "FORBIDDEN", f"Role '{role}' is not authorized to access '{required_perm}'.")


