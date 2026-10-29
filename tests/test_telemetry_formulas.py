import math
import pytest
from fastapi.testclient import TestClient

from app.telematics import (
    compute_freshness_status,
    evaluate_telemetry_step,
    haversine_distance_meters,
)


def test_haversine_distance_mathematical_precision():
    # Benchmark 1: London Trafalgar Square (51.5080, -0.1281) to Paris Eiffel Tower (48.8584, 2.2945)
    # Expected great-circle distance is ~343.5 km (+/- 1.5 km)
    dist_m = haversine_distance_meters(51.5080, -0.1281, 48.8584, 2.2945)
    dist_km = dist_m / 1000.0
    assert 340.0 <= dist_km <= 346.0

    # Benchmark 2: Same point has distance 0.0
    assert haversine_distance_meters(12.9716, 77.5946, 12.9716, 77.5946) == 0.0

    # Benchmark 3: Non-finite inputs raise ValueError
    with pytest.raises(ValueError):
        haversine_distance_meters(float("nan"), 77.0, 12.0, 77.0)


def test_telemetry_step_kinematics_and_jump_detection():
    # Step 1: Normal vehicle velocity (15 m/s = 54 km/h) over 10 seconds = 150m
    # Start: (12.8400, 77.6600), End ~ (12.84135, 77.6600)
    res_normal = evaluate_telemetry_step(
        prev_lat=12.8400,
        prev_lon=77.6600,
        prev_timestamp_iso="2026-10-29T12:00:00Z",
        curr_lat=12.84135,
        curr_lon=77.6600,
        curr_timestamp_iso="2026-10-29T12:00:10Z",
        reported_speed_mps=15.0,
    )
    assert res_normal["is_implausible_jump"] == 0
    assert res_normal["quality_flag"] == "accepted"
    assert res_normal["derived_speed_kmh"] is not None
    assert 40.0 <= res_normal["derived_speed_kmh"] <= 65.0

    # Step 2: Teleportation / Implausible Jump: 5 km in 2 seconds (> 2500 m/s = 9000 km/h)
    res_jump = evaluate_telemetry_step(
        prev_lat=12.8400,
        prev_lon=77.6600,
        prev_timestamp_iso="2026-10-29T12:00:00Z",
        curr_lat=12.8850,
        curr_lon=77.6600,
        curr_timestamp_iso="2026-10-29T12:00:02Z",
        reported_speed_mps=None,
    )
    assert res_jump["is_implausible_jump"] == 1
    assert res_jump["quality_flag"] == "flagged_jump"


def test_freshness_status_thresholds():
    # Fresh fix (< 90s)
    from datetime import datetime, timezone, timedelta
    now_utc = datetime.now(timezone.utc)

    fresh_ts = (now_utc - timedelta(seconds=20)).strftime("%Y-%m-%dT%H:%M:%SZ")
    res_fresh = compute_freshness_status(fresh_ts)
    assert res_fresh["tracking_status"] == "live"
    assert res_fresh["is_live"] is True

    # Stale fix (between 90s and 300s)
    stale_ts = (now_utc - timedelta(seconds=120)).strftime("%Y-%m-%dT%H:%M:%SZ")
    res_stale = compute_freshness_status(stale_ts)
    assert res_stale["tracking_status"] == "stale"
    assert res_stale["is_stale"] is True

    # Offline fix (> 300s)
    offline_ts = (now_utc - timedelta(seconds=600)).strftime("%Y-%m-%dT%H:%M:%SZ")
    res_offline = compute_freshness_status(offline_ts)
    assert res_offline["tracking_status"] == "offline"
    assert res_offline["is_offline"] is True


def test_gps_ingestion_rate_limiting_and_dual_aliased_telemetry(client: TestClient, temp_db: str):
    # Setup driver & session
    client.post("/drivers", json={"driver_id": "DR-KIN-01", "name": "Kinematics Driver", "phone": "+91-9876543210"})
    res_sess = client.post("/tracking/sessions/start", json={"driver_id": "DR-KIN-01"})
    sess_id = res_sess.json()["session_id"]

    # 1. Ingest initial point
    p1 = {
        "session_id": sess_id,
        "latitude": 12.9716,
        "longitude": 77.5946,
        "accuracy": 5.0,
        "device_timestamp": "2026-10-29T12:00:00Z",
    }
    assert client.post("/tracking/location", json=p1).status_code == 201

    # 2. Ingest rapid duplicate device_timestamp (< 0.8s) -> 429 RATE_LIMITED
    p_rapid = {
        "session_id": sess_id,
        "latitude": 12.9717,
        "longitude": 77.5947,
        "accuracy": 5.0,
        "device_timestamp": "2026-10-29T12:00:00Z",
    }
    res_rapid = client.post("/tracking/location", json=p_rapid)
    assert res_rapid.status_code == 429
    assert res_rapid.json()["error"] == "RATE_LIMITED"

    # 3. Ingest next valid point 2 seconds later
    p2 = {
        "session_id": sess_id,
        "latitude": 12.9720,
        "longitude": 77.5950,
        "accuracy": 5.0,
        "device_timestamp": "2026-10-29T12:00:02Z",
    }
    res_p2 = client.post("/tracking/location", json=p2)
    assert res_p2.status_code == 201
    assert res_p2.json()["quality_flag"] == "accepted"
    assert res_p2.json()["is_implausible_jump"] is False

    # 4. Check dual-aliased telemetry graph response keys
    res_graph = client.get(f"/tracking/telemetry-graph?session_id={sess_id}")
    assert res_graph.status_code == 200
    g = res_graph.json()
    assert "data_points" in g
    assert "points" in g
    assert "point_count" in g
    assert "points_count" in g
    assert g["point_count"] == 2
    assert g["points_count"] == 2
    assert len(g["points"]) == 2
    assert len(g["data_points"]) == 2

