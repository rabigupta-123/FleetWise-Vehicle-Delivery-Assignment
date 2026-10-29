import math
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import phonenumbers
from phonenumbers import carrier, geocoder, number_type


# Earth mean radius in meters (WGS 84 / IUGG)
EARTH_RADIUS_METERS = 6371000.0
MAX_PLAUSIBLE_SPEED_MPS = 50.0  # 180 km/h: upper threshold for road fleet movements
FRESH_THRESHOLD_SECONDS = 90
STALE_THRESHOLD_SECONDS = 300


def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Computes great-circle surface distance between two WGS-84 coordinates in meters.
    Formula:
        a = sin²(Δφ/2) + cos(φ1) * cos(φ2) * sin²(Δλ/2)
        c = 2 * atan2(√a, √(1−a))
        d = R * c
    """
    if not (math.isfinite(lat1) and math.isfinite(lon1) and math.isfinite(lat2) and math.isfinite(lon2)):
        raise ValueError("Coordinates must be finite numeric values")

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2) + math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2)
    # Clamp to [0, 1] against numerical floating-point inaccuracies
    a = min(1.0, max(0.0, a))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return EARTH_RADIUS_METERS * c


def evaluate_telemetry_step(
    prev_lat: float,
    prev_lon: float,
    prev_timestamp_iso: str,
    curr_lat: float,
    curr_lon: float,
    curr_timestamp_iso: str,
    reported_speed_mps: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Evaluates step kinematics between consecutive GPS fixes:
    Computes distance, time delta, derived speed, and detects physical jump outliers.
    """
    dist_m = haversine_distance_meters(prev_lat, prev_lon, curr_lat, curr_lon)

    t1 = datetime.fromisoformat(prev_timestamp_iso.replace("Z", "+00:00"))
    t2 = datetime.fromisoformat(curr_timestamp_iso.replace("Z", "+00:00"))
    delta_s = (t2 - t1).total_seconds()

    derived_speed_mps: Optional[float] = None
    if delta_s > 0.0:
        derived_speed_mps = dist_m / delta_s

    # Implausible jump detection
    is_jump = False
    effective_speed = reported_speed_mps if reported_speed_mps is not None else derived_speed_mps

    if effective_speed is not None and effective_speed > MAX_PLAUSIBLE_SPEED_MPS:
        is_jump = True
    elif delta_s < 2.0 and dist_m > 300.0:  # >300m in <2s = >150 m/s
        is_jump = True

    return {
        "distance_m": round(dist_m, 2),
        "time_delta_s": round(delta_s, 2),
        "derived_speed_mps": round(derived_speed_mps, 2) if derived_speed_mps is not None else None,
        "derived_speed_kmh": round(derived_speed_mps * 3.6, 1) if derived_speed_mps is not None else None,
        "is_implausible_jump": 1 if is_jump else 0,
        "quality_flag": "flagged_jump" if is_jump else "accepted",
    }


def compute_freshness_status(server_timestamp_iso: str) -> Dict[str, Any]:
    """
    Evaluates location freshness according to server receive time:
    age_seconds = max(0, server_now - server_received_at)
    """
    try:
        ts = datetime.fromisoformat(server_timestamp_iso.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        age_s = max(0.0, (now - ts).total_seconds())
    except Exception:
        return {"age_seconds": None, "tracking_status": "offline"}

    if age_s <= FRESH_THRESHOLD_SECONDS:
        status = "live"
    elif age_s <= STALE_THRESHOLD_SECONDS:
        status = "stale"
    else:
        status = "offline"

    return {
        "age_seconds": round(age_s, 1),
        "tracking_status": status,
        "is_live": status == "live",
        "is_stale": status == "stale",
        "is_offline": status == "offline",
    }


def normalize_phone_number(raw_phone: str, default_region: str = "IN") -> Dict[str, Any]:
    """
    Normalizes a phone string into standard E.164 format and extracts numbering metadata.
    Does NOT infer device GPS or carrier subscriber identity.
    """
    if not raw_phone or not isinstance(raw_phone, str):
        return {
            "is_valid": False,
            "raw_phone": raw_phone,
            "phone_e164": None,
            "country_code": None,
            "region": None,
            "carrier_name": None,
            "error": "Phone number cannot be empty",
        }

    cleaned = raw_phone.strip()
    try:
        parsed = phonenumbers.parse(cleaned, default_region)
        is_valid = phonenumbers.is_valid_number(parsed)
        if not is_valid:
            # Fallback to possible check
            is_possible = phonenumbers.is_possible_number(parsed)
            if not is_possible:
                return {
                    "is_valid": False,
                    "raw_phone": raw_phone,
                    "phone_e164": None,
                    "country_code": None,
                    "region": None,
                    "carrier_name": None,
                    "error": f"Phone number '{raw_phone}' is not a valid international or regional format",
                }

        e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        region = geocoder.region_code_for_number(parsed)
        carrier_name = carrier.name_for_number(parsed, "en") or None

        return {
            "is_valid": True,
            "raw_phone": raw_phone,
            "phone_e164": e164,
            "country_code": str(parsed.country_code),
            "region": region,
            "carrier_name": carrier_name,
            "error": None,
        }
    except Exception as exc:
        return {
            "is_valid": False,
            "raw_phone": raw_phone,
            "phone_e164": None,
            "country_code": None,
            "region": None,
            "carrier_name": None,
            "error": f"Failed to parse phone number: {str(exc)}",
        }
