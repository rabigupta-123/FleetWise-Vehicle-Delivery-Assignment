from fastapi.testclient import TestClient


def test_driver_phone_update_and_validation(client: TestClient, temp_db: str):
    # Create driver
    res = client.post("/drivers", json={"driver_id": "DR-GPS-01", "name": "GPS Driver", "phone": "+91-9876543210"})
    assert res.status_code == 201

    # Update phone with tester's real phone number
    res_up = client.patch("/drivers/DR-GPS-01/phone", json={"phone": "+1-555-019-2834"})
    assert res_up.status_code == 200
    assert res_up.json()["phone"] == "+1-555-019-2834"

    # Verify updated in driver list
    drv = [d for d in client.get("/drivers").json() if d["driver_id"] == "DR-GPS-01"][0]
    assert drv["phone"] == "+1-555-019-2834"

    # Invalid phone format fails validation
    res_bad = client.patch("/drivers/DR-GPS-01/phone", json={"phone": "short"})
    assert res_bad.status_code == 400
    assert res_bad.json()["error"] == "VALIDATION_ERROR"

    # Nonexistent driver returns 404
    res_404 = client.patch("/drivers/DR-NONEXISTENT/phone", json={"phone": "+91-9876543210"})
    assert res_404.status_code == 404
    assert res_404.json()["error"] == "NOT_FOUND"


def test_tracking_session_lifecycle_and_gps_ingestion(client: TestClient, temp_db: str):
    # Setup vehicle, driver, delivery and assignment
    client.post("/vehicles", json={"vehicle_id": "V-TRK-01", "registration_no": "KA-01-TRK-01", "type": "Van", "capacity": 1500})
    client.post("/drivers", json={"driver_id": "DR-TRK-01", "name": "Track Driver", "phone": "+91-9876543210"})
    client.post("/deliveries", json={"delivery_id": "D-TRK-01", "pickup": "Warehouse A", "dropoff": "Client B", "scheduled_time": "2026-10-30T10:00:00Z", "priority": "urgent"})

    # Assign
    res_asg = client.post("/deliveries/D-TRK-01/assign", json={"vehicle_id": "V-TRK-01", "driver_id": "DR-TRK-01"})
    assert res_asg.status_code == 201

    # 1. Start tracking session
    res_start = client.post("/tracking/sessions/start", json={"driver_id": "DR-TRK-01", "device_info": "iPhone 15 Mobile Safari"})
    assert res_start.status_code == 201
    sess = res_start.json()
    assert sess["driver_id"] == "DR-TRK-01"
    assert sess["vehicle_id"] == "V-TRK-01"
    assert sess["delivery_id"] == "D-TRK-01"
    assert sess["status"] == "active"
    session_id = sess["session_id"]

    # 2. Ingest GPS point 1 (Bengaluru Electronic City)
    pt1_payload = {
        "session_id": session_id,
        "latitude": 12.8452,
        "longitude": 77.6602,
        "accuracy": 8.5,
        "speed": 11.2,  # m/s
        "heading": 85.0,
        "device_timestamp": "2026-10-29T12:00:00Z",
    }
    res_pt1 = client.post("/tracking/location", json=pt1_payload)
    assert res_pt1.status_code == 201
    pt1_data = res_pt1.json()
    assert pt1_data["latitude"] == 12.8452
    assert "https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=" in pt1_data["street_view_url"]

    # 3. Ingest GPS point 2 (moving along corridor)
    pt2_payload = {
        "session_id": session_id,
        "latitude": 12.8510,
        "longitude": 77.6655,
        "accuracy": 6.2,
        "speed": 14.5,
        "heading": 82.0,
        "device_timestamp": "2026-10-29T12:01:00Z",
    }
    res_pt2 = client.post("/tracking/location", json=pt2_payload)
    assert res_pt2.status_code == 201

    # 4. Check latest driver location
    res_drv_lat = client.get("/tracking/drivers/DR-TRK-01/latest")
    assert res_drv_lat.status_code == 200
    drv_latest = res_drv_lat.json()
    assert drv_latest["has_gps"] is True
    assert drv_latest["latitude"] == 12.8510
    assert drv_latest["tracking_status"] == "live"
    assert "google.com/maps" in drv_latest["street_view_url"]

    # 5. Check latest vehicle location (associated via active assignment)
    res_veh_lat = client.get("/tracking/vehicles/V-TRK-01/latest")
    assert res_veh_lat.status_code == 200
    veh_latest = res_veh_lat.json()
    assert veh_latest["has_gps"] is True
    assert veh_latest["vehicle_id"] == "V-TRK-01"
    assert veh_latest["registration_no"] == "KA-01-TRK-01"
    assert veh_latest["assigned_driver"]["name"] == "Track Driver"

    # 6. Check latest delivery location
    res_del_lat = client.get("/tracking/deliveries/D-TRK-01/latest")
    assert res_del_lat.status_code == 200
    del_latest = res_del_lat.json()
    assert del_latest["has_gps"] is True
    assert del_latest["latest_location"]["latitude"] == 12.8510

    # 7. Check location history trail
    res_hist = client.get(f"/tracking/history?session_id={session_id}")
    assert res_hist.status_code == 200
    hist = res_hist.json()
    assert hist["count"] == 2
    assert len(hist["trail"]) == 2

    # 8. Check telemetry graph endpoint
    res_graph = client.get(f"/tracking/telemetry-graph?session_id={session_id}")
    assert res_graph.status_code == 200
    graph_data = res_graph.json()
    assert graph_data["point_count"] == 2
    assert graph_data["total_distance_km"] > 0.5
    assert graph_data["max_speed_kmh"] > 0
    assert len(graph_data["data_points"]) == 2

    # 9. Stop session
    res_stop = client.post("/tracking/sessions/stop", json={"session_id": session_id})
    assert res_stop.status_code == 200
    assert res_stop.json()["status"] == "stopped"

    # Ingesting to stopped session is rejected
    res_after_stop = client.post("/tracking/location", json=pt2_payload)
    assert res_after_stop.status_code == 400
    assert res_after_stop.json()["error"] == "SESSION_INACTIVE"


def test_gps_coordinate_boundaries_and_empty_states(client: TestClient, temp_db: str):
    # Start a dummy session
    client.post("/drivers", json={"driver_id": "DR-BOUND-01", "name": "Bound Driver", "phone": "+91-9876543210"})
    res_sess = client.post("/tracking/sessions/start", json={"driver_id": "DR-BOUND-01"})
    session_id = res_sess.json()["session_id"]

    # Latitude out of bounds (> 90.0)
    bad_lat = {
        "session_id": session_id,
        "latitude": 95.1234,
        "longitude": 77.0,
        "accuracy": 10.0,
        "device_timestamp": "2026-10-29T12:00:00Z",
    }
    res_bad_lat = client.post("/tracking/location", json=bad_lat)
    assert res_bad_lat.status_code == 400
    assert res_bad_lat.json()["error"] == "VALIDATION_ERROR"

    # Longitude out of bounds (<-180.0)
    bad_lng = {
        "session_id": session_id,
        "latitude": 12.0,
        "longitude": -195.0,
        "accuracy": 10.0,
        "device_timestamp": "2026-10-29T12:00:00Z",
    }
    res_bad_lng = client.post("/tracking/location", json=bad_lng)
    assert res_bad_lng.status_code == 400
    assert res_bad_lng.json()["error"] == "VALIDATION_ERROR"

    # Negative accuracy
    bad_acc = {
        "session_id": session_id,
        "latitude": 12.0,
        "longitude": 77.0,
        "accuracy": -5.0,
        "device_timestamp": "2026-10-29T12:00:00Z",
    }
    res_bad_acc = client.post("/tracking/location", json=bad_acc)
    assert res_bad_acc.status_code == 400
    assert res_bad_acc.json()["error"] == "VALIDATION_ERROR"

    # Vehicle with no GPS returns proper offline empty state
    client.post("/vehicles", json={"vehicle_id": "V-EMPTY", "registration_no": "KA-EMPTY-01", "type": "Van", "capacity": 1000})
    res_veh_empty = client.get("/tracking/vehicles/V-EMPTY/latest")
    assert res_veh_empty.status_code == 200
    assert res_veh_empty.json()["has_gps"] is False
    assert res_veh_empty.json()["status"] == "offline"

    # Nonexistent vehicle returns 404
    assert client.get("/tracking/vehicles/V-9999/latest").status_code == 404


def test_driver_gps_consent_requirement_and_revocation(client: TestClient, temp_db: str):
    """
    Verifies that driver explicit consent is mandatory before coordinates can be ingested.
    Rejects coordinates with 403 when consent is missing or revoked.
    """
    client.post("/drivers", json={"driver_id": "DR-CONSENT-01", "name": "Consent Driver", "phone": "+91-9876543299"})

    # 1. Start tracking session WITHOUT consent
    res_start = client.post("/tracking/sessions/start", json={
        "driver_id": "DR-CONSENT-01",
        "consent_given": False,
    })
    assert res_start.status_code == 201
    sess_data = res_start.json()
    assert sess_data["consent_given"] is False
    assert sess_data["consent_timestamp"] is None
    sess_id = sess_data["session_id"]

    # 2. Coordinate stream must be rejected with 403 CONSENT_REQUIRED
    res_fix_blocked = client.post("/tracking/location", json={
        "session_id": sess_id,
        "latitude": 12.9716,
        "longitude": 77.5946,
        "accuracy": 5.0,
        "device_timestamp": "2026-10-31T10:00:00Z",
    })
    assert res_fix_blocked.status_code == 403
    assert res_fix_blocked.json()["error"] == "CONSENT_REQUIRED"

    # 3. Explicitly grant driver consent via endpoint
    res_consent = client.post(f"/tracking/sessions/{sess_id}/consent", json={"consent_given": True})
    assert res_consent.status_code == 200
    assert res_consent.json()["consent_given"] is True
    assert res_consent.json()["consent_timestamp"] is not None

    # 4. Ingesting location fix now succeeds with 201
    res_fix_ok = client.post("/tracking/location", json={
        "session_id": sess_id,
        "latitude": 12.9716,
        "longitude": 77.5946,
        "accuracy": 5.0,
        "device_timestamp": "2026-10-31T10:00:00Z",
    })
    assert res_fix_ok.status_code == 201

    # 5. Revoking consent blocks future location fixes
    client.post(f"/tracking/sessions/{sess_id}/consent", json={"consent_given": False})
    res_fix_revoked = client.post("/tracking/location", json={
        "session_id": sess_id,
        "latitude": 12.9720,
        "longitude": 77.5950,
        "accuracy": 5.0,
        "device_timestamp": "2026-10-31T10:00:02Z",
    })
    assert res_fix_revoked.status_code == 403
    assert res_fix_revoked.json()["error"] == "CONSENT_REQUIRED"


def test_gps_telemetry_retention_purge(temp_db: str, monkeypatch):
    """
    Verifies that the configurable GPS retention policy correctly purges
    historical fixes older than the retention cutoff (default 30 days).
    """
    import sqlite3
    from datetime import UTC, datetime, timedelta

    from app.db import purge_old_gps_telemetry

    conn = sqlite3.connect(temp_db)
    # Insert session
    conn.execute(
        "INSERT INTO drivers (driver_id, name, phone) VALUES ('DR-RET-01', 'Ret Driver', '+919999900000')"
    )
    conn.execute(
        "INSERT INTO tracking_sessions (session_id, driver_id, started_at, status) VALUES ('TRK-RET-01', 'DR-RET-01', '2026-09-01T00:00:00Z', 'active')"
    )

    # Insert old fix (45 days ago) and recent fix (5 days ago)
    old_ts = (datetime.now(UTC) - timedelta(days=45)).isoformat()
    recent_ts = (datetime.now(UTC) - timedelta(days=5)).isoformat()

    conn.execute(
        """
        INSERT INTO gps_locations (location_id, session_id, driver_id, latitude, longitude, accuracy, device_timestamp, server_timestamp)
        VALUES ('LOC-OLD', 'TRK-RET-01', 'DR-RET-01', 12.9, 77.5, 10.0, ?, ?)
        """,
        (old_ts, old_ts),
    )
    conn.execute(
        """
        INSERT INTO gps_locations (location_id, session_id, driver_id, latitude, longitude, accuracy, device_timestamp, server_timestamp)
        VALUES ('LOC-RECENT', 'TRK-RET-01', 'DR-RET-01', 12.91, 77.51, 10.0, ?, ?)
        """,
        (recent_ts, recent_ts),
    )
    conn.commit()

    # Verify both fixes exist
    count_before = conn.execute("SELECT COUNT(*) FROM gps_locations").fetchone()[0]
    assert count_before == 2

    # Run purge with 30-day retention
    purged = purge_old_gps_telemetry(conn, retention_days=30)
    conn.commit()

    assert purged == 1
    remaining = conn.execute("SELECT location_id FROM gps_locations").fetchall()
    assert len(remaining) == 1
    assert remaining[0][0] == "LOC-RECENT"
    conn.close()


def test_three_simulated_devices_interleaved_live_tracking(client: TestClient, temp_db: str):
    """
    Verifies multi-device concurrent tracking and security invariants:
    1. 3 separate driver pairing tokens are created and bound to distinct devices.
    2. Single-device binding: second physical device trying to use token A is rejected (403).
    3. Revoked token is rejected immediately (403).
    4. Interleaved telemetry transmission from multiple devices maintains zero cross-contamination.
    5. GET /tracking/drivers/live returns exact uncapped accuracy, quality score, 95% radius,
       and position confidence with live breadcrumb trails.
    """
    from app.auth import revoke_pairing_token

    # 1. Register 3 drivers and vehicles
    for i in (1, 2, 3):
        client.post("/vehicles", json={
            "vehicle_id": f"V-TRK-0{i}",
            "registration_no": f"KA-01-TK-100{i}",
            "type": "van",
            "capacity": 1000 + i * 100,
        })
        client.post("/drivers", json={
            "driver_id": f"DR-TRK-0{i}",
            "name": f"Track Driver {i}",
            "phone": f"+91 98888 0000{i}",
        })

    # 2. Generate pairing tokens
    r_tok1 = client.post("/api/pairing-tokens", json={"driver_id": "DR-TRK-01"}).json()
    r_tok2 = client.post("/api/pairing-tokens", json={"driver_id": "DR-TRK-02"}).json()
    r_tok3 = client.post("/api/pairing-tokens", json={"driver_id": "DR-TRK-03"}).json()

    tok1, tok2, tok3 = r_tok1["token"], r_tok2["token"], r_tok3["token"]
    assert "https://" in r_tok1["url"]
    assert tok1 in r_tok1["url"]

    # 3. Device initialization and pairing
    # Device A connects with tok1
    sess_a = client.get(f"/api/driver/session?pair={tok1}", headers={"x-device-id": "DEV-PHONE-A"}).json()
    assert sess_a["driver_id"] == "DR-TRK-01"
    sess_id_a = sess_a["session_id"]

    # Device B connects with tok2
    sess_b = client.get(f"/api/driver/session?pair={tok2}", headers={"x-device-id": "DEV-PHONE-B"}).json()
    assert sess_b["driver_id"] == "DR-TRK-02"
    sess_id_b = sess_b["session_id"]

    # Device C connects with tok3
    sess_c = client.get(f"/api/driver/session?pair={tok3}", headers={"x-device-id": "DEV-PHONE-C"}).json()
    assert sess_c["driver_id"] == "DR-TRK-03"

    # Consent given
    client.post(f"/tracking/sessions/{sess_id_a}/consent", json={"consent": True})
    client.post(f"/tracking/sessions/{sess_id_b}/consent", json={"consent": True})

    # 4. Security Check: Second physical device trying to use tok1 is REJECTED
    rogue_res = client.get(f"/api/driver/session?pair={tok1}", headers={"x-device-id": "DEV-PHONE-ROGUE"})
    assert rogue_res.status_code == 403
    assert "Token bound to device" in rogue_res.json()["message"]

    # 5. Security Check: Revoking tok3 rejects Device C
    revoke_pairing_token(tok3)
    revoked_res = client.get(f"/api/driver/session?pair={tok3}", headers={"x-device-id": "DEV-PHONE-C"})
    assert revoked_res.status_code == 403
    assert "revoked" in revoked_res.json()["message"]

    # 6. Interleaved telemetry transmission: Device A & Device B
    now_ts = "2026-11-01T04:00:00Z"
    now_ts2 = "2026-11-01T04:00:05Z"

    # Fix A1: Excellent accuracy (4.2m)
    r_a1 = client.post("/tracking/location", json={
        "session_id": sess_id_a,
        "driver_id": "DR-TRK-01",
        "latitude": 12.9716,
        "longitude": 77.5946,
        "accuracy": 4.2,
        "speed": 8.0,
        "heading": 90.0,
        "device_timestamp": now_ts,
    })
    assert r_a1.status_code == 201

    # Fix B1: Poor accuracy (76.0m)
    r_b1 = client.post("/tracking/location", json={
        "session_id": sess_id_b,
        "driver_id": "DR-TRK-02",
        "latitude": 12.9800,
        "longitude": 77.6000,
        "accuracy": 76.0,
        "speed": 12.5,
        "heading": 180.0,
        "device_timestamp": now_ts,
    })
    assert r_b1.status_code == 201

    # Fix A2: Device A moves slightly
    r_a2 = client.post("/tracking/location", json={
        "session_id": sess_id_a,
        "driver_id": "DR-TRK-01",
        "latitude": 12.9719,
        "longitude": 77.5949,
        "accuracy": 3.8,
        "speed": 9.2,
        "heading": 85.0,
        "device_timestamp": now_ts2,
    })
    assert r_a2.status_code == 201

    # Fix B2: Device B moves slightly
    r_b2 = client.post("/tracking/location", json={
        "session_id": sess_id_b,
        "driver_id": "DR-TRK-02",
        "latitude": 12.9810,
        "longitude": 77.6010,
        "accuracy": 72.0,
        "speed": 11.0,
        "heading": 175.0,
        "device_timestamp": now_ts2,
    })
    assert r_b2.status_code == 201

    # 7. Query live fleet tracking overview: GET /tracking/drivers/live
    live_res = client.get("/tracking/drivers/live")
    assert live_res.status_code == 200
    live_data = live_res.json()

    drivers_by_id = {d["driver_id"]: d for d in live_data["drivers"]}
    assert "DR-TRK-01" in drivers_by_id
    assert "DR-TRK-02" in drivers_by_id

    dr1 = drivers_by_id["DR-TRK-01"]
    dr2 = drivers_by_id["DR-TRK-02"]

    # Invariants for Driver 1 (Live, Excellent accuracy 3.8m, Score > 90)
    assert dr1["status"] == "live"
    assert dr1["latest_fix"]["accuracy"] == 3.8
    assert dr1["latest_fix"]["accuracy_label"] == "Excellent"
    assert dr1["latest_fix"]["accuracy_score"] > 90.0
    assert len(dr1["trail"]) == 2

    # Invariants for Driver 2 (Live, Poor accuracy 72.0m, Score around 23)
    assert dr2["status"] == "live"
    assert dr2["latest_fix"]["accuracy"] == 72.0
    assert dr2["latest_fix"]["accuracy_label"] == "Poor"
    assert dr2["latest_fix"]["accuracy_score"] < 30.0
    assert len(dr2["trail"]) == 2


def test_tunnel_proxy_header_loopback_denial(client: TestClient, temp_db: str):
    """
    Verifies that requests carrying reverse-proxy / tunnel headers
    (Forwarded, X-Forwarded-For, CF-Connecting-IP, CF-Ray) are NEVER
    trusted as loopback, preventing unauthorized admin/dashboard access
    when running FleetWise behind a local tunnel (e.g. cloudflared).
    """
    # 1. Plain loopback request to /vehicles succeeds
    r_clean = client.get("/vehicles")
    assert r_clean.status_code == 200

    # 2. Request carrying X-Forwarded-For is denied (403 Forbidden)
    r_xff = client.get("/vehicles", headers={"x-forwarded-for": "198.51.100.22"})
    assert r_xff.status_code == 403
    assert "loopback" in r_xff.json()["message"]

    # 3. Request carrying CF-Connecting-IP is denied (403 Forbidden)
    r_cf = client.get("/vehicles", headers={"cf-connecting-ip": "203.0.113.88"})
    assert r_cf.status_code == 403

    # 4. Request carrying Forwarded header is denied
    r_fwd = client.get("/demo/status", headers={"forwarded": "for=192.0.2.60;proto=http"})
    assert r_fwd.status_code == 403

    # 5. Public diagnostic endpoints remain reachable even through tunnels
    r_ping = client.get("/ping", headers={"x-forwarded-for": "198.51.100.22"})
    assert r_ping.status_code == 200
    assert r_ping.text == "ok"

    r_health = client.get("/health", headers={"x-forwarded-for": "198.51.100.22"})
    assert r_health.status_code == 200
    assert r_health.json() == {"status": "ok"}



