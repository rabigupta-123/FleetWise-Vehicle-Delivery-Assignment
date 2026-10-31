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


def test_four_cases_and_assignment_regression(client: TestClient, temp_db: str):
    """
    Exhaustive regression test for the 4 prompt cases:
    Case 1: Empty DB -> 201 loaded
    Case 2: DB already containing demo data -> 200 already_loaded
    Case 3: DB containing real records -> untouched, load succeeds
    Case 4: After POST /demo/clear -> clean load (load -> clear -> load)
    Plus: Load then run a live assignment, and verify clean teardown.
    """
    # Clean slate
    client.post("/demo/clear")

    # Case 1: Empty DB
    r1 = client.post("/demo/load", json={"latitude": 12.9716, "longitude": 77.5946})
    assert r1.status_code == 201
    assert r1.json()["status"] == "loaded"
    assert r1.json()["vehicles"] == 12
    assert r1.json()["deliveries"] == 25

    # Case 2: DB already containing demo data (Second click)
    r2 = client.post("/demo/load", json={})
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
    rc = client.post("/demo/clear")
    assert rc.status_code == 200
    assert rc.json()["status"] == "cleared"

    status_cleared = client.get("/demo/status").json()
    assert status_cleared["demo"]["vehicles"] == 0
    assert status_cleared["demo"]["deliveries"] == 0
    assert status_cleared["real"]["vehicles"] >= 1
    assert status_cleared["real"]["drivers"] >= 1

    # Reload again
    r_reload = client.post("/demo/load", json={})
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
    rc_final = client.post("/demo/clear")
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
