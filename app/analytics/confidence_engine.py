"""
FleetWise Confidence Engine (Phase Four)
Evaluates location evidence confidence, device identity confidence, and assignment confidence.

Labels:
All scores are explicitly labeled as "Evidence Confidence Score — Heuristic".
Statistical calibration requires empirical labeled outcomes; heuristic models reflect
evidence completeness and logical constraints.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

CONFIDENCE_FORMULA_VERSION = "1.0.0"


def evaluate_device_identity_confidence(
    is_authenticated: bool,
    has_registered_device: bool,
    is_revoked: bool,
    token_type: str = "client_storage_token",
    phone_verified: bool = False,
    driver_id_match: bool = True,
) -> Dict[str, Any]:
    """
    Evaluates device identity confidence based on authenticated evidence:
    - HIGH: Authenticated driver + active registered device + persistent token + driver match.
    - MEDIUM: Registered device with ephemeral storage token or unverified phone.
    - LOW: Unverified, revoked, mismatched, or anonymous device.
    """
    supporting = []
    missing = []
    contradictory = []

    if is_revoked:
        contradictory.append("Device has been explicitly revoked by an administrator.")
        return {
            "confidence_score": 0.0,
            "level": "LOW",
            "is_trusted": False,
            "supporting_evidence": supporting,
            "missing_evidence": missing,
            "contradictory_evidence": contradictory,
            "explanation": "Device is revoked. Any telemetry or requests from this device are rejected.",
            "label": "Evidence Confidence Score — Heuristic",
            "formula_version": CONFIDENCE_FORMULA_VERSION,
        }

    if not driver_id_match:
        contradictory.append("Device is registered to a different driver ID than the session.")
        return {
            "confidence_score": 0.0,
            "level": "LOW",
            "is_trusted": False,
            "supporting_evidence": supporting,
            "missing_evidence": missing,
            "contradictory_evidence": contradictory,
            "explanation": "Driver identity mismatch detected between session and device record.",
            "label": "Evidence Confidence Score — Heuristic",
            "formula_version": CONFIDENCE_FORMULA_VERSION,
        }

    score = 0.0

    if has_registered_device:
        score += 35.0
        supporting.append("Device is registered in server-side inventory.")
    else:
        missing.append("Device is not registered in inventory.")

    if is_authenticated:
        score += 30.0
        supporting.append("Request is authenticated via signed session token.")
    else:
        missing.append("Request is unauthenticated / anonymous.")

    if token_type == "client_storage_token":
        score += 20.0
        supporting.append("Persistent client installation token verified.")
    elif token_type == "ephemeral_fallback":
        score += 5.0
        missing.append("Ephemeral private browsing token in use; reset upon tab close.")
    else:
        missing.append("Missing persistent device token.")

    if phone_verified:
        score += 15.0
        supporting.append("Associated driver phone is verified via challenge SMS/OTP.")
    else:
        missing.append("Driver phone number is unverified.")

    score = min(100.0, round(score, 1))

    if score >= 80.0:
        level = "HIGH"
        explanation = "Strong multi-factor evidence: authenticated driver, persistent registered device token, and verified phone."
    elif score >= 50.0:
        level = "MEDIUM"
        explanation = "Moderate evidence: registered device with authenticated session, but missing phone verification or using ephemeral token."
    else:
        level = "LOW"
        explanation = "Weak evidence: unverified device, anonymous session, or missing credentials."

    return {
        "confidence_score": score,
        "level": level,
        "is_trusted": score >= 50.0,
        "supporting_evidence": supporting,
        "missing_evidence": missing,
        "contradictory_evidence": contradictory,
        "explanation": explanation,
        "label": "Evidence Confidence Score — Heuristic",
        "formula_version": CONFIDENCE_FORMULA_VERSION,
    }


def evaluate_location_confidence(
    gps_quality_score: Optional[float],
    freshness_score: Optional[float],
    movement_consistency_score: Optional[float],
    distinct_observations_count: int,
    data_completeness_pct: float,
    has_jump_anomaly: bool = False,
) -> Dict[str, Any]:
    """
    Evaluates confidence in location reliability.
    Deduplicates repeated identical fixes so spamming the same coordinates does not inflate confidence.
    """
    supporting = []
    missing = []
    contradictory = []

    if has_jump_anomaly:
        contradictory.append("Kinematic step exceeds maximum plausible speed or jump threshold.")

    if gps_quality_score is not None:
        if gps_quality_score >= 80.0:
            supporting.append(f"High-precision GPS fix (score {gps_quality_score}/100).")
        elif gps_quality_score < 40.0:
            missing.append(f"Low-accuracy GPS fix (score {gps_quality_score}/100).")
    else:
        missing.append("GPS accuracy radius is unavailable.")

    if freshness_score is not None:
        if freshness_score >= 80.0:
            supporting.append(f"Fresh real-time signal (decay score {freshness_score}/100).")
        elif freshness_score < 40.0:
            missing.append(f"Stale location fix (decay score {freshness_score}/100).")
    else:
        missing.append("Signal freshness cannot be determined.")

    # Distinct observations bonus (deduplicated evidence)
    if distinct_observations_count >= 5:
        supporting.append(f"{distinct_observations_count} distinct sequential observations confirm trajectory.")
        obs_score = 100.0
    elif distinct_observations_count >= 2:
        supporting.append(f"{distinct_observations_count} sequential fixes observed.")
        obs_score = 70.0
    elif distinct_observations_count == 1:
        missing.append("Single isolated fix without trajectory history.")
        obs_score = 40.0
    else:
        missing.append("Zero valid fixes.")
        obs_score = 0.0

    # Weighting:
    # 0.35 * GPS Quality + 0.30 * Freshness + 0.20 * Movement + 0.15 * Observation Count
    weights = {}
    values = {}

    if gps_quality_score is not None:
        values["gps"] = gps_quality_score
        weights["gps"] = 0.35
    if freshness_score is not None:
        values["freshness"] = freshness_score
        weights["freshness"] = 0.30
    if movement_consistency_score is not None:
        values["movement"] = movement_consistency_score
        weights["movement"] = 0.20
    values["observations"] = obs_score
    weights["observations"] = 0.15

    total_w = sum(weights.values())
    raw_score = sum(values[k] * weights[k] for k in values) / total_w if total_w > 0 else 0.0

    # Penalize if jump anomaly
    if has_jump_anomaly:
        raw_score = max(0.0, raw_score - 40.0)

    score = round(raw_score, 1)

    if score >= 75.0 and not has_jump_anomaly:
        level = "HIGH"
    elif score >= 45.0:
        level = "MEDIUM"
    else:
        level = "LOW"

    return {
        "confidence_score": score,
        "level": level,
        "supporting_evidence": supporting,
        "missing_evidence": missing,
        "contradictory_evidence": contradictory,
        "distinct_observations_count": distinct_observations_count,
        "has_jump_anomaly": has_jump_anomaly,
        "explanation": f"Location evidence classified as {level} confidence ({score}/100).",
        "label": "Evidence Confidence Score — Heuristic",
        "formula_version": CONFIDENCE_FORMULA_VERSION,
    }


def evaluate_assignment_confidence(
    vehicle: Dict[str, Any],
    driver: Dict[str, Any],
    delivery: Dict[str, Any],
    has_active_vehicle_assignment: bool = False,
    has_active_driver_assignment: bool = False,
) -> Dict[str, Any]:
    """
    Evaluates whether a delivery assignment is valid according to strict operational constraints.
    Hard constraints fail immediately with score 0.0.
    Eligible assignments receive a transparent suitability score.
    """
    hard_violations = []
    supporting = []

    # 1. Mandatory Hard Constraints
    veh_status = (vehicle.get("status") or "").lower()
    if veh_status != "available":
        hard_violations.append(f"Vehicle '{vehicle.get('vehicle_id')}' status is '{veh_status}' (must be 'available').")

    drv_status = (driver.get("availability_status") or "").lower()
    if drv_status != "available":
        hard_violations.append(f"Driver '{driver.get('driver_id')}' availability is '{drv_status}' (must be 'available').")

    if has_active_vehicle_assignment:
        hard_violations.append(f"Vehicle '{vehicle.get('vehicle_id')}' is currently occupied by an active delivery.")

    if has_active_driver_assignment:
        hard_violations.append(f"Driver '{driver.get('driver_id')}' is currently occupied by an active delivery.")

    veh_cap = vehicle.get("capacity") or 0.0
    del_weight = delivery.get("package_weight") or 0.0
    if veh_cap < del_weight:
        hard_violations.append(f"Insufficient capacity: vehicle holds {veh_cap}kg but delivery weighs {del_weight}kg.")

    del_status = (delivery.get("status") or "").lower()
    if del_status != "pending":
        hard_violations.append(f"Delivery '{delivery.get('delivery_id')}' status is '{del_status}' (only pending deliveries can be assigned).")

    # Hard constraint rejection
    if hard_violations:
        return {
            "is_eligible": False,
            "confidence_score": 0.0,
            "level": "REJECTED",
            "hard_constraint_violations": hard_violations,
            "supporting_evidence": [],
            "explanation": "Assignment rejected due to violation of mandatory operational constraints.",
            "label": "Evidence Confidence Score — Heuristic",
            "formula_version": CONFIDENCE_FORMULA_VERSION,
        }

    # 2. Eligible Suitability Scoring
    # Capacity utilization efficiency (sweet spot 50% - 90%)
    cap_ratio = del_weight / veh_cap if veh_cap > 0 else 0.0
    if 0.5 <= cap_ratio <= 0.95:
        cap_score = 100.0
        supporting.append(f"Optimal capacity utilization: {round(cap_ratio * 100, 1)}%.")
    elif cap_ratio < 0.5:
        cap_score = 60.0 + (cap_ratio * 80.0)
        supporting.append(f"Vehicle underutilized ({round(cap_ratio * 100, 1)}% capacity).")
    else:
        cap_score = 75.0
        supporting.append("Near-maximum capacity utilization.")

    # Driver verification bonus
    drv_phone_status = driver.get("phone_verification_status") or "unverified"
    if drv_phone_status == "verified":
        drv_score = 100.0
        supporting.append("Driver identity and contact phone verified.")
    else:
        drv_score = 70.0
        supporting.append("Driver phone pending OTP verification.")

    suitability = round(0.60 * cap_score + 0.40 * drv_score, 1)

    return {
        "is_eligible": True,
        "confidence_score": suitability,
        "level": "HIGH" if suitability >= 80.0 else "MEDIUM",
        "hard_constraint_violations": [],
        "supporting_evidence": supporting,
        "capacity_utilization_pct": round(cap_ratio * 100, 1),
        "explanation": f"Assignment satisfies all hard constraints with {suitability}/100 suitability.",
        "label": "Evidence Confidence Score — Heuristic",
        "formula_version": CONFIDENCE_FORMULA_VERSION,
    }

