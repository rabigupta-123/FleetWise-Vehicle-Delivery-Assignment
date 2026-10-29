import pytest
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
