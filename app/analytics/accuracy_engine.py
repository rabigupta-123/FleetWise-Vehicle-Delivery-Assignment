"""
FleetWise Telemetry Accuracy Engine (Phase Three)
Deterministic, reproducible calculations for GPS quality, location freshness,
movement consistency, data completeness, and overall telemetry quality scoring.

Formulas & Definitions:
1. GPS Quality Score:
   Score = 100 * exp(-accuracy_meters / scale_meters)
   scale_meters = 50.0 (configurable)
   Returns null if accuracy is missing, negative, or invalid.

2. Location Freshness Score:
   Score = 100 * exp(-age_seconds / tau_seconds)
   tau_seconds = 120.0 (configurable)
   Penalizes future timestamps (clock skew) and returns null on invalid dates.

3. Movement Consistency:
   Haversine distance (R = 6,371,000m) with actual timestamp difference.
   Flags impossible speed by vehicle type, negative delta, zero delta, and jumps.

4. Data Completeness:
   (present_valid_required_fields / total_required_fields) * 100.
   Required fields: session_id, latitude, longitude, accuracy, device_timestamp.

5. Telemetry Quality Score:
   Weighted combination: 0.40 * GPS + 0.30 * Freshness + 0.20 * Movement + 0.10 * Completeness.
   Renormalizes over available components.
"""
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

FORMULA_VERSION = "1.0.0"
EARTH_RADIUS_METERS = 6371000.0

# Vehicle max speeds in meters/second
VEHICLE_MAX_SPEED_MPS = {
    "bike": 22.2,   # ~80 km/h
    "scooter": 22.2,# ~80 km/h
    "van": 38.9,    # ~140 km/h
    "truck": 33.3,  # ~120 km/h
    "car": 44.4,    # ~160 km/h
    "default": 50.0 # ~180 km/h
}

REQUIRED_TELEMETRY_FIELDS = [
    "session_id",
    "latitude",
    "longitude",
    "accuracy",
    "device_timestamp",
]

OPTIONAL_TELEMETRY_FIELDS = [
    "altitude",
    "altitude_accuracy",
    "speed",
    "heading",
    "battery_level",
    "network_type",
]


def calculate_gps_quality_score(
    accuracy_meters: Optional[float],
    scale_meters: float = 50.0,
) -> Tuple[Optional[float], List[str]]:
    """
    Computes normalized GPS Quality Score:
    Score = 100 * exp(-accuracy_meters / scale_meters)
    Returns (score, flags). Returns (None, flags) if accuracy missing or invalid.
    """
    flags = []
    if accuracy_meters is None:
        flags.append("missing_accuracy")
        return None, flags

    if not isinstance(accuracy_meters, (int, float)) or not math.isfinite(accuracy_meters):
        flags.append("invalid_accuracy_not_finite")
        return None, flags

    if accuracy_meters < 0.0:
        flags.append("negative_accuracy")
        return None, flags

    if scale_meters <= 0.0:
        scale_meters = 50.0

    score = 100.0 * math.exp(-accuracy_meters / scale_meters)
    if accuracy_meters > 150.0:
        flags.append("low_accuracy_radius")
    elif accuracy_meters <= 10.0:
        flags.append("high_precision_fix")

    return round(score, 2), flags


def calculate_freshness_score(
    location_timestamp_iso: Optional[str],
    current_time_iso: Optional[str] = None,
    tau_seconds: float = 120.0,
) -> Tuple[Optional[float], List[str], Optional[float]]:
    """
    Computes location freshness decay score:
    age_seconds = current_time - location_timestamp
    Score = 100 * exp(-age_seconds / tau_seconds)
    Returns (score, flags, age_seconds).
    """
    flags = []
    if not location_timestamp_iso:
        flags.append("missing_timestamp")
        return None, flags, None

    try:
        t_loc = datetime.fromisoformat(location_timestamp_iso.replace("Z", "+00:00"))
        if current_time_iso:
            t_now = datetime.fromisoformat(current_time_iso.replace("Z", "+00:00"))
        else:
            t_now = datetime.now(timezone.utc)
        age_seconds = (t_now - t_loc).total_seconds()
    except Exception:
        flags.append("unparseable_timestamp")
        return None, flags, None

    if tau_seconds <= 0.0:
        tau_seconds = 120.0

    # Handle future timestamps and severe clock skew
    if age_seconds < -300.0:
        flags.append("severe_future_clock_skew")
        return 0.0, flags, round(age_seconds, 2)
    elif age_seconds < 0.0:
        flags.append("mild_future_clock_skew")
        # Penalize future timestamps: cannot receive 100
        score = 100.0 * math.exp(-abs(age_seconds) / 60.0)
        return round(score, 2), flags, round(age_seconds, 2)

    score = 100.0 * math.exp(-age_seconds / tau_seconds)
    if age_seconds > 300.0:
        flags.append("stale_location")
    elif age_seconds <= 30.0:
        flags.append("realtime_fresh")

    return round(score, 2), flags, round(age_seconds, 2)


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates surface distance in meters using the standard Haversine formula."""
    if not (math.isfinite(lat1) and math.isfinite(lon1) and math.isfinite(lat2) and math.isfinite(lon2)):
        raise ValueError("Coordinates must be finite numbers")

    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)

    a = (math.sin(dp / 2.0) ** 2) + math.cos(p1) * math.cos(p2) * (math.sin(dl / 2.0) ** 2)
    a = min(1.0, max(0.0, a))
    return 2.0 * EARTH_RADIUS_METERS * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def calculate_movement_consistency(
    prev_lat: float,
    prev_lon: float,
    prev_ts_iso: str,
    curr_lat: float,
    curr_lon: float,
    curr_ts_iso: str,
    vehicle_type: str = "van",
    reported_speed_mps: Optional[float] = None,
    reported_accuracy_m: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Evaluates kinematic consistency between consecutive GPS fixes.
    Returns distance, time delta, speed, consistency score (0-100), and anomaly flags.
    """
    flags = []
    dist_m = haversine_distance(prev_lat, prev_lon, curr_lat, curr_lon)

    try:
        t1 = datetime.fromisoformat(prev_ts_iso.replace("Z", "+00:00"))
        t2 = datetime.fromisoformat(curr_ts_iso.replace("Z", "+00:00"))
        delta_s = (t2 - t1).total_seconds()
    except Exception:
        flags.append("invalid_timestamp_diff")
        return {
            "consistency_score": None,
            "distance_m": round(dist_m, 2),
            "delta_s": None,
            "derived_speed_mps": None,
            "derived_speed_kmh": None,
            "flags": flags,
            "is_implausible": False,
        }

    # 1. Negative elapsed time (out-of-order)
    if delta_s < 0.0:
        flags.append("negative_elapsed_time")
        flags.append("out_of_order")
        return {
            "consistency_score": 0.0,
            "distance_m": round(dist_m, 2),
            "delta_s": round(delta_s, 2),
            "derived_speed_mps": None,
            "derived_speed_kmh": None,
            "flags": flags,
            "is_implausible": True,
        }

    # 2. Zero elapsed time
    if delta_s == 0.0:
        flags.append("zero_elapsed_time")
        if dist_m < 1.0:
            flags.append("duplicate_point")
            return {
                "consistency_score": 100.0,
                "distance_m": round(dist_m, 2),
                "delta_s": 0.0,
                "derived_speed_mps": 0.0,
                "derived_speed_kmh": 0.0,
                "flags": flags,
                "is_implausible": False,
            }
        else:
            flags.append("impossible_zero_delta_displacement")
            return {
                "consistency_score": 0.0,
                "distance_m": round(dist_m, 2),
                "delta_s": 0.0,
                "derived_speed_mps": None,
                "derived_speed_kmh": None,
                "flags": flags,
                "is_implausible": True,
            }

    derived_speed_mps = dist_m / delta_s
    derived_speed_kmh = derived_speed_mps * 3.6
    effective_speed_mps = reported_speed_mps if reported_speed_mps is not None else derived_speed_mps

    max_speed_mps = VEHICLE_MAX_SPEED_MPS.get(vehicle_type.lower(), VEHICLE_MAX_SPEED_MPS["default"])
    is_implausible = False

    # 3. Impossible speed check
    if effective_speed_mps > max_speed_mps:
        flags.append("impossible_speed")
        is_implausible = True
    elif delta_s < 2.0 and dist_m > 300.0:
        flags.append("large_jump")
        is_implausible = True

    if reported_accuracy_m is not None and reported_accuracy_m > 150.0:
        flags.append("excessive_accuracy_radius")

    # Score calculation
    if is_implausible:
        score = max(0.0, 100.0 - (effective_speed_mps - max_speed_mps) * 2.0)
    else:
        score = 100.0

    return {
        "consistency_score": round(score, 2),
        "distance_m": round(dist_m, 2),
        "delta_s": round(delta_s, 2),
        "derived_speed_mps": round(derived_speed_mps, 2),
        "derived_speed_kmh": round(derived_speed_kmh, 1),
        "max_speed_mps_threshold": max_speed_mps,
        "flags": flags,
        "is_implausible": is_implausible,
    }


def calculate_data_completeness(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluates telemetry data completeness:
    (present_valid_required_fields / total_required_fields) * 100
    Also reports optional completeness.
    """
    valid_req = 0
    missing_req = []

    for f in REQUIRED_TELEMETRY_FIELDS:
        val = record.get(f)
        if val is not None and val != "":
            if f in ("latitude", "longitude", "accuracy") and not isinstance(val, (int, float)):
                missing_req.append(f)
            else:
                valid_req += 1
        else:
            missing_req.append(f)

    score = (valid_req / len(REQUIRED_TELEMETRY_FIELDS)) * 100.0

    valid_opt = 0
    present_opt = []
    for f in OPTIONAL_TELEMETRY_FIELDS:
        val = record.get(f)
        if val is not None and val != "":
            valid_opt += 1
            present_opt.append(f)

    optional_ratio = (valid_opt / len(OPTIONAL_TELEMETRY_FIELDS)) * 100.0

    return {
        "completeness_score": round(score, 2),
        "required_fields_total": len(REQUIRED_TELEMETRY_FIELDS),
        "required_fields_present": valid_req,
        "missing_required_fields": missing_req,
        "optional_fields_present": present_opt,
        "optional_completeness_pct": round(optional_ratio, 2),
    }


def calculate_telemetry_quality_score(
    record: Dict[str, Any],
    prev_record: Optional[Dict[str, Any]] = None,
    vehicle_type: str = "van",
    scale_meters: float = 50.0,
    tau_seconds: float = 120.0,
) -> Dict[str, Any]:
    """
    Computes overall Telemetry Quality Score using transparent weighted components:
    - 0.40 * GPS Quality
    - 0.30 * Freshness
    - 0.20 * Movement Consistency
    - 0.10 * Data Completeness
    Renormalizes over available components.
    """
    components = {}
    weights = {}
    flags = []

    # 1. GPS Quality
    accuracy = record.get("accuracy")
    gps_score, gps_flags = calculate_gps_quality_score(accuracy, scale_meters=scale_meters)
    flags.extend(gps_flags)
    if gps_score is not None:
        components["gps_quality"] = gps_score
        weights["gps_quality"] = 0.40

    # 2. Location Freshness
    loc_ts = record.get("device_timestamp") or record.get("server_timestamp")
    fresh_score, fresh_flags, age_s = calculate_freshness_score(loc_ts, tau_seconds=tau_seconds)
    flags.extend(fresh_flags)
    if fresh_score is not None:
        components["freshness"] = fresh_score
        weights["freshness"] = 0.30

    # 3. Movement Consistency
    kin_data = None
    if prev_record and all(k in prev_record for k in ("latitude", "longitude", "device_timestamp")) and \
       all(k in record for k in ("latitude", "longitude", "device_timestamp")):
        kin_data = calculate_movement_consistency(
            prev_record["latitude"],
            prev_record["longitude"],
            prev_record["device_timestamp"],
            record["latitude"],
            record["longitude"],
            record["device_timestamp"],
            vehicle_type=vehicle_type,
            reported_speed_mps=record.get("speed"),
            reported_accuracy_m=record.get("accuracy"),
        )
        flags.extend(kin_data["flags"])
        if kin_data["consistency_score"] is not None:
            components["movement_consistency"] = kin_data["consistency_score"]
            weights["movement_consistency"] = 0.20

    # 4. Data Completeness
    comp_data = calculate_data_completeness(record)
    components["data_completeness"] = comp_data["completeness_score"]
    weights["data_completeness"] = 0.10
    if comp_data["missing_required_fields"]:
        flags.append(f"missing_fields_{len(comp_data['missing_required_fields'])}")

    # Renormalization over available components
    total_weight = sum(weights.values())
    if total_weight > 0.0:
        weighted_sum = sum(components[k] * weights[k] for k in components)
        overall_score = round(weighted_sum / total_weight, 2)
    else:
        overall_score = None

    return {
        "telemetry_quality_score": overall_score,
        "component_scores": components,
        "component_weights": weights,
        "available_components": list(components.keys()),
        "missing_components": [k for k in ("gps_quality", "freshness", "movement_consistency", "data_completeness") if k not in components],
        "quality_flags": list(set(flags)),
        "kinematics": kin_data,
        "completeness": comp_data,
        "calculation_timestamp": datetime.now(timezone.utc).isoformat(),
        "formula_version": FORMULA_VERSION,
        "label": "Telemetry Quality Score",
        "description": "Weighted heuristic combining GPS accuracy, freshness decay, kinematic consistency, and completeness.",
    }

