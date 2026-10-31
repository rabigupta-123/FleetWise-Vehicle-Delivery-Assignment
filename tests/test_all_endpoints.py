from starlette.testclient import TestClient


def test_audit_all_44_endpoints_and_status_codes(client: TestClient, temp_db: str):
    """
    Exhaustively audits all 44 endpoints listed in the system specification:
    Verifies that every endpoint returns the documented 2xx, 4xx status codes and unified envelopes.
    """

    # 1. GET / -> 200
    r = client.get("/")
    assert r.status_code == 200
    assert "FleetWise" in r.text

    # 2. GET /health -> 200
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

    # 3. GET /metrics -> 200
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "available_fleet" in r.json()

    # 4. GET /audit -> 200
    r = client.get("/audit")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

    # 5. GET /vehicles -> 200
    r = client.get("/vehicles")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

    # 6. POST /vehicles -> 201, 400, 409
    # 201 Valid
    r = client.post("/vehicles", json={"vehicle_id": "V-AUDIT-1", "registration_no": "KA-01-AU-1001", "capacity": 2000})
    assert r.status_code == 201
    assert r.json()["vehicle_id"] == "V-AUDIT-1"
    # 400 Invalid Capacity
    r = client.post("/vehicles", json={"registration_no": "KA-01-AU-1002", "capacity": -50})
    assert r.status_code == 400
    assert r.json()["error"] == "VALIDATION_ERROR"
    # 409 Duplicate Registration No
    r = client.post("/vehicles", json={"registration_no": "ka-01-au-1001", "capacity": 1500})
    assert r.status_code == 409
    assert r.json()["error"] in ("CONFLICT", "DUPLICATE")

    # 7. PATCH /vehicles/{id}/status -> 200, 404, 409
    # 200 Valid
    r = client.patch("/vehicles/V-AUDIT-1/status", json={"status": "maintenance"})
    assert r.status_code == 200
    assert r.json()["status"] == "maintenance"
    # Restore to available
    client.patch("/vehicles/V-AUDIT-1/status", json={"status": "available"})
    # 404 Nonexistent
    r = client.patch("/vehicles/V-NONEXISTENT/status", json={"status": "maintenance"})
    assert r.status_code == 404
    assert r.json()["error"] == "NOT_FOUND"

    # 8. GET /drivers -> 200
    r = client.get("/drivers")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

    # 9. POST /drivers -> 201, 400, 409
    # 201 Valid
    r = client.post("/drivers", json={"driver_id": "DR-AUDIT-1", "name": "Audit Driver", "phone": "+91-9876543210"})
    assert r.status_code == 201
    assert r.json()["driver_id"] == "DR-AUDIT-1"
    # 400 Invalid phone format
    r = client.post("/drivers", json={"name": "Bad Driver", "phone": "123"})
    assert r.status_code == 400
    assert r.json()["error"] == "VALIDATION_ERROR"
    # 409 Duplicate Driver ID
    r = client.post("/drivers", json={"driver_id": "DR-AUDIT-1", "name": "Audit Driver", "phone": "+91-9876543211"})
    assert r.status_code == 409
    assert r.json()["error"] in ("CONFLICT", "DUPLICATE")

    # 10. PATCH /drivers/{id}/status -> 200, 404, 409
    # 200 Valid
    r = client.patch("/drivers/DR-AUDIT-1/status", json={"availability_status": "unavailable"})
    assert r.status_code == 200
    assert r.json()["availability_status"] == "unavailable"
    # Restore to available
    client.patch("/drivers/DR-AUDIT-1/status", json={"availability_status": "available"})
    # 404 Nonexistent
    r = client.patch("/drivers/DR-NONEXISTENT/status", json={"availability_status": "available"})
    assert r.status_code == 404

    # 11. GET /deliveries -> 200
    r = client.get("/deliveries?status=pending&q=test")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

    # 12. POST /deliveries -> 201, 400, 409
    # 201 Valid
    r = client.post("/deliveries", json={
        "delivery_id": "D-AUDIT-1",
        "pickup": "Hub A",
        "dropoff": "Hub B",
        "scheduled_time": "2026-10-31T12:00:00Z",
        "priority": "high",
        "required_capacity": 500
    })
    assert r.status_code == 201
    assert r.json()["delivery_id"] == "D-AUDIT-1"
    # 400 Invalid ISO time
    r = client.post("/deliveries", json={
        "pickup": "Hub A",
        "dropoff": "Hub B",
        "scheduled_time": "Tomorrow at 5pm",
    })
    assert r.status_code == 400
    # 409 Duplicate Delivery ID
    r = client.post("/deliveries", json={
        "delivery_id": "D-AUDIT-1",
        "pickup": "Hub A",
        "dropoff": "Hub B",
        "scheduled_time": "2026-10-31T12:00:00Z",
    })
    assert r.status_code == 409

    # 13. POST /deliveries/{id}/assign -> 201, 400, 404, 409
    # 404 Nonexistent delivery
    r = client.post("/deliveries/D-NONEXISTENT/assign", json={"vehicle_id": "V-AUDIT-1", "driver_id": "DR-AUDIT-1"})
    assert r.status_code == 404
    # 201 Valid assignment
    r = client.post("/deliveries/D-AUDIT-1/assign", json={"vehicle_id": "V-AUDIT-1", "driver_id": "DR-AUDIT-1"})
    assert r.status_code == 201
    assert r.json()["status"] == "assigned"
    # 409 Conflict when assigning occupied vehicle/driver
    r2 = client.post("/deliveries", json={"delivery_id": "D-AUDIT-2", "pickup": "Hub A", "dropoff": "Hub C", "scheduled_time": "2026-10-31T12:00:00Z"})
    assert r2.status_code == 201
    r = client.post("/deliveries/D-AUDIT-2/assign", json={"vehicle_id": "V-AUDIT-1", "driver_id": "DR-AUDIT-1"})
    assert r.status_code == 409
    assert r.json()["error"] in ("VEHICLE_OCCUPIED", "DRIVER_OCCUPIED", "RESOURCES_UNAVAILABLE")

    # 7 & 10 (409 Guard while occupied)
    r_veh_guard = client.patch("/vehicles/V-AUDIT-1/status", json={"status": "maintenance"})
    assert r_veh_guard.status_code == 409
    assert r_veh_guard.json()["error"] in ("VEHICLE_UNAVAILABLE", "VEHICLE_OCCUPIED")

    r_drv_guard = client.patch("/drivers/DR-AUDIT-1/status", json={"availability_status": "unavailable"})
    assert r_drv_guard.status_code == 409
    assert r_drv_guard.json()["error"] in ("DRIVER_UNAVAILABLE", "DRIVER_OCCUPIED")

    # 14. PATCH /deliveries/{id}/status -> 200, 404, 409
    # 404 Nonexistent
    r = client.patch("/deliveries/D-NONEXISTENT/status", json={"status": "in_transit"})
    assert r.status_code == 404
    # 409 Invalid Transition (assigned -> delivered is invalid; must go to in_transit first)
    r = client.patch("/deliveries/D-AUDIT-1/status", json={"status": "delivered"})
    assert r.status_code == 409
    assert r.json()["error"] == "INVALID_TRANSITION"
    # 200 Valid Transition (assigned -> in_transit)
    r = client.patch("/deliveries/D-AUDIT-1/status", json={"status": "in_transit"})
    assert r.status_code == 200
    assert r.json()["status"] == "in_transit"

    # 15. GET /deliveries/{id}/recommendations -> 200, 404
    r = client.get("/deliveries/D-AUDIT-2/recommendations")
    assert r.status_code == 200
    assert "recommendations" in r.json()
    r = client.get("/deliveries/D-NONEXISTENT/recommendations")
    assert r.status_code == 404

    # 16. GET /deliveries/dispatch-next -> 200
    r = client.get("/deliveries/dispatch-next")
    assert r.status_code == 200
    assert "has_next" in r.json()

    # 17. GET /deliveries/blocked -> 200
    r = client.get("/deliveries/blocked")
    assert r.status_code == 200
    assert "blocked_deliveries" in r.json()

    # 18. POST /deliveries/auto-assign -> 200
    r = client.post("/deliveries/auto-assign?dry_run=true")
    assert r.status_code == 200
    assert r.json()["dry_run"] is True

    # 19. GET /events -> 200
    with client.stream("GET", "/events?single_ping=true") as s:
        assert s.status_code == 200
        assert "text/event-stream" in s.headers.get("content-type", "")
        for line in s.iter_lines():
            if "connected" in line:
                break

    # 20. POST /diagnostics/concurrency-test -> 200
    r = client.post("/diagnostics/concurrency-test?workers=5")
    assert r.status_code == 200
    assert r.json()["workers_dispatched"] == 5

    # 21. GET /analytics/summary -> 200
    r = client.get("/analytics/summary")
    assert r.status_code == 200
    assert "utilisation_pct" in r.json()

    # 22. GET /deliveries/routes -> 200
    r = client.get("/deliveries/routes")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

    # 23. GET /export/{entity}.csv -> 200, 404
    for ent in ["vehicles", "drivers", "deliveries", "audit"]:
        r = client.get(f"/export/{ent}.csv")
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")
    r = client.get("/export/unknown_entity.csv")
    assert r.status_code == 404

    # 24. POST /auth/login -> 200, 400, 401
    # 400 Missing username/password
    r = client.post("/auth/login", json={})
    assert r.status_code == 400
    # 401 Invalid password
    r = client.post("/auth/login", json={"username": "dispatcher", "password": "wrongpassword"})
    assert r.status_code == 401
    # 200 Valid
    r = client.post("/auth/login", json={"username": "dispatcher", "password": "DispatcherSecurePass123!"})
    assert r.status_code == 200
    assert r.json()["user"]["username"] == "dispatcher"

    # 25. GET /auth/me -> 200
    r = client.get("/auth/me")
    assert r.status_code == 200
    assert r.json()["authenticated"] is True
    assert r.json()["user"]["username"] == "dispatcher"

    # 26. POST /auth/logout -> 200
    r = client.post("/auth/logout")
    assert r.status_code == 200

    # 27. GET /import/templates/{entity}.csv -> 200, 404
    for ent in ["vehicles", "drivers", "deliveries"]:
        r = client.get(f"/import/templates/{ent}.csv")
        assert r.status_code == 200
    r = client.get("/import/templates/invalid_entity.csv")
    assert r.status_code == 404

    # 28. POST /import/{entity}?dry_run=true|false -> 200, 400
    # Dry-run 200
    csv_veh = "vehicle_id,registration_no,type,capacity,status\nV-IMP-1,KA-05-AB-9999,Van,1000,available\n"
    r = client.post("/import/vehicles?dry_run=true", files={"file": ("vehicles.csv", csv_veh, "text/csv")})
    assert r.status_code == 200
    assert r.json()["valid_rows"] == 1
    # 400 Bad entity or payload
    r = client.post("/import/invalid_entity?dry_run=true", files={"file": ("v.csv", csv_veh, "text/csv")})
    assert r.status_code == 400

    # 29. PATCH /drivers/{id}/phone -> 200, 400, 404
    # 200 Valid update
    r = client.patch("/drivers/DR-AUDIT-1/phone", json={"phone": "+91 98765 00001"})
    assert r.status_code == 200
    assert r.json()["phone_e164"] == "+919876500001"
    # 400 Invalid format
    r = client.patch("/drivers/DR-AUDIT-1/phone", json={"phone": "not-a-number"})
    assert r.status_code == 400
    # 404 Nonexistent
    r = client.patch("/drivers/DR-NONEXISTENT/phone", json={"phone": "+91 98765 00001"})
    assert r.status_code == 404

    # 30. POST /drivers/{id}/phone/request-verification -> 200, 400, 429
    # 200 Valid
    r = client.post("/drivers/DR-AUDIT-1/phone/request-verification")
    assert r.status_code == 200
    assert "verification_id" in r.json()
    ver_id = r.json()["verification_id"]
    dev_code = r.json().get("dev_challenge_code")

    # 404 Nonexistent
    r = client.post("/drivers/DR-NONEXISTENT/phone/request-verification")
    assert r.status_code == 404

    # 31. POST /drivers/{id}/phone/verify -> 200, 400
    # 400 Wrong code
    r = client.post("/drivers/DR-AUDIT-1/phone/verify", json={"verification_id": ver_id, "code": "000000"})
    assert r.status_code == 400
    # 200 Valid code
    r = client.post("/drivers/DR-AUDIT-1/phone/verify", json={"verification_id": ver_id, "code": dev_code})
    assert r.status_code == 200
    assert r.json()["verified"] is True

    # 32. POST /devices/register -> 201, 400
    # 201 Valid
    r = client.post("/devices/register", json={
        "driver_id": "DR-AUDIT-1",
        "nickname": "Audit iPhone",
        "os_family": "iOS",
        "browser_family": "Safari"
    })
    assert r.status_code == 201
    dev_id = r.json()["device_id"]
    # 400 Missing required fields
    r = client.post("/devices/register", json={"driver_id": "DR-AUDIT-1"})
    assert r.status_code == 400

    # 33. GET /devices -> 200
    r = client.get("/devices")
    assert r.status_code == 200
    assert any(d["device_id"] == dev_id for d in r.json())

    # 34. GET /devices/{device_id} -> 200, 404
    r = client.get(f"/devices/{dev_id}")
    assert r.status_code == 200
    assert r.json()["nickname"] == "Audit iPhone"
    r = client.get("/devices/DEV-NONEXISTENT")
    assert r.status_code == 404

    # 35. POST /devices/{device_id}/revoke -> 200, 404
    # Create second device to revoke
    r_dev2 = client.post("/devices/register", json={"driver_id": "DR-AUDIT-1", "nickname": "To Revoke"})
    dev2_id = r_dev2.json()["device_id"]
    r = client.post(f"/devices/{dev2_id}/revoke", json={"reason": "Audit test"})
    assert r.status_code == 200
    assert r.json()["is_revoked"] is True
    # 404 Nonexistent
    r = client.post("/devices/DEV-NONEXISTENT/revoke")
    assert r.status_code == 404

    # 36. GET /devices/{device_id}/telemetry -> 200, 404
    r = client.get(f"/devices/{dev_id}/telemetry")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    r = client.get("/devices/DEV-NONEXISTENT/telemetry")
    assert r.status_code == 404

    # 37. POST /tracking/sessions/start -> 201, 400, 404
    # 201 Valid
    r = client.post("/tracking/sessions/start", json={"driver_id": "DR-AUDIT-1", "device_id": dev_id})
    assert r.status_code == 201
    sess_id = r.json()["session_id"]
    # 404 Nonexistent driver
    r = client.post("/tracking/sessions/start", json={"driver_id": "DR-NONEXISTENT"})
    assert r.status_code == 404

    # 38. POST /tracking/sessions/stop -> 200, 400, 404
    # Create separate session on second driver to test stop
    client.post("/drivers", json={"driver_id": "DR-AUDIT-2", "name": "Driver Two", "phone": "+91-9876543299"})
    r_temp_sess = client.post("/tracking/sessions/start", json={"driver_id": "DR-AUDIT-2"})
    temp_sess_id = r_temp_sess.json()["session_id"]
    r = client.post("/tracking/sessions/stop", json={"session_id": temp_sess_id})
    assert r.status_code == 200
    # 400 Missing session_id
    r = client.post("/tracking/sessions/stop", json={})
    assert r.status_code == 400
    # 404 Nonexistent
    r = client.post("/tracking/sessions/stop", json={"session_id": "TRK-NONEXISTENT"})
    assert r.status_code == 404

    # 39. POST /tracking/location -> 201, 400
    # 201 Valid fix
    r = client.post("/tracking/location", json={
        "session_id": sess_id,
        "device_id": dev_id,
        "latitude": 12.9716,
        "longitude": 77.5946,
        "accuracy": 5.0,
        "device_timestamp": "2026-10-31T12:00:00Z"
    })
    assert r.status_code == 201
    assert r.json()["quality_flag"] == "accepted"
    # 400 Bad coordinates
    r = client.post("/tracking/location", json={
        "session_id": sess_id,
        "latitude": 999.0,
        "longitude": 77.5946
    })
    assert r.status_code == 400

    # 40. GET /tracking/drivers/{id}/latest -> 200, 404
    r = client.get("/tracking/drivers/DR-AUDIT-1/latest")
    assert r.status_code == 200
    assert r.json()["has_gps"] is True
    r = client.get("/tracking/drivers/DR-NONEXISTENT/latest")
    assert r.status_code == 404

    # 41. GET /tracking/vehicles/{id}/latest -> 200, 404
    r = client.get("/tracking/vehicles/V-AUDIT-1/latest")
    assert r.status_code == 200
    assert r.json()["has_gps"] is True
    r = client.get("/tracking/vehicles/V-NONEXISTENT/latest")
    assert r.status_code == 404

    # 42. GET /tracking/deliveries/{id}/latest -> 200, 404
    r = client.get("/tracking/deliveries/D-AUDIT-1/latest")
    assert r.status_code == 200
    assert r.json()["has_gps"] is True
    r = client.get("/tracking/deliveries/D-NONEXISTENT/latest")
    assert r.status_code == 404

    # 43. GET /tracking/history -> 200
    r = client.get("/tracking/history?vehicle_id=V-AUDIT-1")
    assert r.status_code == 200
    assert isinstance(r.json()["trail"], list)

    # 44. GET /tracking/telemetry-graph -> 200
    r = client.get("/tracking/telemetry-graph?vehicle_id=V-AUDIT-1")
    assert r.status_code == 200
    assert "data_points" in r.json()
    assert "points" in r.json()


def test_auth_enforcement_on_all_routes_when_require_auth_active(client: TestClient, monkeypatch):
    """
    Enumerates every route registered in app.routes.
    When REQUIRE_AUTH=1, asserts that all non-allowlisted routes return 401 without credentials.
    Allowlist: {/, /health, /auth/login, /probe, /static/*, /openapi.json, /docs, /redoc, /docs/oauth2-redirect}
    """
    import re

    from app.main import app

    monkeypatch.setenv("REQUIRE_AUTH", "1")
    public_allowlist = {
        "/",
        "/health",
        "/auth/login",
        "/probe",
        "/probe/report",
        "/openapi.json",
        "/docs",
        "/redoc",
        "/docs/oauth2-redirect",
    }

    tested_routes = 0
    for route in app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if not path or not methods:
            continue

        # Skip documentation and Swagger UI routes
        if path in public_allowlist or path.startswith("/static"):
            continue

        # Substitute path parameters (e.g., {delivery_id} -> test_id)
        test_path = re.sub(r"\{[^}]+\}", "test_id", path)

        # Pick one supported method to probe
        method = "GET" if "GET" in methods else ("POST" if "POST" in methods else list(methods)[0])

        if method == "GET":
            res = client.get(test_path)
        elif method == "POST":
            res = client.post(test_path, json={})
        elif method == "PATCH":
            res = client.patch(test_path, json={})
        else:
            continue

        tested_routes += 1
        assert res.status_code == 401, f"Route {method} {path} returned {res.status_code} instead of 401"
        assert res.json()["error"] == "UNAUTHORIZED"

    assert tested_routes >= 35, f"Expected at least 35 protected routes tested, got {tested_routes}"


def test_route_order_dispatch_next_and_blocked(client: TestClient, temp_db: str):
    """
    Verifies that FastAPI routes /deliveries/dispatch-next and /deliveries/blocked
    are evaluated before parameterized /deliveries/{delivery_id} routes and never treated as ID lookups.
    """
    # 1. /deliveries/dispatch-next returns 200 or 404 (no deliveries to dispatch), not a single delivery lookup
    res_dn = client.get("/deliveries/dispatch-next")
    assert res_dn.status_code in (200, 404)
    if res_dn.status_code == 200:
        data = res_dn.json()
        assert "delivery" in data or "delivery_id" in data

    # 2. /deliveries/blocked returns 200 payload with blocked_deliveries list
    res_blk = client.get("/deliveries/blocked")
    assert res_blk.status_code == 200
    data_blk = res_blk.json()
    assert "blocked_deliveries" in data_blk
    assert isinstance(data_blk["blocked_deliveries"], list)

