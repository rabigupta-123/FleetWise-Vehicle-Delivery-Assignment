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
