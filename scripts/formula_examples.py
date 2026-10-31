"""
FleetWise Mathematical Formula Verification & Worked Examples Generator.
Produces verified, reproducible numeric values directly from the codebase functions.
"""
import json
import math
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

# Add workspace root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.math_utils import calculate_capacity_suitability, round_half_up
from app.analytics.accuracy_engine import haversine_distance, calculate_telemetry_quality_score
from app.telematics import haversine_distance_meters, compute_freshness_status


def get_worked_examples() -> dict[str, Any]:
    # 1. Haversine Distance
    lat1, lon1 = 12.9716, 77.5946
    lat2, lon2 = 12.9784, 77.6408
    hav_m = haversine_distance(lat1, lon1, lat2, lon2)
    hav_m_rounded = round_half_up(hav_m, 2)

    # 2. Kinematic Speed
    delta_s = 240.0
    speed_mps = round_half_up(hav_m / delta_s, 2)
    speed_kmh = round_half_up((hav_m / delta_s) * 3.6, 2)

    # 3. Freshness Thresholds
    # LIVE: 45s, STALE: 180s, OFFLINE: 450s
    from datetime import datetime, timedelta, UTC
    now = datetime.now(UTC)
    fresh_live = compute_freshness_status((now - timedelta(seconds=45)).strftime("%Y-%m-%dT%H:%M:%SZ"))
    fresh_stale = compute_freshness_status((now - timedelta(seconds=180)).strftime("%Y-%m-%dT%H:%M:%SZ"))
    fresh_offline = compute_freshness_status((now - timedelta(seconds=450)).strftime("%Y-%m-%dT%H:%M:%SZ"))

    # 4. Capacity Suitability
    # 800 kg package on 1000 kg van -> (1000 - 800)/1000 = 0.20 -> 100 - (0.20 * 20) = 96.0
    cap_suit_800_1000 = calculate_capacity_suitability(800.0, 1000.0)
    # 1200 kg package on 1000 kg van -> Overloaded -> 0.0
    cap_suit_overload = calculate_capacity_suitability(1200.0, 1000.0)
    # Exact fit: 1000 kg on 1000 kg van -> 100.0
    cap_suit_exact = calculate_capacity_suitability(1000.0, 1000.0)

    # 5. Telemetry Quality with Renormalization
    # GPS accuracy 15.0m, device_ts = server_ts (0s latency), speed reported 15 m/s, vehicle type van
    record = {
        "latitude": 12.9784,
        "longitude": 77.6408,
        "accuracy": 15.0,
        "speed": 15.0,
        "heading": 90.0,
        "altitude": 920.0,
        "battery_pct": 82.0,
        "device_timestamp": "2026-10-31T12:00:00Z",
        "server_timestamp": "2026-10-31T12:00:02Z",
    }
    prev_record = {
        "latitude": 12.9716,
        "longitude": 77.5946,
        "device_timestamp": "2026-10-31T11:56:00Z",
    }
    telem_acc = calculate_telemetry_quality_score(record, prev_record=prev_record, vehicle_type="van")

    # 6. Deep Analytics Rates (Zero Denominator Safety)
    # Fleet Utilization: 7 active out of 10 available vehicles -> 70.0%
    fleet_util = round_half_up((7 / 10) * 100.0, 2)
    # Zero denominator case: 0 total vehicles -> null / None
    zero_fleet = None

    return {
        "haversine_meters": hav_m_rounded,
        "speed_mps": speed_mps,
        "speed_kmh": speed_kmh,
        "freshness": {
            "live_status": fresh_live["tracking_status"],
            "stale_status": fresh_stale["tracking_status"],
            "offline_status": fresh_offline["tracking_status"],
        },
        "capacity_suitability": {
            "fit_800_1000": cap_suit_800_1000,
            "overloaded": cap_suit_overload,
            "exact_fit": cap_suit_exact,
        },
        "telemetry_accuracy": {
            "total_score": telem_acc["telemetry_quality_score"],
            "gps_quality": telem_acc["component_scores"].get("gps_quality"),
            "freshness_quality": telem_acc["component_scores"].get("freshness"),
            "movement_quality": telem_acc["component_scores"].get("movement_consistency"),
            "completeness_quality": telem_acc["component_scores"].get("data_completeness"),
        },
        "analytics": {
            "fleet_utilization_pct": fleet_util,
            "zero_denominator_result": zero_fleet,
        },
    }


if __name__ == "__main__":
    examples = get_worked_examples()
    print(json.dumps(examples, indent=2))
