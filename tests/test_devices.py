from fastapi.testclient import TestClient


def test_device_registration_and_listing(client: TestClient, temp_db: str):
    # Setup driver
    client.post("/drivers", json={"driver_id": "DR-DEV-01", "name": "Device Tester", "phone": "+91-9876543210"})

    # 1. Register device
    reg_payload = {
        "driver_id": "DR-DEV-01",
        "nickname": "Work iPhone 15",
        "os_family": "iOS",
        "browser_family": "Mobile Safari",
        "platform": "iPhone",
        "screen_res": "393x852",
        "capabilities": {"geolocation": True, "battery": True},
        "permission_status": "granted",
    }
    res = client.post("/devices/register", json=reg_payload)
    assert res.status_code == 201
    dev = res.json()
    assert dev["device_id"].startswith("DEV-")
    assert dev["driver_id"] == "DR-DEV-01"
    assert dev["nickname"] == "Work iPhone 15"
    assert dev["is_revoked"] is False
    device_id = dev["device_id"]

    # 2. List devices
    res_list = client.get("/devices")
    assert res_list.status_code == 200
    devices = res_list.json()
    assert any(d["device_id"] == device_id for d in devices)

    # 3. Filter devices by driver
    res_filt = client.get("/devices?driver_id=DR-DEV-01")
    assert res_filt.status_code == 200
    assert len(res_filt.json()) == 1

    # 4. Get device details
    res_det = client.get(f"/devices/{device_id}")
    assert res_det.status_code == 200
    det = res_det.json()
    assert det["device_id"] == device_id
    assert det["capabilities"]["geolocation"] is True
    assert det["active_session"] is None


def test_device_revocation_and_authorization_guards(client: TestClient, temp_db: str):
    # Setup driver
    client.post("/drivers", json={"driver_id": "DR-DEV-02", "name": "Revoke Tester", "phone": "+1-415-555-2671"})

    # Register device
    res_dev = client.post("/devices/register", json={
        "driver_id": "DR-DEV-02",
        "nickname": "Test Pixel 8",
        "os_family": "Android",
        "browser_family": "Chrome Mobile",
    })
    device_id = res_dev.json()["device_id"]

    # Start tracking session linked to device
    res_start = client.post("/tracking/sessions/start", json={
        "driver_id": "DR-DEV-02",
        "device_id": device_id,
        "device_info": "Pixel 8 Pro",
    })
    assert res_start.status_code == 201
    sess_id = res_start.json()["session_id"]
    assert res_start.json()["device_id"] == device_id

    # Ingest 1 location fix
    res_loc = client.post("/tracking/location", json={
        "session_id": sess_id,
        "device_id": device_id,
        "latitude": 37.7749,
        "longitude": -122.4194,
        "accuracy": 10.0,
        "device_timestamp": "2026-10-29T12:00:00Z",
    })
    assert res_loc.status_code == 201

    # Verify device telemetry history
    res_tel = client.get(f"/devices/{device_id}/telemetry")
    assert res_tel.status_code == 200
    assert len(res_tel.json()) == 1
    assert res_tel.json()[0]["latitude"] == 37.7749

    # Revoke device
    res_rev = client.post(f"/devices/{device_id}/revoke", json={"reason": "Device reported lost in transit"})
    assert res_rev.status_code == 200
    assert res_rev.json()["is_revoked"] is True

    # Active session should have been automatically stopped
    res_det = client.get(f"/devices/{device_id}")
    assert res_det.json()["is_revoked"] is True
    assert res_det.json()["active_session"] is None

    # Revoked device CANNOT submit further GPS fixes (403 DEVICE_REVOKED)
    res_loc2 = client.post("/tracking/location", json={
        "session_id": sess_id,
        "device_id": device_id,
        "latitude": 37.7755,
        "longitude": -122.4199,
        "accuracy": 8.0,
        "device_timestamp": "2026-10-29T12:01:00Z",
    })
    assert res_loc2.status_code == 403
    assert res_loc2.json()["error"] == "DEVICE_REVOKED"

    # Revoked device CANNOT start a new tracking session (403 DEVICE_REVOKED)
    res_start2 = client.post("/tracking/sessions/start", json={
        "driver_id": "DR-DEV-02",
        "device_id": device_id,
    })
    assert res_start2.status_code == 403
    assert res_start2.json()["error"] == "DEVICE_REVOKED"


def test_device_negative_cases(client: TestClient, temp_db: str):
    # Nonexistent driver register returns 404
    res_bad_drv = client.post("/devices/register", json={
        "driver_id": "DR-NOT-EXIST",
        "nickname": "Phantom Phone",
    })
    assert res_bad_drv.status_code == 404
    assert res_bad_drv.json()["error"] == "NOT_FOUND"

    # Nonexistent device details returns 404
    assert client.get("/devices/DEV-NONEXISTENT").status_code == 404

    # Nonexistent device revoke returns 404
    res_bad_rev = client.post("/devices/DEV-NONEXISTENT/revoke", json={"reason": "test"})
    assert res_bad_rev.status_code == 404
    assert res_bad_rev.json()["error"] == "NOT_FOUND"


def test_driver_phone_full_telemetry_and_battery_permissions(client: TestClient, temp_db: str):
    client.post("/drivers", json={"driver_id": "DR-PHONE-99", "name": "Phone Sensor Driver", "phone": "+91-9876500099"})

    telemetry_payload = {
        "device_id": "DEV-PHONE-99",
        "driver_id": "DR-PHONE-99",
        "battery": {
            "value": 84,
            "pct": "84%",
            "status": "measured",
            "is_charging": True,
            "source": "BatteryManager",
        },
        "network": {
            "online": True,
            "effective_type": "5G",
            "downlink_mbps": 45.2,
            "rtt_ms": 22,
        },
        "motion": {
            "compass_heading": 142,
            "alpha": 218.0,
            "beta": 12.5,
            "gamma": -3.1,
            "accel_x": 0.12,
            "accel_y": 0.05,
            "accel_z": 9.81,
        },
        "hardware": {
            "model": "Pixel 9 Pro",
            "os_family": "Android",
            "os_version": "15",
            "browser_family": "Chrome",
            "browser_version": "131",
            "cpu_cores": 8,
            "device_memory_gb": 12,
            "storage_used_mb": 420,
            "storage_quota_gb": 128.0,
            "screen_res": "412x915 @2.6x",
            "max_touch_points": 10,
        },
        "permissions": {
            "battery": "granted",
            "geolocation": "granted",
            "motion": "granted",
            "hardware": "granted",
            "full_device_access": True,
        },
    }

    res = client.post("/api/driver/telemetry", json=telemetry_payload)
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["device"]["device_id"] == "DEV-PHONE-99"
    assert body["device"]["model"] == "Pixel 9 Pro"
    assert body["device"]["capabilities"]["battery"]["value"] == 84
    assert body["device"]["capabilities"]["network_type"] == "5G"
    assert body["device"]["capabilities"]["permissions"]["full_device_access"] is True

    # Verify /tracking/drivers/live returns the phone capabilities
    live_res = client.get("/tracking/drivers/live")
    assert live_res.status_code == 200
    drv_entry = next(d for d in live_res.json()["drivers"] if d["driver_id"] == "DR-PHONE-99")
    assert drv_entry["device"] is not None
    assert drv_entry["device"]["model"] == "Pixel 9 Pro"
    assert drv_entry["device"]["capabilities"]["battery"]["value"] == 84
    assert drv_entry["device"]["capabilities"]["network_type"] == "5G"


