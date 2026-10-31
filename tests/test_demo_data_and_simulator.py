"""
FleetWise — Automated Tests for Demo Data, Entity Isolation, and Demo Simulator.
Verifies:
1. Demo data loads ~12 vehicles, ~15 drivers, 25 deliveries flagged with is_demo = 1.
2. Clear demo data deletes only is_demo rows in 1 atomic transaction; real records remain untouched.
3. Source separation: demo vehicle rejects source='device'; real vehicle rejects source='simulated'.
4. Demo simulator state toggling and status reporting.
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

    # 3. Load demo dataset
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

    # 4. Clear demo dataset
    clear_res = clear_demo_data()
    assert clear_res["status"] == "cleared"
    assert clear_res["deleted"]["vehicles"] == 12
    assert clear_res["deleted"]["drivers"] == 15
    assert clear_res["deleted"]["deliveries"] == 25

    # 5. Verify real vehicle and driver were NOT deleted
    status_after = get_demo_status()
    assert status_after["demo"]["vehicles"] == 0
    assert status_after["demo"]["drivers"] == 0
    assert status_after["real"]["vehicles"] >= 1
    assert status_after["real"]["drivers"] >= 1


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
    is_on = toggle_demo_simulator(True)
    assert is_on is True
    # Toggle off
    is_off = toggle_demo_simulator(False)
    assert is_off is False
