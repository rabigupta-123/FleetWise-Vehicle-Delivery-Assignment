"""
FleetWise — Automated Tests for Authentication Security, Session Hardening,
Scrypt User Provisioning, Lockout Rate Limiting, and CSRF Protection (Section 1).
"""
import pytest
from fastapi.testclient import TestClient

from app.auth import (
    hash_password,
    verify_password,
    verify_session_token,
)
from app.db import init_db
from scripts.create_user import create_user, validate_password_strength


def test_password_strength_validation():
    # Weak/short passwords (< 12 chars) must be rejected
    with pytest.raises(ValueError, match="at least 12 characters"):
        validate_password_strength("Short1!")

    # Common passwords must be rejected
    with pytest.raises(ValueError, match="too common"):
        validate_password_strength("password12345")

    # Strong password passes
    validate_password_strength("ValidStrongFleetPassword2026!")


def test_user_creation_and_scrypt_verification(tmp_path):
    test_db = str(tmp_path / "user_test.db")
    init_db(test_db)

    # 1. Provision user with manual strong password
    u1 = create_user("ops_admin", "ops_lead", "SuperSecurePassword123!", db_path=test_db)
    assert u1["username"] == "ops_admin"
    assert u1["role"] == "ops_lead"
    assert u1["must_change_password"] is False

    # Verify password against scrypt hash
    assert verify_password("SuperSecurePassword123!", hash_password("SuperSecurePassword123!"))
    assert not verify_password("WrongPassword123!", hash_password("SuperSecurePassword123!"))

    # 2. Provision user with generated password
    u2 = create_user("auto_disp", "dispatcher", generate_pwd=True, db_path=test_db)
    assert len(u2["password"]) >= 24
    assert u2["must_change_password"] is True


def test_no_default_placeholder_credentials_work(client: TestClient, temp_db: str):
    # Attempt login with legacy placeholder passwords
    placeholders = [
        ("dispatcher", "dispatcher_placeholder_password"),
        ("fleet_manager", "fleet_manager_placeholder_password"),
        ("ops_lead", "ops_lead_placeholder_password"),
        ("admin", "admin"),
        ("root", "root"),
    ]
    for username, pwd in placeholders:
        res = client.post("/auth/login", json={"username": username, "password": pwd})
        assert res.status_code == 401
        assert res.json()["error"] == "UNAUTHORIZED"


def test_login_rate_limiting_lockout(client: TestClient, temp_db: str):
    # 5 failed login attempts trigger 429 lockout
    user = "rate_limit_target_user"
    for _ in range(5):
        r = client.post("/auth/login", json={"username": user, "password": "WrongPassword123!"})
        assert r.status_code == 401

    # 6th attempt must be blocked by rate limiter with 429
    r_locked = client.post("/auth/login", json={"username": user, "password": "WrongPassword123!"})
    assert r_locked.status_code == 429
    assert r_locked.json()["error"] == "RATE_LIMITED"


def test_logout_session_invalidation(client: TestClient, temp_db: str):
    # Log in as provisioned user
    login_res = client.post("/auth/login", json={"username": "dispatcher", "password": "DispatcherSecurePass123!"})
    assert login_res.status_code == 200
    token = login_res.json().get("token")
    assert token is not None

    # Verify session is currently valid
    assert verify_session_token(token) is not None

    # Log out
    logout_res = client.post("/auth/logout")
    assert logout_res.status_code == 200

    # Token must now be invalidated
    assert verify_session_token(token) is None


def test_csrf_origin_protection(client: TestClient, temp_db: str, monkeypatch):
    monkeypatch.setenv("REQUIRE_AUTH", "1")
    # Log in to get session cookie
    login_res = client.post("/auth/login", json={"username": "ops_lead", "password": "OpsLeadSecurePass123!"})
    assert login_res.status_code == 200

    # Cross-site attack simulation: POST with evil origin header
    evil_headers = {"Origin": "https://malicious-attacker-site.com", "Host": "127.0.0.1:8000"}
    res_attack = client.post("/vehicles", json={"vehicle_id": "V-CSRF-1", "registration_no": "KA-99-CSRF", "type": "Van", "capacity": 1000}, headers=evil_headers)
    assert res_attack.status_code == 403
    assert res_attack.json()["error"] == "CSRF_FAILED"

    # Legitimate origin passes
    good_headers = {"Origin": "http://127.0.0.1:8000", "Host": "127.0.0.1:8000"}
    res_good = client.post("/vehicles", json={"vehicle_id": "V-CSRF-1", "registration_no": "KA-99-CSRF", "type": "Van", "capacity": 1000}, headers=good_headers)
    assert res_good.status_code == 201


def test_docs_disabled_by_default(client: TestClient, monkeypatch):
    monkeypatch.delenv("FLEETWISE_ENABLE_DOCS", raising=False)
    # Docs routes return 404
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert client.get("/openapi.json").status_code == 404
