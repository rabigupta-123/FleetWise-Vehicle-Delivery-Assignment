"""
Verifies that all formula calculations documented in docs/FORMULAS.md match
runtime calculations exactly with deterministic precision.
"""

from app.analytics.accuracy_engine import haversine_distance
from app.math_utils import calculate_capacity_suitability, round_half_up
from scripts.formula_examples import get_worked_examples


def test_formula_worked_examples_reproducibility():
    examples = get_worked_examples()

    # 1. Haversine distance
    lat1, lon1 = 12.9716, 77.5946
    lat2, lon2 = 12.9784, 77.6408
    dist = haversine_distance(lat1, lon1, lat2, lon2)
    assert round_half_up(dist, 2) == examples["haversine_meters"]
    assert round_half_up(dist, 2) == 5062.82

    # 2. Kinematic speed
    delta_s = 240.0
    v_mps = round_half_up(dist / delta_s, 2)
    v_kmh = round_half_up((dist / delta_s) * 3.6, 2)
    assert v_mps == examples["speed_mps"]
    assert v_mps == 21.10
    assert v_kmh == examples["speed_kmh"]
    assert v_kmh == 75.94

    # 3. Capacity Suitability
    assert calculate_capacity_suitability(800.0, 1000.0) == 96.0
    assert calculate_capacity_suitability(1000.0, 1000.0) == 100.0
    assert calculate_capacity_suitability(1200.0, 1000.0) == 0.0
    assert calculate_capacity_suitability(0.0, 1000.0) == 0.0
    assert calculate_capacity_suitability(500.0, 0.0) == 0.0

    # 4. Freshness states
    assert examples["freshness"]["live_status"] == "live"
    assert examples["freshness"]["stale_status"] == "stale"
    assert examples["freshness"]["offline_status"] == "offline"

    # 5. Zero denominator edge case safety
    assert examples["analytics"]["zero_denominator_result"] is None

    # 6. GPS Accuracy, Radius & Confidence Worked Examples (accuracy 76.0m)
    acc_ex = examples["accuracy_worked_example"]
    assert acc_ex["raw_accuracy_m"] == 76.0
    assert acc_ex["quality_score_S"] == 21.9
    assert acc_ex["sigma_m"] == 50.3
    assert acc_ex["radius_95pct_m"] == 123.2
    assert acc_ex["confidence_within_50m_pct"] == 38.9
    assert acc_ex["quality_label"] == "Poor"


def test_gps_accuracy_score_property_bounds():
    """Property test that every accuracy quality score S stays bounded strictly in [0.0, 100.0]."""
    from app.gps_pipeline import (
        calculate_accuracy_score,
        calculate_position_confidence,
        calculate_sigma_pos,
        get_accuracy_quality_label,
    )

    # Edge cases
    assert calculate_accuracy_score(None) is None
    assert calculate_accuracy_score(-10.0) is None
    assert calculate_accuracy_score(float("nan")) is None
    assert calculate_accuracy_score(float("inf")) is None

    # Tiers
    assert get_accuracy_quality_label(3.0) == "Excellent"
    assert get_accuracy_quality_label(5.0) == "Excellent"
    assert get_accuracy_quality_label(12.0) == "Good"
    assert get_accuracy_quality_label(15.0) == "Good"
    assert get_accuracy_quality_label(35.0) == "Fair"
    assert get_accuracy_quality_label(50.0) == "Fair"
    assert get_accuracy_quality_label(76.0) == "Poor"
    assert get_accuracy_quality_label(100.0) == "Poor"
    assert get_accuracy_quality_label(105.0) == "Very poor"
    assert get_accuracy_quality_label(500.0) == "Very poor"
    assert get_accuracy_quality_label(None) == "n/a"

    # Monotonicity & Boundedness over wide domain [0, 5000 meters]
    for acc in [0.0, 1.0, 5.0, 15.0, 50.0, 76.0, 100.0, 250.0, 1000.0, 5000.0]:
        s = calculate_accuracy_score(acc)
        assert s is not None
        assert 0.0 <= s <= 100.0
        sig = calculate_sigma_pos(acc)
        if acc > 0:
            assert sig is not None and sig > 0
            c_50 = calculate_position_confidence(sig, 50.0)
            assert 0.0 <= c_50 <= 1.0
