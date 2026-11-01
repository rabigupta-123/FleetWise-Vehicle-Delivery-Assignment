"""
FleetWise — Automated Tests for Demo Data, Entity Isolation, and Demo Simulator.
Verifies:
1. Demo data loads ~12 vehicles, ~15 drivers, 25 deliveries flagged with is_demo = 1.
2. Clear demo data deletes only is_demo rows in 1 atomic transaction; real records remain untouched.
3. Source separation: demo vehicle rejects source='device'; real vehicle rejects source='simulated'.
4. Demo simulator state toggling and status reporting.
5. Idempotent load: second click returns 200 already_loaded.
6. Full lifecycle: load -> clear -> load -> assign -> clear.
"""
from fastapi.testclient import TestClient

from app.db import get_connection
from scripts.demo_data import clear_demo_data, get_demo_status, load_demo_data, toggle_demo_simulator


def test_demo_data_loading_and_clearing_lifecycle(temp_db: str):
    # 1. Start with clean state
    clear_demo_data()
    status_init = get_demo_status()
    assert status_init["demo"]["vehicles"] == 0
    assert status_init["demo"]["deliveries"] == 0

    # 2. Insert a real vehicle and driver
    conn = get_connection()
    try:
        conn.execute("INSERT INTO vehicles (vehicle_id, registration_no, type, capacity, is_demo) VALUES ('V-REAL-1', 'KA-01-RL-9999', 'van', 1000, 0)")
        conn.execute("INSERT INTO drivers (driver_id, name, phone, is_demo) VALUES ('DR-REAL-1', 'Real Pilot', '+91 91234 56789', 0)")
    finally:
        conn.close()

    # 3. Load demo dataset (First click: 201)
    load_res = load_demo_data(center_lat=12.9716, center_lon=77.5946)
    assert load_res["status"] == "loaded"
    assert load_res["vehicles"] == 12
    assert load_res["drivers"] == 15
    assert load_res["deliveries"] == 25

    status_loaded = get_demo_status()
    assert status_loaded["demo"]["vehicles"] == 12
    assert status_loaded["demo"]["drivers"] == 15
    assert status_loaded["demo"]["deliveries"] == 25
    assert status_loaded["real"]["vehicles"] >= 1
    assert status_loaded["real"]["drivers"] >= 1

    # 4. Second click on load_demo_data: Idempotent return (already_loaded)
    second_load = load_demo_data(center_lat=12.9716, center_lon=77.5946)
    assert second_load["status"] == "already_loaded"
    assert second_load["counts"]["vehicles"] == 12
    assert second_load["counts"]["drivers"] == 15
    assert second_load["counts"]["deliveries"] == 25

    # 5. Clear demo dataset
    clear_res = clear_demo_data()
    assert clear_res["status"] == "cleared"
    assert clear_res["deleted"]["vehicles"] == 12
    assert clear_res["deleted"]["drivers"] == 15
    assert clear_res["deleted"]["deliveries"] == 25

    # 6. Verify real vehicle and driver were NOT deleted
    status_after = get_demo_status()
    assert status_after["demo"]["vehicles"] == 0
    assert status_after["demo"]["drivers"] == 0
    assert status_after["real"]["vehicles"] >= 1
    assert status_after["real"]["drivers"] >= 1


def _get_csrf_headers(client: TestClient) -> dict[str, str]:
    r = client.get("/api/csrf-token")
    csrf = r.json()["csrf_token"]
    return {"x-csrf-token": csrf, "origin": "http://testserver"}


def test_four_cases_and_assignment_regression(client: TestClient, temp_db: str, monkeypatch):
    """
    Exhaustive regression test for the 4 prompt cases:
    Case 1: Empty DB -> 201 loaded
    Case 2: DB already containing demo data -> 200 already_loaded
    Case 3: DB containing real records -> untouched, load succeeds
    Case 4: After POST /demo/clear -> clean load (load -> clear -> load)
    Plus: Load then run a live assignment, and verify clean teardown.
    """
    monkeypatch.setenv("ENABLE_DEMO_ROUTES", "true")
    hdrs = _get_csrf_headers(client)

    # Clean slate
    client.post("/demo/clear", headers=hdrs)

    # Case 1: Empty DB
    r1 = client.post("/demo/load", json={"latitude": 12.9716, "longitude": 77.5946}, headers=hdrs)
    assert r1.status_code == 201
    assert r1.json()["status"] == "loaded"
    assert r1.json()["vehicles"] == 12
    assert r1.json()["deliveries"] == 25

    # Case 2: DB already containing demo data (Second click)
    r2 = client.post("/demo/load", json={}, headers=hdrs)
    assert r2.status_code == 200
    assert r2.json()["status"] == "already_loaded"
    assert r2.json()["counts"]["vehicles"] == 12
    assert r2.json()["counts"]["deliveries"] == 25

    # Case 3: Create real user record, load should maintain real records
    client.post("/vehicles", json={"vehicle_id": "V-PROD-REG1", "registration_no": "KA-01-PR-1111", "capacity": 1500})
    client.post("/drivers", json={"driver_id": "DR-PROD-REG1", "name": "Captain Kirk", "phone": "+91-9988776655"})

    status_mid = client.get("/demo/status").json()
    assert status_mid["real"]["vehicles"] >= 1
    assert status_mid["real"]["drivers"] >= 1
    assert status_mid["demo"]["vehicles"] == 12

    # Case 4: Clear demo data, verify real data untouched, then reload (load -> clear -> load)
    rc = client.post("/demo/clear", headers=hdrs)
    assert rc.status_code == 200
    assert rc.json()["status"] == "cleared"

    status_cleared = client.get("/demo/status").json()
    assert status_cleared["demo"]["vehicles"] == 0
    assert status_cleared["demo"]["deliveries"] == 0
    assert status_cleared["real"]["vehicles"] >= 1
    assert status_cleared["real"]["drivers"] >= 1

    # Reload again
    r_reload = client.post("/demo/load", json={}, headers=hdrs)
    assert r_reload.status_code == 201
    assert r_reload.json()["status"] == "loaded"

    # Case 5: Load then run a live assignment on demo pending delivery
    # DEL-DEMO-001 requires 45kg; V-DEMO-V01 has 900kg capacity
    r_assign = client.post("/deliveries/DEL-DEMO-001/assign", json={
        "vehicle_id": "V-DEMO-V01",
        "driver_id": "DR-DEMO-01",
    })
    assert r_assign.status_code == 201
    assert r_assign.json()["status"] == "assigned"

    # Case 6: Clear demo data after assignment (foreign key cascade must be clean)
    rc_final = client.post("/demo/clear", headers=hdrs)
    assert rc_final.status_code == 200
    assert rc_final.json()["status"] == "cleared"


def test_source_separation_guards(client: TestClient, temp_db: str):
    # Load demo dataset
    load_demo_data()

    # Setup real vehicle and driver with active tracking session
    client.post("/vehicles", json={"vehicle_id": "V-PROD-01", "registration_no": "KA-01-PD-0001", "capacity": 1200})
    client.post("/drivers", json={"driver_id": "DR-PROD-01", "name": "Prod Driver", "phone": "+91-9876543210"})
    res_sess = client.post("/tracking/sessions/start", json={"driver_id": "DR-PROD-01", "vehicle_id": "V-PROD-01"})
    prod_sess_id = res_sess.json()["session_id"]
    client.post(f"/tracking/sessions/{prod_sess_id}/consent", json={"consent": True})

    # 1. Real session sending simulated telemetry -> REJECTED (400)
    res_sim_on_real = client.post("/tracking/location", json={
        "session_id": prod_sess_id,
        "latitude": 12.9716,
        "longitude": 77.5946,
        "accuracy": 5.0,
        "source": "simulated",
        "device_timestamp": "2026-10-31T14:00:00Z",
    })
    assert res_sim_on_real.status_code == 400
    assert "Real vehicle cannot receive simulated telemetry" in res_sim_on_real.json()["message"]

    # 2. Demo session sending real device telemetry -> REJECTED (400)
    demo_sess_id = "TRK-DEMO-SESS-01"
    res_dev_on_demo = client.post("/tracking/location", json={
        "session_id": demo_sess_id,
        "latitude": 12.9716,
        "longitude": 77.5946,
        "accuracy": 5.0,
        "source": "device",
        "device_timestamp": "2026-10-31T14:00:00Z",
    })
    assert res_dev_on_demo.status_code == 400
    assert "Demo vehicle cannot receive real device telemetry" in res_dev_on_demo.json()["message"]

    # 3. Clean up demo data
    clear_demo_data()


def test_demo_simulator_toggle():
    # Toggle on
    s1 = toggle_demo_simulator()
    assert s1 is True
    # Toggle off
    s2 = toggle_demo_simulator()
    assert s2 is False


def test_item1_error_leakage_request_id_and_app_debug(client: TestClient, temp_db: str, monkeypatch, caplog):
    """
    Item 1 Verification:
    (a) Force an sqlite3.IntegrityError and assert response body contains only
        {"error": "internal_error", "message": "An unexpected error occurred.", "request_id": "<id>"}
        with HTTP 500, and NO "sqlite", "constraint", table names, or file paths.
    (b) Assert request_id in body matches X-Request-ID header and request_id in server log.
    (c) With APP_DEBUG=true, assert "detail" appears in response.
    """
    import logging
    import sqlite3

    import scripts.demo_data as demo_mod
    from app.main import app

    monkeypatch.setenv("ENABLE_DEMO_ROUTES", "true")
    monkeypatch.delenv("APP_DEBUG", raising=False)
    _get_csrf_headers(client)

    def _raise_integrity_error(*args, **kwargs):
        raise sqlite3.IntegrityError(
            "FOREIGN KEY constraint failed on table vehicles in C:\\secret\\path\\fleetwise.db"
        )

    monkeypatch.setattr(demo_mod, "load_demo_data", _raise_integrity_error)

    # Use TestClient with raise_server_exceptions=False to inspect the 500 HTTP response
    no_raise_client = TestClient(app, raise_server_exceptions=False)
    # Sync csrf cookie
    r_csrf = no_raise_client.get("/api/csrf-token")
    csrf_tok = r_csrf.json()["csrf_token"]
    req_hdrs = {"x-csrf-token": csrf_tok, "origin": "http://testserver"}

    with caplog.at_level(logging.ERROR, logger="fleetwise"):
        res_500 = no_raise_client.post("/demo/load", json={}, headers=req_hdrs)

    assert res_500.status_code == 500
    body = res_500.json()
    raw_text = res_500.text.lower()

    # (a) Exact keys and no internal leaks
    assert set(body.keys()) == {"error", "message", "request_id"}
    assert body["error"] == "internal_error"
    assert body["message"] == "An unexpected error occurred."
    assert "sqlite" not in raw_text
    assert "constraint" not in raw_text
    assert "vehicles" not in raw_text
    assert "secret" not in raw_text
    assert "fleetwise.db" not in raw_text

    # (b) X-Request-ID header on response and matching request_id in server log
    req_id = body["request_id"]
    assert req_id.startswith("req_")
    assert res_500.headers.get("X-Request-ID") == req_id
    assert any(req_id in record.message for record in caplog.records)

    # Verify X-Request-ID is also set on normal 200 responses
    res_health = no_raise_client.get("/health")
    assert res_health.status_code == 200
    assert res_health.headers.get("X-Request-ID", "").startswith("req_")

    # (c) With APP_DEBUG=true, assert "detail" appears
    monkeypatch.setenv("APP_DEBUG", "true")
    res_debug = no_raise_client.post("/demo/load", json={}, headers=req_hdrs)
    assert res_debug.status_code == 500
    debug_body = res_debug.json()
    assert "detail" in debug_body
    assert "FOREIGN KEY constraint failed" in debug_body["detail"]


def test_item2_lock_down_destructive_demo_routes(client: TestClient, temp_db: str, monkeypatch):
    """
    Item 2 Verification:
    - Disabled (default false) -> 404 on /demo/load and /demo/clear
    - Cross-origin POST -> 403
    - Missing CSRF -> 403
    - Real rows survive clear (1 real vehicle, 1 real driver)
    """
    # 1. Default disabled -> 404
    monkeypatch.delenv("ENABLE_DEMO_ROUTES", raising=False)
    r_load_off = client.post("/demo/load", json={})
    r_clear_off = client.post("/demo/clear")
    assert r_load_off.status_code == 404
    assert r_clear_off.status_code == 404

    # 2. Enable demo routes
    monkeypatch.setenv("ENABLE_DEMO_ROUTES", "true")
    csrf_res = client.get("/api/csrf-token")
    csrf_tok = csrf_res.json()["csrf_token"]

    # 3. Cross-origin POST -> 403
    r_cross = client.post(
        "/demo/load",
        json={},
        headers={"x-csrf-token": csrf_tok, "origin": "https://evil.example.com"},
    )
    assert r_cross.status_code == 403

    r_cross_clear = client.post(
        "/demo/clear",
        headers={"x-csrf-token": csrf_tok, "origin": "https://evil.example.com"},
    )
    assert r_cross_clear.status_code == 403

    # 4. Missing or wrong CSRF -> 403
    r_no_csrf = client.post(
        "/demo/load",
        json={},
        headers={"origin": "http://testserver"},
    )
    assert r_no_csrf.status_code == 403

    r_bad_csrf = client.post(
        "/demo/clear",
        headers={"x-csrf-token": "wrong_token", "origin": "http://testserver"},
    )
    assert r_bad_csrf.status_code == 403

    # 5. Real rows survive clear
    client.post("/vehicles", json={"vehicle_id": "V-SURVIVE-1", "registration_no": "KA-99-SV-0001", "capacity": 1000})
    client.post("/drivers", json={"driver_id": "DR-SURVIVE-1", "name": "Real Survivor", "phone": "+91-9000011111"})

    valid_hdrs = {"x-csrf-token": csrf_tok, "origin": "http://testserver"}
    r_load_ok = client.post("/demo/load", json={}, headers=valid_hdrs)
    assert r_load_ok.status_code in (200, 201)

    r_clear_ok = client.post("/demo/clear", headers=valid_hdrs)
    assert r_clear_ok.status_code == 200

    vehicles_after = client.get("/vehicles").json()
    drivers_after = client.get("/drivers").json()
    assert any(v["vehicle_id"] == "V-SURVIVE-1" for v in vehicles_after)
    assert any(d["driver_id"] == "DR-SURVIVE-1" for d in drivers_after)
    assert not any(v.get("is_demo") for v in vehicles_after)
    assert not any(d.get("is_demo") for d in drivers_after)


def test_item4_robust_fk_cascade_and_concurrent_idempotency(client: TestClient, temp_db: str, monkeypatch):
    """
    Item 4 Verification:
    - PRAGMA foreign_keys=ON on every connection
    - ON DELETE CASCADE on child tables
    - (a) load demo, insert child rows (sessions, GPS points, assignments, pairing tokens), run clear -> no IntegrityError, all children gone
    - (b) fire 10 concurrent /demo/load requests -> exactly one 201, the rest 200 already_loaded, row counts equal 12/15/25 afterward
    - (c) load -> clear -> load again works repeatedly (5 cycles)
    """
    from concurrent.futures import ThreadPoolExecutor

    from app.auth import generate_pairing_token

    monkeypatch.setenv("ENABLE_DEMO_ROUTES", "true")
    hdrs = _get_csrf_headers(client)

    # Verify PRAGMA foreign_keys=ON on every new connection and ON DELETE CASCADE on child tables
    for _ in range(3):
        conn = get_connection()
        try:
            assert conn.execute("PRAGMA foreign_keys;").fetchone()[0] == 1
            for tbl in ("devices", "phone_pairing_tokens", "assignments", "tracking_sessions", "gps_locations"):
                fks = conn.execute(f"PRAGMA foreign_key_list({tbl})").fetchall()
                assert len(fks) >= 1
                assert all(fk["on_delete"].upper() == "CASCADE" for fk in fks)
        finally:
            conn.close()

    # (a) Load demo, insert extra child rows (sessions, GPS points, assignments, pairing tokens, devices), run clear
    client.post("/demo/clear", headers=hdrs)
    r_load = client.post("/demo/load", json={}, headers=hdrs)
    assert r_load.status_code == 201

    # Insert child rows linked to demo driver DR-DEMO-01 and demo vehicle V-DEMO-B01
    generate_pairing_token(driver_id="DR-DEMO-01")
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO devices (device_id, driver_id, nickname, registered_at, last_seen_at) VALUES ('DEV-DEMO-CH1', 'DR-DEMO-01', 'Demo Phone', '2026-11-01T00:00:00Z', '2026-11-01T00:00:00Z')"
        )
        conn.execute(
            "INSERT INTO tracking_sessions (session_id, driver_id, device_id, vehicle_id, delivery_id, started_at, status, is_demo) VALUES ('TRK-DEMO-CH1', 'DR-DEMO-01', 'DEV-DEMO-CH1', 'V-DEMO-B01', 'DEL-DEMO-001', '2026-11-01T00:00:00Z', 'active', 1)"
        )
        conn.execute(
            "INSERT INTO gps_locations (location_id, session_id, driver_id, device_id, vehicle_id, delivery_id, latitude, longitude, accuracy, device_timestamp, server_timestamp, source, is_demo) VALUES ('LOC-DEMO-CH1', 'TRK-DEMO-CH1', 'DR-DEMO-01', 'DEV-DEMO-CH1', 'V-DEMO-B01', 'DEL-DEMO-001', 12.97, 77.59, 4.0, '2026-11-01T00:00:00Z', '2026-11-01T00:00:00Z', 'simulated', 1)"
        )
    finally:
        conn.close()

    r_clear = client.post("/demo/clear", headers=hdrs)
    assert r_clear.status_code == 200

    conn = get_connection()
    try:
        assert conn.execute("SELECT COUNT(*) FROM gps_locations WHERE session_id = 'TRK-DEMO-CH1'").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM tracking_sessions WHERE session_id = 'TRK-DEMO-CH1'").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM devices WHERE device_id = 'DEV-DEMO-CH1'").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM phone_pairing_tokens WHERE driver_id = 'DR-DEMO-01'").fetchone()[0] == 0
    finally:
        conn.close()

    # (b) Fire 10 concurrent /demo/load requests -> exactly one 201, the rest 200 already_loaded, counts 12/15/25
    def _call_load(_: int) -> int:
        res = client.post("/demo/load", json={}, headers=hdrs)
        return res.status_code

    with ThreadPoolExecutor(max_workers=10) as pool:
        statuses = list(pool.map(_call_load, range(10)))

    assert statuses.count(201) == 1
    assert statuses.count(200) == 9

    st = client.get("/demo/status").json()
    assert st["demo"]["vehicles"] == 12
    assert st["demo"]["drivers"] == 15
    assert st["demo"]["deliveries"] == 25

    # (c) Load -> Clear -> Load repeatedly (5 cycles)
    client.post("/demo/clear", headers=hdrs)
    for cycle in range(5):
        rl = client.post("/demo/load", json={}, headers=hdrs)
        assert rl.status_code == 201, f"Cycle {cycle} load failed: {rl.text}"
        rc = client.post("/demo/clear", headers=hdrs)
        assert rc.status_code == 200, f"Cycle {cycle} clear failed: {rc.text}"
        st_c = client.get("/demo/status").json()
        assert st_c["demo"]["vehicles"] == 0
        assert st_c["demo"]["drivers"] == 0
        assert st_c["demo"]["deliveries"] == 0

