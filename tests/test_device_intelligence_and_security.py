"""
FleetWise — Automated Tests for Device Intelligence, Secure Mobile GPS, Telemetry Ingestion,
Device Ownership Authorization, Duplicate Prevention, and Rate Limiting (Phase 10).
"""
from datetime import UTC

from fastapi.testclient import TestClient


def test_device_registration_attributes_and_duplicate_prevention(client: TestClient, temp_db: str):
    # 1. Setup Driver
    client.post("/drivers", json={"driver_id": "DR-INTEL-01", "name": "Intel Tester", "phone": "+91-9876543210"})

    # 2. Register device with full hardware intelligence
    payload = {
        "driver_id": "DR-INTEL-01",
        "nickname": "Samsung Galaxy S24 (Chrome)",
        "device_category": "Smartphone",
        "model": "SM-S928B",
        "os_family": "Android",
        "os_version": "14",
        "browser_family": "Google Chrome",
        "browser_version": "128.0.0.0",
        "platform": "Linux armv8l",
        "screen_res": "412x915 (@3.0x DPR, portrait-primary)",
        "permission_status": "granted",
        "capabilities": {
            "device_type": "Smartphone",
            "cpu_cores": 8,
            "touch_points": 5,
            "battery_pct": "84%",
            "battery_charging": "🔋 Discharging (Battery)",
            "network_type": "5G",
            "downlink": "45 Mbps",
            "rtt": "22 ms",
            "secure_context": True,
        },
    }

    res = client.post("/devices/register", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["device_id"].startswith("DEV-")
    assert data["driver_id"] == "DR-INTEL-01"
    assert data["device_category"] == "Smartphone"
    assert data["model"] == "SM-S928B"
    assert data["os_family"] == "Android"
    assert data["os_version"] == "14"
    assert data["browser_family"] == "Google Chrome"
    dev_id = data["device_id"]

    # 3. Prevent duplicate registration: Calling register again with identical driver and nickname reuses DEV-ID
    payload_repeat = {**payload, "capabilities": {**payload["capabilities"], "battery_pct": "82%"}}
    res_repeat = client.post("/devices/register", json=payload_repeat)
    assert res_repeat.status_code == 201
    data_repeat = res_repeat.json()
    assert data_repeat["device_id"] == dev_id
    assert data_repeat.get("is_reused") is True

    # 4. Confirm in listing that only 1 device exists for this driver
    res_list = client.get("/devices?driver_id=DR-INTEL-01")
    assert res_list.status_code == 200
    assert len(res_list.json()) == 1


def test_device_ownership_and_spoofing_guards(client: TestClient, temp_db: str):
    # Setup two separate drivers
    client.post("/drivers", json={"driver_id": "DR-ALICE", "name": "Alice Driver", "phone": "+1-415-555-0101"})
    client.post("/drivers", json={"driver_id": "DR-BOB", "name": "Bob Driver", "phone": "+1-415-555-0102"})

    # Register device to Alice
    res_dev_a = client.post("/devices/register", json={
        "driver_id": "DR-ALICE",
        "nickname": "Alice iPhone",
        "os_family": "iOS",
    })
    alice_dev_id = res_dev_a.json()["device_id"]

    # Bob cannot start a tracking session with Alice's device (403 DEVICE_DRIVER_MISMATCH)
    res_bad_start = client.post("/tracking/sessions/start", json={
        "driver_id": "DR-BOB",
        "device_id": alice_dev_id,
    })
    assert res_bad_start.status_code == 403
    assert res_bad_start.json()["error"] == "DEVICE_DRIVER_MISMATCH"

    # Alice starts a valid tracking session
    res_alice_start = client.post("/tracking/sessions/start", json={
        "driver_id": "DR-ALICE",
        "device_id": alice_dev_id,
    })
    assert res_alice_start.status_code == 201
    alice_sess_id = res_alice_start.json()["session_id"]

    # Bob cannot submit GPS telemetry with Alice's session and Bob's driver ID (403 DRIVER_MISMATCH)
    res_spoof = client.post("/tracking/location", json={
        "session_id": alice_sess_id,
        "driver_id": "DR-BOB",
        "latitude": 12.9716,
        "longitude": 77.5946,
        "accuracy": 5.0,
        "device_timestamp": "2026-10-30T10:00:00Z",
    })
    assert res_spoof.status_code == 403
    assert res_spoof.json()["error"] == "DRIVER_MISMATCH"

    # Alice submits valid telemetry with altitude and heading
    res_alice_loc = client.post("/tracking/location", json={
        "session_id": alice_sess_id,
        "driver_id": "DR-ALICE",
        "device_id": alice_dev_id,
        "latitude": 12.9716,
        "longitude": 77.5946,
        "accuracy": 4.5,
        "altitude": 920.5,
        "altitude_accuracy": 3.0,
        "speed": 12.0,
        "heading": 180.0,
        "device_timestamp": "2026-10-30T10:00:00Z",
    })
    assert res_alice_loc.status_code == 201
    loc_data = res_alice_loc.json()
    assert loc_data["latitude"] == 12.9716
    assert loc_data["altitude"] == 920.5
    assert loc_data["altitude_accuracy"] == 3.0
    assert loc_data["heading"] == 180.0


def test_gps_telemetry_rate_limiting_and_validation(client: TestClient, temp_db: str):
    # Setup driver & session
    client.post("/drivers", json={"driver_id": "DR-RATE", "name": "Rate Tester", "phone": "+91-9876543222"})
    res_start = client.post("/tracking/sessions/start", json={"driver_id": "DR-RATE"})
    sess_id = res_start.json()["session_id"]

    # Ingest first fix
    res1 = client.post("/tracking/location", json={
        "session_id": sess_id,
        "latitude": 12.9700,
        "longitude": 77.5900,
        "accuracy": 8.0,
        "device_timestamp": "2026-10-30T10:00:00Z",
    })
    assert res1.status_code == 201

    # Ingest second fix only 0.2s later -> Throttled with 429 RATE_LIMITED
    res2 = client.post("/tracking/location", json={
        "session_id": sess_id,
        "latitude": 12.9701,
        "longitude": 77.5901,
        "accuracy": 8.0,
        "device_timestamp": "2026-10-30T10:00:00.200Z",
    })
    assert res2.status_code == 429
    assert res2.json()["error"] == "RATE_LIMITED"

    # Ingest fix after 1.5s -> Accepted
    res3 = client.post("/tracking/location", json={
        "session_id": sess_id,
        "latitude": 12.9702,
        "longitude": 77.5902,
        "accuracy": 8.0,
        "device_timestamp": "2026-10-30T10:00:01.500Z",
    })
    assert res3.status_code == 201


def test_gps_coordinate_strict_boundaries(client: TestClient, temp_db: str):
    client.post("/drivers", json={"driver_id": "DR-BOUND", "name": "Bound Tester", "phone": "+91-9876543233"})
    res_start = client.post("/tracking/sessions/start", json={"driver_id": "DR-BOUND"})
    sess_id = res_start.json()["session_id"]

    # Invalid latitude > 90
    res_bad_lat = client.post("/tracking/location", json={
        "session_id": sess_id,
        "latitude": 95.0,
        "longitude": 77.0,
        "accuracy": 5.0,
        "device_timestamp": "2026-10-30T10:00:00Z",
    })
    assert res_bad_lat.status_code == 400

    # Invalid longitude < -180
    res_bad_lng = client.post("/tracking/location", json={
        "session_id": sess_id,
        "latitude": 12.0,
        "longitude": -185.0,
        "accuracy": 5.0,
        "device_timestamp": "2026-10-30T10:00:00Z",
    })
    assert res_bad_lng.status_code == 400

    # Negative accuracy < 0
    res_bad_acc = client.post("/tracking/location", json={
        "session_id": sess_id,
        "latitude": 12.0,
        "longitude": 77.0,
        "accuracy": -2.0,
        "device_timestamp": "2026-10-30T10:00:00Z",
    })
    assert res_bad_acc.status_code == 400


def test_network_info_and_ssl_cert_detection(client: TestClient, temp_db: str):
    res = client.get("/network-info")
    assert res.status_code == 200
    data = res.json()
    assert "local_ip" in data
    assert "lan_url" in data
    assert "lan_https_url" in data
    assert "localhost_url" in data
    assert data["https_port"] == 8443
    assert data["port"] == 8000
    assert "has_ssl_certs" in data
    assert "secure_context_hint" in data
    assert "cert_details" in data
    if data["has_ssl_certs"]:
        assert data["cert_details"].get("valid") is True
        assert "trust_guide" in data["cert_details"]


def test_device_token_identity_separation_and_renaming(client: TestClient, temp_db: str):
    client.post("/drivers", json={"driver_id": "DR-MULTI-DEV", "name": "Multi Dev Driver", "phone": "+91-9876543299"})

    # 1. Register Phone A
    res_a = client.post("/devices/register", json={
        "driver_id": "DR-MULTI-DEV",
        "nickname": "Work Phone",
        "client_device_token": "FLT-DEV-PHONE-AAA",
        "identity_confidence": "client_storage_token",
    })
    assert res_a.status_code == 201
    dev_a = res_a.json()
    dev_a_id = dev_a["device_id"]
    assert dev_a["client_device_token"] == "FLT-DEV-PHONE-AAA"

    # 2. Register Phone B for the same driver with a different token
    res_b = client.post("/devices/register", json={
        "driver_id": "DR-MULTI-DEV",
        "nickname": "Personal Phone",
        "client_device_token": "FLT-DEV-PHONE-BBB",
        "identity_confidence": "client_storage_token",
    })
    assert res_b.status_code == 201
    dev_b = res_b.json()
    dev_b_id = dev_b["device_id"]
    assert dev_b["client_device_token"] == "FLT-DEV-PHONE-BBB"

    # Crucial assertion: Two different physical phones for the same driver are NOT merged
    assert dev_a_id != dev_b_id

    # 3. Reloading Phone A reuses dev_a_id and does not create a third device
    res_a_reload = client.post("/devices/register", json={
        "driver_id": "DR-MULTI-DEV",
        "nickname": "Work Phone",
        "client_device_token": "FLT-DEV-PHONE-AAA",
    })
    assert res_a_reload.status_code == 201
    assert res_a_reload.json()["device_id"] == dev_a_id
    assert res_a_reload.json().get("is_reused") is True

    # 4. Device renaming endpoint
    res_rename = client.patch(f"/devices/{dev_a_id}/rename", json={"nickname": "Field Operations Tablet"})
    assert res_rename.status_code == 200
    assert res_rename.json()["nickname"] == "Field Operations Tablet"

    # Verify persisted in GET /devices
    res_list = client.get("/devices?driver_id=DR-MULTI-DEV")
    assert res_list.status_code == 200
    assert len(res_list.json()) == 2


def test_revoked_device_cannot_reregister_or_send_telemetry(client: TestClient, temp_db: str):
    client.post("/drivers", json={"driver_id": "DR-REVOKE-TEST", "name": "Revoke Tester", "phone": "+91-9876543288"})

    # Register device
    res_reg = client.post("/devices/register", json={
        "driver_id": "DR-REVOKE-TEST",
        "nickname": "Compromised Device",
        "client_device_token": "FLT-DEV-COMPROMISED-1",
    })
    dev_id = res_reg.json()["device_id"]

    # Start tracking session
    res_start = client.post("/tracking/sessions/start", json={
        "driver_id": "DR-REVOKE-TEST",
        "device_id": dev_id,
    })
    sess_id = res_start.json()["session_id"]

    # Send 1 good location
    res_loc = client.post("/tracking/location", json={
        "session_id": sess_id,
        "device_id": dev_id,
        "latitude": 12.9716,
        "longitude": 77.5946,
        "accuracy": 5.0,
        "device_timestamp": "2026-10-30T10:00:00Z",
    })
    assert res_loc.status_code == 201

    # Revoke device
    res_rev = client.post(f"/devices/{dev_id}/revoke", json={"reason": "Device reported lost/compromised"})
    assert res_rev.status_code == 200
    assert res_rev.json()["is_revoked"] is True

    # Subsequent telemetry using old session is strictly rejected with 403 DEVICE_REVOKED
    res_blocked_loc = client.post("/tracking/location", json={
        "session_id": sess_id,
        "device_id": dev_id,
        "latitude": 12.9720,
        "longitude": 77.5950,
        "accuracy": 5.0,
        "device_timestamp": "2026-10-30T10:00:05Z",
    })
    assert res_blocked_loc.status_code == 403
    assert res_blocked_loc.json()["error"] == "DEVICE_REVOKED"

    # Attempting to re-register with the revoked persistent client token is blocked with 403
    res_re_register = client.post("/devices/register", json={
        "driver_id": "DR-REVOKE-TEST",
        "nickname": "Trying to bypass revocation",
        "client_device_token": "FLT-DEV-COMPROMISED-1",
    })
    assert res_re_register.status_code == 403
    assert res_re_register.json()["error"] == "DEVICE_REVOKED"


def test_out_of_order_stale_and_jump_gps_anomalies(client: TestClient, temp_db: str):
    from datetime import datetime, timedelta
    now = datetime.now(UTC)
    t0_str = now.isoformat()
    t1_str = (now + timedelta(seconds=2)).isoformat()
    t_ooo_str = (now + timedelta(seconds=1)).isoformat()  # Out of order compared to t1

    client.post("/drivers", json={"driver_id": "DR-ANOMALY", "name": "Anomaly Tester", "phone": "+91-9876543277"})
    res_start = client.post("/tracking/sessions/start", json={"driver_id": "DR-ANOMALY"})
    sess_id = res_start.json()["session_id"]

    # Point 1: Valid initial fix with synchronized current timestamp
    res1 = client.post("/tracking/location", json={
        "session_id": sess_id,
        "latitude": 12.9716,
        "longitude": 77.5946,
        "accuracy": 10.0,
        "device_timestamp": t0_str,
    })
    assert res1.status_code == 201
    assert res1.json()["quality_flag"] == "accepted"

    # Point 2: Physical jump (>300m in 2 seconds = >150 m/s > 50 m/s threshold)
    res_jump = client.post("/tracking/location", json={
        "session_id": sess_id,
        "latitude": 12.9800,  # ~930 meters north
        "longitude": 77.5946,
        "accuracy": 10.0,
        "device_timestamp": t1_str,
    })
    assert res_jump.status_code == 201
    jump_data = res_jump.json()
    assert jump_data["is_implausible_jump"] is True
    assert jump_data["quality_flag"] == "flagged_jump"
    # Preserves received coordinates for forensic audit
    assert jump_data["latitude"] == 12.9800

    # Point 3: Out-of-order timestamp (sent with timestamp earlier than point 2)
    res_ooo = client.post("/tracking/location", json={
        "session_id": sess_id,
        "latitude": 12.9810,
        "longitude": 77.5946,
        "accuracy": 10.0,
        "device_timestamp": t_ooo_str,
    })
    assert res_ooo.status_code == 201
    assert res_ooo.json()["quality_flag"] == "out_of_order"


def test_concurrent_gps_rate_limit_atomic_enforcement(client: TestClient, temp_db: str):
    from concurrent.futures import ThreadPoolExecutor

    client.post("/drivers", json={"driver_id": "DR-CONCUR", "name": "Concurrency Tester", "phone": "+91-9876543266"})
    res_start = client.post("/tracking/sessions/start", json={"driver_id": "DR-CONCUR"})
    sess_id = res_start.json()["session_id"]

    # Initial fix to establish baseline
    res_init = client.post("/tracking/location", json={
        "session_id": sess_id,
        "latitude": 12.9700,
        "longitude": 77.5900,
        "accuracy": 5.0,
        "device_timestamp": "2026-10-30T14:00:00Z",
    })
    assert res_init.status_code == 201

    # Send 8 parallel location requests simultaneously at 14:00:01.000Z
    def send_fix(idx):
        return client.post("/tracking/location", json={
            "session_id": sess_id,
            "latitude": 12.9700 + (idx * 0.0001),
            "longitude": 77.5900 + (idx * 0.0001),
            "accuracy": 5.0,
            "device_timestamp": f"2026-10-30T14:00:01.{idx:03d}Z",
        })

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(send_fix, range(1, 9)))

    status_codes = [r.status_code for r in results]
    # Majority must be throttled with 429; at most 2 can succeed if wall-clock span crosses rate interval
    assert 429 in status_codes
    assert status_codes.count(429) >= 5
    assert status_codes.count(201) <= 2


def test_tunnel_external_access_authentication_guard(client: TestClient, temp_db: str):
    # Simulating request through localtunnel public proxy
    tunnel_headers = {"x-forwarded-host": "fleetwise-secure.loca.lt"}

    # Public unauthenticated request attempting write must receive 401 UNAUTHORIZED
    res_unauth = client.post("/vehicles", json={
        "vehicle_id": "V-TUNNEL-1",
        "registration_no": "KA-01-TU-1111",
        "type": "van",
        "capacity": 1000,
    }, headers=tunnel_headers)
    assert res_unauth.status_code == 401
    assert res_unauth.json()["error"] == "UNAUTHORIZED"

    # Authenticated user with ops_lead session cookie is allowed
    from app.auth import sign_session_data
    token = sign_session_data({"username": "ops_lead", "role": "ops_lead"})
    auth_headers = {**tunnel_headers, "Cookie": f"fleetwise_session={token}"}

    res_auth = client.post("/vehicles", json={
        "vehicle_id": "V-TUNNEL-1",
        "registration_no": "KA-01-TU-1111",
        "type": "van",
        "capacity": 1000,
    }, headers=auth_headers)
    assert res_auth.status_code == 201


def test_battery_truthfulness_unit_states_node():
    """Executes the unit tests for all 4 battery states with mocked BatteryManager under Node.js."""
    import subprocess
    proc = subprocess.run(["node", "--test", "tests/test_battery_states.test.js"], capture_output=True, text=True)
    assert proc.returncode == 0, f"Node battery tests failed:\n{proc.stdout}\n{proc.stderr}"
    assert "fail 0" in proc.stdout
    assert "pass 6" in proc.stdout


def test_system_host_power_endpoint(client: TestClient):
    """Verifies that /system/host-power returns server host physical telemetry with explicit role isolation, and old routes are 404."""
    res = client.get("/system/host-power")
    assert res.status_code == 200
    data = res.json()
    assert "supported" in data
    assert data["role"] == "server_host_power"
    assert "Server host power" in data["label"]

    # Strict route removal: old endpoints MUST return 404
    assert client.get("/api/system/power-status").status_code == 404
    assert client.get("/system/power-status").status_code == 404


def test_linux_and_missing_hardware_power_fallback(monkeypatch):
    """Verifies that on non-Windows or when ctypes.windll is missing, status is 'unavailable' with a truthful reason."""
    import sys

    from app.power import get_server_host_power_status

    # Simulate non-Windows Linux platform with no psutil battery
    monkeypatch.setattr(sys, "platform", "linux")
    res = get_server_host_power_status()
    assert res["supported"] is False
    assert res["status"] == "unavailable"
    assert "No battery sensor detected" in res["reason"]
    assert res["percentage_num"] is None
    assert res["role"] == "server_host_power"


def test_probe_endpoints_and_recording(client: TestClient, temp_db: str):
    """Verifies that /probe serves HTML and /probe/report records client diagnostics into device_probe_reports."""
    # 1. GET /probe
    res_probe = client.get("/probe")
    assert res_probe.status_code == 200
    assert "BATTERY DIAGNOSTICS" in res_probe.text
    assert "TRUTHFULNESS COMPLIANT" in res_probe.text

    # 2. POST /probe/report
    probe_payload = {
        "device_id": "DEV-PROBE-01",
        "driver_id": "DR-001",
        "battery": {
            "status": "measured_suspect",
            "reason": "values equal the API's defaults; the browser may not be reading a battery",
            "raw": {
                "level": 1.0,
                "charging": True,
                "chargingTime": 0,
                "dischargingTime": "Infinity",
            },
        },
        "browser": "Chrome 156.0.0.0",
        "isSecureContext": True,
    }
    res_post = client.post("/probe/report", json=probe_payload)
    assert res_post.status_code == 200
    report_data = res_post.json()
    assert report_data["status"] == "ok"
    assert report_data["report_id"].startswith("prb_")

    # 3. GET /devices/probe-reports
    res_list = client.get("/devices/probe-reports")
    assert res_list.status_code == 200
    reports = res_list.json()
    assert len(reports) >= 1
    assert reports[0]["report_id"] == report_data["report_id"]
    assert reports[0]["device_id"] == "DEV-PROBE-01"




