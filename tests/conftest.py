import sys
from collections.abc import Generator
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.db import get_connection, init_db
from app.main import app

# Starlette 1.2.1 attempts `import httpx2 as httpx` before falling back to `httpx`.
# Providing the installed `httpx` module under `httpx2` resolves the import at its source.
sys.modules.setdefault("httpx2", httpx)


def snapshot_db(db_path: str) -> dict[str, list[dict[str, Any]]]:
    """Capture a deterministic snapshot of all core tables to verify zero partial mutations on conflict."""
    conn = get_connection(db_path)
    try:
        vehicles = [
            dict(r)
            for r in conn.execute(
                "SELECT vehicle_id, registration_no, type, capacity, status FROM vehicles ORDER BY vehicle_id"
            ).fetchall()
        ]
        drivers = [
            dict(r)
            for r in conn.execute(
                "SELECT driver_id, name, phone, availability_status FROM drivers ORDER BY driver_id"
            ).fetchall()
        ]
        deliveries = [
            dict(r)
            for r in conn.execute(
                "SELECT delivery_id, pickup, dropoff, scheduled_time, priority, required_capacity, status, created_at, version FROM deliveries ORDER BY delivery_id"
            ).fetchall()
        ]
        assignments = [
            dict(r)
            for r in conn.execute(
                "SELECT assignment_id, delivery_id, vehicle_id, driver_id, assigned_at, released_at, release_reason FROM assignments ORDER BY assignment_id"
            ).fetchall()
        ]
        audit_log = [
            dict(r)
            for r in conn.execute(
                "SELECT id, ts, actor, action, entity, entity_id, before_json, after_json FROM audit_log ORDER BY id"
            ).fetchall()
        ]
        return {
            "vehicles": vehicles,
            "drivers": drivers,
            "deliveries": deliveries,
            "assignments": assignments,
            "audit_log": audit_log,
        }
    finally:
        conn.close()


@pytest.fixture()
def temp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    from app.auth import reset_pairing_rate_limits
    reset_pairing_rate_limits()
    db_file = str(tmp_path / "test_fleetwise.db")
    monkeypatch.setenv("DATABASE_PATH", db_file)
    monkeypatch.setenv("FLEETWISE_INSECURE_DEV", "1")
    init_db(db_file)
    return db_file


@pytest.fixture()
def client(temp_db: str) -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c

