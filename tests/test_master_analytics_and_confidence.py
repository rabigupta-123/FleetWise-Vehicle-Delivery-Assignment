"""
FleetWise Automated Tests — Master Security Hardening, Accuracy Engine,
Confidence Engine, Deep Analytics, and SOC Endpoints (Phase Ten).
"""
import pytest
from starlette.testclient import TestClient

from app.analytics.accuracy_engine import (
    calculate_data_completeness,
    calculate_freshness_score,
    calculate_gps_quality_score,
    calculate_movement_consistency,
    calculate_telemetry_quality_score,
)
from app.analytics.confidence_engine import (
    evaluate_assignment_confidence,
    evaluate_device_identity_confidence,
    evaluate_location_confidence,
)


# =========================================================================
# 1. ACCURACY ENGINE TESTS
# =========================================================================
def test_accuracy_engine_gps_score_calculations():
    # 5m: ~90.5
    s5, f5 = calculate_gps_quality_score(5.0)
    assert round(s5, 1) == 90.5
    assert "high_precision_fix" in f5

    # 10m: ~81.9
    s10, _ = calculate_gps_quality_score(10.0)
    assert round(s10, 1) == 81.9

    # 25m: ~60.7
    s25, _ = calculate_gps_quality_score(25.0)
    assert 60.5 <= s25 <= 60.8

    # 50m: ~36.8
    s50, _ = calculate_gps_quality_score(50.0)
    assert round(s50, 1) == 36.8

    # 100m: ~13.5
    s100, f100 = calculate_gps_quality_score(100.0)
    assert round(s100, 1) == 13.5

    # Boundary: Missing / None -> returns null
    s_none, f_none = calculate_gps_quality_score(None)
    assert s_none is None
    assert "missing_accuracy" in f_none

    # Boundary: Negative accuracy -> returns null
    s_neg, f_neg = calculate_gps_quality_score(-5.0)
    assert s_neg is None
    assert "negative_accuracy" in f_neg

    # High accuracy radius flag (>150m)
    s160, f160 = calculate_gps_quality_score(160.0)
    assert "low_accuracy_radius" in f160


def test_accuracy_engine_freshness_score():
    # Current fix -> ~100
    s_now, f_now, age_now = calculate_freshness_score("2026-10-30T12:00:00Z", current_time_iso="2026-10-30T12:00:00Z")
    assert s_now == 100.0
    assert age_now == 0.0

    # 120s decay (tau = 120s) -> 100 * exp(-1) = 36.79
    s_120, _, age_120 = calculate_freshness_score("2026-10-30T12:00:00Z", current_time_iso="2026-10-30T12:02:00Z")
    assert round(s_120, 1) == 36.8
    assert age_120 == 120.0

    # Future timestamp (clock skew 30s ahead): penalized, cannot receive 100
    s_fut, f_fut, age_fut = calculate_freshness_score("2026-10-30T12:00:30Z", current_time_iso="2026-10-30T12:00:00Z")
    assert s_fut < 100.0
    assert "mild_future_clock_skew" in f_fut

    # Severe future timestamp (>5m): score = 0.0
    s_sev, f_sev, _ = calculate_freshness_score("2026-10-30T12:10:00Z", current_time_iso="2026-10-30T12:00:00Z")
    assert s_sev == 0.0
    assert "severe_future_clock_skew" in f_sev


def test_accuracy_engine_movement_consistency():
    # Normal movement: 100m displacement in 10s = 10 m/s (36 km/h) -> Score 100
    res = calculate_movement_consistency(
        12.9716, 77.5946, "2026-10-30T12:00:00Z",
        12.9725, 77.5946, "2026-10-30T12:00:10Z",
        vehicle_type="van",
    )
    assert res["consistency_score"] == 100.0
    assert res["is_implausible"] is False
    assert res["derived_speed_kmh"] > 0

    # Impossible speed: ~930m in 2s = 465 m/s > 38.9 m/s van limit
    res_jump = calculate_movement_consistency(
        12.9716, 77.5946, "2026-10-30T12:00:00Z",
        12.9800, 77.5946, "2026-10-30T12:00:02Z",
        vehicle_type="van",
    )
    assert res_jump["is_implausible"] is True
    assert "impossible_speed" in res_jump["flags"]

    # Negative elapsed time (out-of-order)
    res_neg = calculate_movement_consistency(
        12.9716, 77.5946, "2026-10-30T12:00:10Z",
        12.9720, 77.5946, "2026-10-30T12:00:00Z",
    )
    assert res_neg["consistency_score"] == 0.0
    assert "negative_elapsed_time" in res_neg["flags"]

    # Zero elapsed time duplicate point (same location)
    res_dup = calculate_movement_consistency(
        12.9716, 77.5946, "2026-10-30T12:00:00Z",
        12.9716, 77.5946, "2026-10-30T12:00:00Z",
    )
    assert res_dup["consistency_score"] == 100.0
    assert "duplicate_point" in res_dup["flags"]


def test_accuracy_engine_completeness_and_overall_score():
    record = {
        "session_id": "SES-1",
        "latitude": 12.9716,
        "longitude": 77.5946,
        "accuracy": 8.0,
        "device_timestamp": "2026-10-30T12:00:00Z",
        "speed": 12.0,
    }
    comp = calculate_data_completeness(record)
    assert comp["completeness_score"] == 100.0
    assert len(comp["missing_required_fields"]) == 0

    quality = calculate_telemetry_quality_score(record)
    assert quality["telemetry_quality_score"] is not None
    assert quality["label"] == "Telemetry Quality Score"
    assert "gps_quality" in quality["component_scores"]
    assert "data_completeness" in quality["component_scores"]


# =========================================================================
# 2. CONFIDENCE ENGINE TESTS
# =========================================================================
def test_confidence_engine_device_identity():
    # HIGH: Auth + registered + persistent token + phone verified
    res_high = evaluate_device_identity_confidence(
        is_authenticated=True,
        has_registered_device=True,
        is_revoked=False,
        token_type="client_storage_token",
        phone_verified=True,
        driver_id_match=True,
    )
    assert res_high["level"] == "HIGH"
    assert res_high["confidence_score"] == 100.0
    assert res_high["is_trusted"] is True

    # Revoked: Strictly 0.0 and LOW
    res_rev = evaluate_device_identity_confidence(
        is_authenticated=True,
        has_registered_device=True,
        is_revoked=True,
    )
    assert res_rev["level"] == "LOW"
    assert res_rev["confidence_score"] == 0.0
    assert res_rev["is_trusted"] is False

    # Driver mismatch: Strictly 0.0 and LOW
    res_mis = evaluate_device_identity_confidence(
        is_authenticated=True,
        has_registered_device=True,
        is_revoked=False,
        driver_id_match=False,
    )
    assert res_mis["level"] == "LOW"
    assert res_mis["confidence_score"] == 0.0


def test_confidence_engine_location_confidence():
    # Strong location evidence
    res_strong = evaluate_location_confidence(
        gps_quality_score=90.0,
        freshness_score=95.0,
        movement_consistency_score=100.0,
        distinct_observations_count=6,
        data_completeness_pct=100.0,
        has_jump_anomaly=False,
    )
    assert res_strong["level"] == "HIGH"
    assert res_strong["confidence_score"] >= 80.0

    # Contradictory jump anomaly severely penalizes score
    res_jump = evaluate_location_confidence(
        gps_quality_score=90.0,
        freshness_score=95.0,
        movement_consistency_score=20.0,
        distinct_observations_count=6,
        data_completeness_pct=100.0,
        has_jump_anomaly=True,
    )
    assert "Kinematic step exceeds maximum plausible speed" in res_jump["contradictory_evidence"][0]
    assert res_jump["confidence_score"] < res_strong["confidence_score"]


def test_confidence_engine_assignment_hard_constraints():
    # Eligible assignment
    res_el = evaluate_assignment_confidence(
        vehicle={"vehicle_id": "V-1", "status": "available", "capacity": 1000},
        driver={"driver_id": "DR-1", "availability_status": "available", "phone_verification_status": "verified"},
        delivery={"delivery_id": "D-1", "status": "pending", "package_weight": 600},
    )
    assert res_el["is_eligible"] is True
    assert res_el["confidence_score"] >= 80.0

    # Hard Constraint Failure: Insufficient capacity
    res_over = evaluate_assignment_confidence(
        vehicle={"vehicle_id": "V-1", "status": "available", "capacity": 500},
        driver={"driver_id": "DR-1", "availability_status": "available"},
        delivery={"delivery_id": "D-1", "status": "pending", "package_weight": 800},
    )
    assert res_over["is_eligible"] is False
    assert res_over["confidence_score"] == 0.0
    assert res_over["level"] == "REJECTED"
    assert any("Insufficient capacity" in v for v in res_over["hard_constraint_violations"])

    # Hard Constraint Failure: Vehicle already assigned/occupied
    res_occ = evaluate_assignment_confidence(
        vehicle={"vehicle_id": "V-1", "status": "available", "capacity": 1000},
        driver={"driver_id": "DR-1", "availability_status": "available"},
        delivery={"delivery_id": "D-1", "status": "pending", "package_weight": 200},
        has_active_vehicle_assignment=True,
    )
    assert res_occ["is_eligible"] is False
    assert res_occ["level"] == "REJECTED"


# =========================================================================
# 3. DEEP ANALYTICS API ENDPOINTS
# =========================================================================
def test_deep_analytics_api_endpoints(client: TestClient, temp_db: str):
    # Setup test fixtures
    client.post("/vehicles", json={"vehicle_id": "V-DEEP-1", "registration_no": "KA-01-DP-1001", "capacity": 1200})
    client.post("/drivers", json={"driver_id": "DR-DEEP-1", "name": "Deep Tester", "phone": "+91-9876543201"})
    client.post("/deliveries", json={"delivery_id": "D-DEEP-1", "pickup": "Depot A", "dropoff": "Hub B", "package_weight": 350, "priority": "high"})

    # 1. GET /analytics/overview
    r_ov = client.get("/analytics/overview")
    assert r_ov.status_code == 200
    ov_data = r_ov.json()
    assert "fleet" in ov_data
    assert "drivers" in ov_data
    assert "deliveries" in ov_data
    assert "fleet_utilization_pct" in ov_data["fleet"]

    # 2. GET /analytics/fleet
    r_flt = client.get("/analytics/fleet")
    assert r_flt.status_code == 200
    flt_data = r_flt.json()
    assert "utilization" in flt_data
    assert "vehicles" in flt_data
    assert any(v["vehicle_id"] == "V-DEEP-1" for v in flt_data["vehicles"])

    # 3. GET /analytics/drivers
    r_drv = client.get("/analytics/drivers")
    assert r_drv.status_code == 200
    drv_data = r_drv.json()
    assert "utilization" in drv_data
    assert "drivers" in drv_data
    assert any(d["driver_id"] == "DR-DEEP-1" for d in drv_data["drivers"])

    # 4. GET /analytics/deliveries
    r_del = client.get("/analytics/deliveries")
    assert r_del.status_code == 200
    del_data = r_del.json()
    assert "completion_rate_pct" in del_data
    assert "on_time_rate_pct" in del_data

    # 5. GET /analytics/telemetry
    r_tel = client.get("/analytics/telemetry")
    assert r_tel.status_code == 200
    assert "summary" in r_tel.json()

    # 6. GET /analytics/accuracy
    r_acc = client.get("/analytics/accuracy")
    assert r_acc.status_code == 200
    assert "formula_description" in r_acc.json()

    # 7. GET /analytics/confidence
    r_conf = client.get("/analytics/confidence")
    assert r_conf.status_code == 200
    assert "label" in r_conf.json()

    # 8. GET /analytics/anomalies
    r_anom = client.get("/analytics/anomalies")
    assert r_anom.status_code == 200
    assert "anomalies" in r_anom.json()

    # 9. GET /analytics/vehicles/{id} (Valid & 404)
    r_v = client.get("/analytics/vehicles/V-DEEP-1")
    assert r_v.status_code == 200
    assert r_v.json()["vehicle_id"] == "V-DEEP-1"

    r_v_404 = client.get("/analytics/vehicles/V-NONEXISTENT")
    assert r_v_404.status_code == 404

    # 10. GET /analytics/drivers/{id} (Valid & 404)
    r_d = client.get("/analytics/drivers/DR-DEEP-1")
    assert r_d.status_code == 200
    assert r_d.json()["driver_id"] == "DR-DEEP-1"

    r_d_404 = client.get("/analytics/drivers/DR-NONEXISTENT")
    assert r_d_404.status_code == 404
