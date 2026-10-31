"""
FleetWise — Automated Tests for GPS Processing Pipeline & Mathematical Invariants.
Verifies:
1. Equirectangular projection and inverse projection mathematical precision.
2. 2D Constant-velocity Kalman Filter with Mahalanobis outlier gating (d^2 > 9.21).
3. Stationary condition freeze when speed < 0.5 m/s.
4. Circular-mean heading around modular boundary (350° and 10° -> 0°).
5. Analytical position confidence formula: C_pos(r) = 1 - exp(-r^2 / (2 * sigma^2)).
6. Geofence arrival: distance <= 50m, confidence >= 0.90, sustained >= 20s.
7. EWMA ETA and route progress percentage.
8. Property-based tests verifying all confidence scores are strictly clamped to [0.0, 100.0].
"""
import math
import random

from app.gps_pipeline import (
    KalmanFilter2D,
    calculate_circular_mean_heading,
    calculate_composite_telemetry_confidence,
    calculate_eta_and_progress,
    calculate_position_confidence,
    check_geofence_arrival,
    detect_stationary_condition,
    equirectangular_project,
    get_accuracy_quality_label,
    inv_equirectangular_project,
)


def test_equirectangular_projection_roundtrip():
    lat0, lon0 = 12.9716, 77.5946
    # Offset by ~500 meters
    target_lat, target_lon = 12.9760, 77.5990

    x, y = equirectangular_project(target_lat, target_lon, lat0, lon0)
    recovered_lat, recovered_lon = inv_equirectangular_project(x, y, lat0, lon0)

    assert math.isclose(target_lat, recovered_lat, abs_tol=1e-6)
    assert math.isclose(target_lon, recovered_lon, abs_tol=1e-6)


def test_kalman_filter_gating_and_smoothing():
    kf = KalmanFilter2D(init_x=0.0, init_y=0.0, init_accuracy=5.0)

    # 1. Normal plausible update along x-axis
    kf.predict(dt=1.0)
    fx, fy, vx, vy, is_gated, d2, sig_pos = kf.update(10.0, 0.0, accuracy_m=5.0)
    assert not is_gated
    assert d2 <= 9.21
    assert fx > 0.0
    assert vx > 0.0

    # 2. Extreme impossible outlier jump (10,000 meters in 1 second)
    kf.predict(dt=1.0)
    fx2, fy2, vx2, vy2, is_gated2, d2_outlier, sig_pos2 = kf.update(10000.0, 5000.0, accuracy_m=5.0)
    assert is_gated2 is True
    assert d2_outlier > 9.21
    # Outlier rejected: state does not jump to 10,000m
    assert fx2 < 50.0


def test_stationary_freeze():
    # Speeds sub 0.5 m/s and within accuracy radius -> stationary
    is_stat = detect_stationary_condition([0.2, 0.3, 0.1], displacement_from_anchor_m=2.0, reported_accuracy_m=5.0)
    assert is_stat is True

    # Moving speeds -> not stationary
    is_stat2 = detect_stationary_condition([5.0, 6.0, 7.0], displacement_from_anchor_m=20.0, reported_accuracy_m=5.0)
    assert is_stat2 is False


def test_circular_mean_heading_boundary():
    # Average of 350° and 10° across the 0° wrap-around
    mean_hdg = calculate_circular_mean_heading([350.0, 10.0], [5.0, 5.0])
    assert mean_hdg is not None
    assert math.isclose(mean_hdg, 0.0, abs_tol=0.1) or math.isclose(mean_hdg, 360.0, abs_tol=0.1)

    # Simple cardinal average (80° and 100° -> 90°)
    mean_east = calculate_circular_mean_heading([80.0, 100.0], [5.0, 5.0])
    assert mean_east is not None
    assert math.isclose(mean_east, 90.0, abs_tol=0.1)


def test_analytical_position_confidence():
    # If accuracy is very high (sigma = 3m), probability of being within 10m is near 1.0
    c_high = calculate_position_confidence(sigma_pos=3.0, radius_m=10.0)
    assert c_high > 0.99

    # If accuracy is degraded (sigma = 50m), probability of being within 10m is very small
    c_low = calculate_position_confidence(sigma_pos=50.0, radius_m=10.0)
    assert 0.0 < c_low < 0.10

    # Boundaries
    assert calculate_position_confidence(sigma_pos=0.0, radius_m=10.0) == 0.0
    assert calculate_position_confidence(sigma_pos=10.0, radius_m=0.0) == 0.0


def test_geofence_arrival_criteria():
    target_lat, target_lon = 12.9716, 77.5946

    # 1. Inside fence (10m away), high confidence (sigma=3m), sustained 25s -> ARRIVED
    arrived, dist, conf = check_geofence_arrival(
        12.97168, 77.5946, target_lat, target_lon,
        sigma_pos=3.0, radius_m=50.0, sustained_seconds=25.0,
    )
    assert arrived is True
    assert dist <= 50.0
    assert conf >= 0.90

    # 2. Inside fence distance but low confidence (sigma=80m) -> NOT ARRIVED
    arrived_low_conf, _, conf_bad = check_geofence_arrival(
        12.97168, 77.5946, target_lat, target_lon,
        sigma_pos=80.0, radius_m=50.0, sustained_seconds=30.0,
    )
    assert arrived_low_conf is False
    assert conf_bad < 0.90

    # 3. Inside fence and high confidence, but sustained duration only 5s (< 20s required) -> NOT ARRIVED
    arrived_brief, _, _ = check_geofence_arrival(
        12.97168, 77.5946, target_lat, target_lon,
        sigma_pos=3.0, radius_m=50.0, sustained_seconds=5.0,
    )
    assert arrived_brief is False


def test_eta_and_route_progress():
    p_lat, p_lon = 12.9000, 77.5000
    d_lat, d_lon = 12.9500, 77.5500
    # Midway point
    curr_lat, curr_lon = 12.9250, 77.5250

    res = calculate_eta_and_progress(
        curr_lat, curr_lon, d_lat, d_lon, p_lat, p_lon,
        moving_speeds_kmh=[30.0, 35.0, 40.0],
        sigma_pos=4.0,
    )
    assert res["remaining_distance_m"] > 0.0
    assert res["eta_seconds"] > 0
    assert 40.0 <= res["route_progress_pct"] <= 60.0
    assert res["eta_uncertainty_seconds"] is not None


def test_accuracy_quality_tiers():
    assert get_accuracy_quality_label(3.5) == "Excellent"
    assert get_accuracy_quality_label(12.0) == "Good"
    assert get_accuracy_quality_label(35.0) == "Fair"
    assert get_accuracy_quality_label(75.0) == "Poor"
    assert get_accuracy_quality_label(150.0) == "Very poor"
    assert get_accuracy_quality_label(None) == "n/a"


def test_property_based_confidence_and_quality_score_clamping():
    """Property test: for 100 randomized inputs, composite score is strictly within [0.0, 100.0]."""
    for _ in range(100):
        raw_acc = random.uniform(0.1, 500.0)
        freshness_s = random.uniform(0.0, 3600.0)
        jump_flag = random.choice([True, False])
        revoked_flag = random.choice([True, False])

        res = calculate_composite_telemetry_confidence(
            accuracy_m=raw_acc,
            server_age_s=freshness_s,
            movement_consistency_score=random.uniform(0.0, 100.0),
            data_completeness_score=random.uniform(0.0, 100.0),
            is_revoked=revoked_flag,
            is_jump_anomaly=jump_flag,
        )

        score = res["confidence_score"]
        assert 0.0 <= score <= 100.0, f"Composite score {score} out of bounds for acc={raw_acc}"
        assert res["level"] in ("ZERO", "HIGH", "MEDIUM", "LOW", "DEGRADED")
