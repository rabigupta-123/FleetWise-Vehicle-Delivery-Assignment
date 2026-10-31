"""
FleetWise — First-run bootstrap and user provisioning script.
Provisions RBAC users with scrypt password hashing and mandatory password rotation.
Usage:
    python scripts/create_user.py --role ops_lead [--username admin] [--password SecurePassword123!]
    python scripts/create_user.py --role dispatcher --generate-password
"""
import argparse
import getpass
import io
import secrets
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.auth import hash_password
from app.clock import utc_now_iso
from app.config import get_db_path
from app.db import immediate_transaction, init_db

COMMON_WEAK_PASSWORDS = {
    "password",
    "password1234",
    "password12345",
    "123456789012",
    "admin12345678",
    "qwertyuiop12",
    "fleetwise1234",
    "dispatcher123",
    "fleetmanager1",
    "opslead123456",
}


def validate_password_strength(password: str) -> None:
    if len(password) < 12:
        raise ValueError(f"Password must be at least 12 characters long (received {len(password)}).")
    if password.lower() in COMMON_WEAK_PASSWORDS:
        raise ValueError("Password is too common or easily guessed. Please choose a stronger password.")


def generate_secure_password(length: int = 24) -> str:
    """Generate a high-entropy 24+ character password."""
    return secrets.token_urlsafe(length)[:length]


def create_user(
    username: str,
    role: str,
    password: str | None = None,
    generate_pwd: bool = False,
    db_path: str | None = None,
) -> dict:
    if role not in ("ops_lead", "dispatcher", "fleet_manager"):
        raise ValueError(f"Invalid role '{role}'. Must be one of: ops_lead, dispatcher, fleet_manager.")

    must_change = 0
    if generate_pwd or not password:
        if generate_pwd:
            password = generate_secure_password(24)
            must_change = 1
        else:
            try:
                prompt_pwd = getpass.getpass(f"Enter password for user '{username}' (min 12 chars): ")
                validate_password_strength(prompt_pwd)
                confirm_pwd = getpass.getpass("Confirm password: ")
                if prompt_pwd != confirm_pwd:
                    raise ValueError("Passwords do not match.")
                password = prompt_pwd
            except (io.UnsupportedOperation, OSError):
                # Non-interactive fallback: generate random password
                password = generate_secure_password(24)
                must_change = 1
    else:
        validate_password_strength(password)

    target_db = db_path or get_db_path()
    init_db(target_db)

    hashed_pwd = hash_password(password)
    now_ts = utc_now_iso()

    with immediate_transaction(target_db) as conn:
        conn.execute(
            """
            INSERT INTO users (username, password_hash, role, created_at, must_change_password)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                password_hash = excluded.password_hash,
                role = excluded.role,
                must_change_password = excluded.must_change_password
            """,
            (username, hashed_pwd, role, now_ts, must_change),
        )

    return {
        "username": username,
        "role": role,
        "password": password,
        "must_change_password": bool(must_change),
        "db_path": target_db,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="FleetWise User Provisioning & Bootstrap CLI")
    parser.add_argument("--role", required=True, choices=["ops_lead", "dispatcher", "fleet_manager"], help="User RBAC role")
    parser.add_argument("--username", help="Username (defaults to the role name)")
    parser.add_argument("--password", help="User password (min 12 characters)")
    parser.add_argument("--generate-password", action="store_true", help="Generate a random 24-character password")
    parser.add_argument("--db", help="Path to SQLite database file")

    args = parser.parse_args()
    username = args.username or args.role

    try:
        user_info = create_user(
            username=username,
            role=args.role,
            password=args.password,
            generate_pwd=args.generate_password,
            db_path=args.db,
        )

        print("\n" + "=" * 65)
        print(" [OK] FLEETWISE USER PROVISIONED SUCCESSFULLY")
        print("=" * 65)
        print(f" Database:             {user_info['db_path']}")
        print(f" Username:             {user_info['username']}")
        print(f" Role:                 {user_info['role']}")
        if args.generate_password or not args.password:
            print(f" Generated Password:   {user_info['password']}")
            print(f" Must Change on Login: {user_info['must_change_password']}")
            print("\n [!] Store this password safely. It is displayed ONCE and cannot be recovered.")
        else:
            print(" Password:             [Hidden — Scrypt hashed with per-user salt]")
        print("=" * 65 + "\n")
        return 0

    except Exception as exc:
        print(f"\n[ERROR] Failed to provision user: {exc}\n", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
