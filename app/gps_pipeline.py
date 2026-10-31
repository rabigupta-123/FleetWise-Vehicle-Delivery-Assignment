"""
FleetWise — Real-GPS Processing Pipeline & Mathematical Analytics.
Provides:
1. Equirectangular local coordinate projection.
2. 2D Constant-Velocity Kalman Filter with Mahalanobis outlier gating.
3. Stationary position freeze (anti-jitter).
4. Circular-mean heading calculation.
5. Analytical position confidence probability.
6. Rigorous geofence arrival detection with confidence threshold.
7. Exponentially Weighted Moving Average (EWMA) ETA and route progress.
8. Composite telemetry confidence scoring with hard-constraint gates.
All tuning constants sourced from app.config heuristics.
"""
import math
from typing import Any

from app.config import (
    ACCURACY_SIGMA_DIVISOR,
    ETA_EWMA_ALPHA,
    ETA_SPEED_FLOOR_KMH,
    GEOFENCE_CONFIDENCE_THRESHOLD,
    GEOFENCE_RADIUS_M,
    GEOFENCE_SUSTAINED_S,
    HEADING_MIN_SPEED_MPS,
    HEURISTIC_GPS_ACCURACY_DECAY_M,
    KALMAN_SIGMA_A,
    KALMAN_SIGMA_M_MIN,
    MAHALANOBIS_OUTLIER_THRESHOLD,
    ROUTE_FACTOR,
    STATIONARY_SPEED_THRESHOLD_MPS,
)

EARTH_RADIUS_M = 6371000.0


# =============================================================================
# 1. LOCAL PROJECTION
# =============================================================================
def equirectangular_project(lat: float, lon: float, lat0: float, lon0: float) -> tuple[float, float]:
    """
    Projects spherical GPS (lat, lon) onto local Cartesian plane (x, y) centered at (lat0, lon0).
    x = R * (lon - lon0) * cos(lat0)
    y = R * (lat - lat0)
    Units: meters.
    """
    phi0 = math.radians(lat0)
    phi = math.radians(lat)
    lam0 = math.radians(lon0)
    lam = math.radians(lon)

    x = EARTH_RADIUS_M * (lam - lam0) * math.cos(phi0)
    y = EARTH_RADIUS_M * (phi - phi0)
    return x, y


def inv_equirectangular_project(x: float, y: float, lat0: float, lon0: float) -> tuple[float, float]:
    """Inverse projection from local Cartesian (x, y) in meters back to (lat, lon) in degrees."""
    phi0 = math.radians(lat0)
    cos_phi0 = math.cos(phi0)
    if abs(cos_phi0) < 1e-9:
        cos_phi0 = 1e-9

    phi = math.radians(lat0) + (y / EARTH_RADIUS_M)
    lam = math.radians(lon0) + (x / (EARTH_RADIUS_M * cos_phi0))
    return math.degrees(phi), math.degrees(lam)


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates great-circle distance between two GPS fixes in meters."""
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = (math.sin(dp / 2.0) ** 2) + math.cos(p1) * math.cos(p2) * (math.sin(dl / 2.0) ** 2)
    a = min(1.0, max(0.0, a))
    return 2.0 * EARTH_RADIUS_M * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


# =============================================================================
# 2. 2D CONSTANT-VELOCITY KALMAN FILTER WITH OUTLIER GATING
# =============================================================================
class KalmanFilter2D:
    """
    2D Constant-Velocity Kalman Filter for GPS smoothing and outlier gating.
    State vector: [x, y, vx, vy]^T in local projection meters and m/s.
    Covariance P: 4x4 matrix.
    """

    def __init__(self, init_x: float = 0.0, init_y: float = 0.0, init_accuracy: float = 10.0):
        self.state = [init_x, init_y, 0.0, 0.0]
        # Initial covariance: position variance from accuracy; high initial velocity uncertainty
        pos_var = max((init_accuracy / ACCURACY_SIGMA_DIVISOR) ** 2, 9.0)
        self.P = [
            [pos_var, 0.0, 0.0, 0.0],
            [0.0, pos_var, 0.0, 0.0],
            [0.0, 0.0, 25.0, 0.0],  # 5 m/s uncertainty
            [0.0, 0.0, 0.0, 25.0],
        ]

    def predict(self, dt: float) -> None:
        """Predicts state and covariance forward by dt seconds."""
        if dt <= 0.0:
            return

        dt = min(dt, 10.0)  # Bound time step to prevent covariance blowup
        x, y, vx, vy = self.state

        # State transition: F = [[1,0,dt,0],[0,1,0,dt],[0,0,1,0],[0,0,0,1]]
        new_x = x + vx * dt
        new_y = y + vy * dt
        self.state = [new_x, new_y, vx, vy]

        # Process noise Q with continuous acceleration noise sigma_a
        sa2 = KALMAN_SIGMA_A ** 2
        dt2 = dt * dt
        dt3 = dt2 * dt
        dt4 = dt3 * dt

        q_pos = 0.25 * dt4 * sa2
        q_pos_vel = 0.5 * dt3 * sa2
        q_vel = dt2 * sa2

        # P' = F * P * F^T + Q
        p = self.P
        # Compute F * P
        fp = [
            [p[0][0] + dt * p[2][0], p[0][1] + dt * p[2][1], p[0][2] + dt * p[2][2], p[0][3] + dt * p[2][3]],
            [p[1][0] + dt * p[3][0], p[1][1] + dt * p[3][1], p[1][2] + dt * p[3][2], p[1][3] + dt * p[3][3]],
            [p[2][0], p[2][1], p[2][2], p[2][3]],
            [p[3][0], p[3][1], p[3][2], p[3][3]],
        ]
        # Compute (F * P) * F^T + Q
        self.P = [
            [fp[0][0] + dt * fp[0][2] + q_pos, fp[0][1] + dt * fp[0][3], fp[0][2] + q_pos_vel, fp[0][3]],
            [fp[1][0] + dt * fp[1][2], fp[1][1] + dt * fp[1][3] + q_pos, fp[1][2], fp[1][3] + q_pos_vel],
            [fp[2][0] + dt * fp[2][2] + q_pos_vel, fp[2][1] + dt * fp[2][3], fp[2][2] + q_vel, fp[2][3]],
            [fp[3][0] + dt * fp[3][2], fp[3][1] + dt * fp[3][3] + q_pos_vel, fp[3][2], fp[3][3] + q_vel],
        ]

    def update(self, z_x: float, z_y: float, accuracy_m: float) -> tuple[float, float, float, float, bool, float, float]:
        """
        Updates filter with raw measurement (z_x, z_y) and accuracy.
        Performs Mahalanobis distance outlier gating.
        Returns (filtered_x, filtered_y, filtered_vx, filtered_vy, is_gated, mahalanobis_d2, sigma_pos).
        """
        sigma_m = max(accuracy_m / ACCURACY_SIGMA_DIVISOR, KALMAN_SIGMA_M_MIN)
        R_val = sigma_m ** 2

        # Innovation: y = z - H * s'
        y_x = z_x - self.state[0]
        y_y = z_y - self.state[1]

        # Innovation covariance: S = H * P * H^T + R
        S_xx = self.P[0][0] + R_val
        S_xy = self.P[0][1]
        S_yx = self.P[1][0]
        S_yy = self.P[1][1] + R_val

        det_S = S_xx * S_yy - S_xy * S_yx
        if det_S <= 1e-9:
            det_S = 1e-9

        # Inverse of S (2x2)
        inv_S_xx = S_yy / det_S
        inv_S_xy = -S_xy / det_S
        inv_S_yx = -S_yx / det_S
        inv_S_yy = S_xx / det_S

        # Mahalanobis distance squared: d^2 = y^T * S^-1 * y
        d2 = y_x * (inv_S_xx * y_x + inv_S_xy * y_y) + y_y * (inv_S_yx * y_x + inv_S_yy * y_y)

        # Current position standard deviation: sigma_pos = sqrt((P_xx + P_yy) / 2)
        sigma_pos = math.sqrt(max(0.0, (self.P[0][0] + self.P[1][1]) / 2.0))

        # Outlier Gate: Chi-square with 2 degrees of freedom at 99% is 9.21
        if d2 > MAHALANOBIS_OUTLIER_THRESHOLD:
            # Gated: reject position update, inflate covariance slightly to allow recovery
            self.P[0][0] += 5.0
            self.P[1][1] += 5.0
            return self.state[0], self.state[1], self.state[2], self.state[3], True, round(d2, 2), round(sigma_pos, 2)

        # Kalman Gain: K = P' * H^T * S^-1 (4x2)
        # H^T has 1 at (0,0) and (1,1)
        K00 = self.P[0][0] * inv_S_xx + self.P[0][1] * inv_S_yx
        K01 = self.P[0][0] * inv_S_xy + self.P[0][1] * inv_S_yy

        K10 = self.P[1][0] * inv_S_xx + self.P[1][1] * inv_S_yx
        K11 = self.P[1][0] * inv_S_xy + self.P[1][1] * inv_S_yy

        K20 = self.P[2][0] * inv_S_xx + self.P[2][1] * inv_S_yx
        K21 = self.P[2][0] * inv_S_xy + self.P[2][1] * inv_S_yy

        K30 = self.P[3][0] * inv_S_xx + self.P[3][1] * inv_S_yx
        K31 = self.P[3][0] * inv_S_xy + self.P[3][1] * inv_S_yy

        # State update: s = s' + K * y
        self.state[0] += K00 * y_x + K01 * y_y
        self.state[1] += K10 * y_x + K11 * y_y
        self.state[2] += K20 * y_x + K21 * y_y
        self.state[3] += K30 * y_x + K31 * y_y

        # Covariance update: P = (I - K * H) * P' (Joseph form or simple I - KH)
        # I - KH has row i subtracted by K_i0 * P_row0 + K_i1 * P_row1
        P_orig = [row[:] for row in self.P]
        for i in range(4):
            k_i0 = [K00, K10, K20, K30][i]
            k_i1 = [K01, K11, K21, K31][i]
            for j in range(4):
                self.P[i][j] = P_orig[i][j] - (k_i0 * P_orig[0][j] + k_i1 * P_orig[1][j])

        # Recalculate sigma_pos after measurement update
        sigma_pos = math.sqrt(max(0.0, (self.P[0][0] + self.P[1][1]) / 2.0))
        return self.state[0], self.state[1], self.state[2], self.state[3], False, round(d2, 2), round(sigma_pos, 2)


# =============================================================================
# 3. STATIONARY DETECTION & POSITION FREEZE
# =============================================================================
def detect_stationary_condition(
    recent_speeds_mps: list[float],
    displacement_from_anchor_m: float,
    reported_accuracy_m: float,
    speed_threshold: float = STATIONARY_SPEED_THRESHOLD_MPS,
) -> bool:
    """
    Detects if vehicle/phone is stationary:
    1. Filtered speeds across the window are all < 0.5 m/s.
    2. Displacement from anchor point is strictly below reported accuracy radius.
    When true, freeze position to anchor point to prevent GPS jitter.
    """
    if not recent_speeds_mps or len(recent_speeds_mps) < 3:
        return False

    all_speeds_sub = all(s < speed_threshold for s in recent_speeds_mps)
    under_accuracy = displacement_from_anchor_m < max(reported_accuracy_m, 5.0)
    return all_speeds_sub and under_accuracy


# =============================================================================
# 4. CIRCULAR-MEAN HEADING CALCULATION
# =============================================================================
def calculate_circular_mean_heading(
    headings_deg: list[float],
    speeds_mps: list[float],
    min_speed_mps: float = HEADING_MIN_SPEED_MPS,
) -> float | None:
    """
    Calculates speed-weighted circular mean heading:
    theta_bar = atan2(sum(w * sin(theta)), sum(w * cos(theta)))
    Ignores samples where speed is below 1.0 m/s (heading is erratic/undefined when stationary).
    Returns degrees in [0, 360) or None if no moving samples.
    """
    sum_sin = 0.0
    sum_cos = 0.0
    total_w = 0.0

    for h, v in zip(headings_deg, speeds_mps, strict=False):
        if v is not None and v >= min_speed_mps and h is not None and math.isfinite(h):
            rad = math.radians(h % 360.0)
            weight = max(v, 0.1)
            sum_sin += weight * math.sin(rad)
            sum_cos += weight * math.cos(rad)
            total_w += weight

    if total_w <= 0.0:
        return None

    mean_rad = math.atan2(sum_sin, sum_cos)
    mean_deg = math.degrees(mean_rad) % 360.0
    return round(mean_deg, 1)


# =============================================================================
# 5. ANALYTICAL POSITION CONFIDENCE
# =============================================================================
def calculate_position_confidence(sigma_pos: float, radius_m: float) -> float:
    """
    Probability that the true position lies within radius r of the estimate:
    C_pos(r) = 1 - exp(-r^2 / (2 * sigma_pos^2))
    Domain: [0.0, 1.0]. Returns 0.0 if sigma_pos <= 0 or radius_m <= 0.
    """
    if sigma_pos <= 0.0 or not math.isfinite(sigma_pos):
        return 0.0
    if radius_m <= 0.0:
        return 0.0

    exp_term = -(radius_m ** 2) / (2.0 * (sigma_pos ** 2))
    prob = 1.0 - math.exp(exp_term)
    return max(0.0, min(1.0, prob))


# =============================================================================
# 6. GEOFENCE ARRIVAL DETECTION
# =============================================================================
def check_geofence_arrival(
    current_lat: float,
    current_lon: float,
    target_lat: float | None,
    target_lon: float | None,
    sigma_pos: float,
    radius_m: float = GEOFENCE_RADIUS_M,
    sustained_seconds: float = 0.0,
) -> tuple[bool, float, float]:
    """
    Evaluates whether vehicle has arrived at geofence:
    1. Distance d = haversine(current, target) <= radius_m (default 50m).
    2. Analytical confidence C_pos(radius_m) >= 0.90.
    3. Condition sustained for >= 20 seconds.
    Poor accuracy never produces a confident arrival.
    Returns (has_arrived, distance_m, confidence).
    """
    if target_lat is None or target_lon is None:
        return False, -1.0, 0.0

    dist = haversine_m(current_lat, current_lon, target_lat, target_lon)
    conf = calculate_position_confidence(sigma_pos, radius_m)

    within_fence = dist <= radius_m
    high_confidence = conf >= GEOFENCE_CONFIDENCE_THRESHOLD
    time_satisfied = sustained_seconds >= GEOFENCE_SUSTAINED_S

    has_arrived = within_fence and high_confidence and time_satisfied
    return has_arrived, round(dist, 1), round(conf, 3)


# =============================================================================
# 7. EWMA SPEED, ETA & ROUTE PROGRESS
# =============================================================================
def calculate_eta_and_progress(
    current_lat: float,
    current_lon: float,
    dropoff_lat: float | None,
    dropoff_lon: float | None,
    pickup_lat: float | None,
    pickup_lon: float | None,
    moving_speeds_kmh: list[float],
    sigma_pos: float = 5.0,
) -> dict[str, Any]:
    """
    Calculates remaining distance, EWMA moving speed, ETA (seconds), and route progress percentage:
    remaining = haversine * ROUTE_FACTOR (1.3)
    v_eff = EWMA(alpha=0.2) of moving speeds with 5 km/h floor
    ETA = remaining / v_eff
    Progress % = clamp(1 - remaining / total, 0, 100)
    """
    if dropoff_lat is None or dropoff_lon is None:
        return {
            "remaining_distance_m": None,
            "eta_seconds": None,
            "eta_formatted": "n/a",
            "route_progress_pct": None,
            "effective_speed_kmh": None,
            "eta_uncertainty_seconds": None,
        }

    direct_m = haversine_m(current_lat, current_lon, dropoff_lat, dropoff_lon)
    remaining_m = direct_m * ROUTE_FACTOR

    # Total route distance reference
    if pickup_lat is not None and pickup_lon is not None:
        total_m = haversine_m(pickup_lat, pickup_lon, dropoff_lat, dropoff_lon) * ROUTE_FACTOR
    else:
        total_m = remaining_m

    # Route progress % clamped to [0, 100]
    if total_m > 0.0:
        progress_pct = max(0.0, min(100.0, (1.0 - (remaining_m / max(total_m, remaining_m))) * 100.0))
    else:
        progress_pct = 100.0

    # Calculate EWMA of moving speed
    moving = [s for s in moving_speeds_kmh if s is not None and s >= ETA_SPEED_FLOOR_KMH]
    if not moving:
        return {
            "remaining_distance_m": round(remaining_m, 1),
            "eta_seconds": None,
            "eta_formatted": "n/a (stationary)",
            "route_progress_pct": round(progress_pct, 1),
            "effective_speed_kmh": None,
            "eta_uncertainty_seconds": None,
        }

    # EWMA calculation: S_t = alpha * Y_t + (1 - alpha) * S_{t-1}
    v_ewma = moving[0]
    for s in moving[1:]:
        v_ewma = ETA_EWMA_ALPHA * s + (1.0 - ETA_EWMA_ALPHA) * v_ewma

    v_eff_kmh = max(v_ewma, ETA_SPEED_FLOOR_KMH)
    v_eff_mps = v_eff_kmh / 3.6

    eta_seconds = remaining_m / v_eff_mps if v_eff_mps > 0 else None

    # Uncertainty bounds from position uncertainty
    eta_uncertainty_s = (sigma_pos * ROUTE_FACTOR) / v_eff_mps if eta_seconds and v_eff_mps > 0 else 0.0

    # Format human-readable ETA
    if eta_seconds is not None:
        if eta_seconds < 60:
            formatted = f"{int(eta_seconds)}s"
        elif eta_seconds < 3600:
            mins = int(eta_seconds / 60)
            formatted = f"{mins} min"
        else:
            hours = int(eta_seconds / 3600)
            mins = int((eta_seconds % 3600) / 60)
            formatted = f"{hours}h {mins}m"
    else:
        formatted = "n/a"

    return {
        "remaining_distance_m": round(remaining_m, 1),
        "eta_seconds": round(eta_seconds, 1) if eta_seconds else None,
        "eta_formatted": formatted,
        "route_progress_pct": round(progress_pct, 1),
        "effective_speed_kmh": round(v_eff_kmh, 1),
        "eta_uncertainty_seconds": round(eta_uncertainty_s, 1),
    }


# =============================================================================
# 8. COMPOSITE TELEMETRY CONFIDENCE (WITH HARD GATES)
# =============================================================================
def calculate_composite_telemetry_confidence(
    accuracy_m: float | None,
    server_age_s: float | None,
    movement_consistency_score: float | None,
    data_completeness_score: float | None,
    is_revoked: bool = False,
    is_jump_anomaly: bool = False,
) -> dict[str, Any]:
    """
    Computes composite telemetry confidence score in [0.0, 100.0].
    Hard Constraint Violations immediately yield score 0.0:
    - Revoked token/device
    - Stale location > 300 seconds
    - Impossible kinematic jump
    """
    hard_violations = []
    if is_revoked:
        hard_violations.append("Device/Token is revoked")
    if server_age_s is not None and server_age_s > 300.0:
        hard_violations.append(f"Telemetry is stale ({round(server_age_s, 1)}s > 300s threshold)")
    if is_jump_anomaly:
        hard_violations.append("Kinematic jump anomaly detected")

    if hard_violations:
        return {
            "confidence_score": 0.0,
            "level": "ZERO",
            "is_valid": False,
            "hard_constraint_violations": hard_violations,
            "explanation": f"Rejected by operational hard constraints: {'; '.join(hard_violations)}.",
            "components": {},
            "weights": {},
        }

    components = {}
    weights = {}

    # 1. GPS Quality Score
    if accuracy_m is not None and math.isfinite(accuracy_m) and accuracy_m >= 0:
        q_gps = 100.0 * math.exp(-accuracy_m / HEURISTIC_GPS_ACCURACY_DECAY_M)
        components["q_gps"] = max(0.0, min(100.0, q_gps))
        weights["q_gps"] = 0.40

    # 2. Freshness Score
    if server_age_s is not None and math.isfinite(server_age_s):
        q_fresh = 100.0 * math.exp(-max(0.0, server_age_s) / 120.0)
        components["q_freshness"] = max(0.0, min(100.0, q_fresh))
        weights["q_freshness"] = 0.30

    # 3. Movement Consistency
    if movement_consistency_score is not None and math.isfinite(movement_consistency_score):
        components["q_movement"] = max(0.0, min(100.0, movement_consistency_score))
        weights["q_movement"] = 0.20

    # 4. Data Completeness
    if data_completeness_score is not None and math.isfinite(data_completeness_score):
        components["q_completeness"] = max(0.0, min(100.0, data_completeness_score))
        weights["q_completeness"] = 0.10

    total_w = sum(weights.values())
    if total_w > 0.0:
        weighted = sum(components[k] * weights[k] for k in components) / total_w
        final_score = max(0.0, min(100.0, round(weighted, 1)))
    else:
        final_score = 0.0

    if final_score >= 80.0:
        level = "HIGH"
    elif final_score >= 50.0:
        level = "MEDIUM"
    else:
        level = "LOW"

    return {
        "confidence_score": final_score,
        "level": level,
        "is_valid": True,
        "hard_constraint_violations": [],
        "explanation": f"Composite confidence {final_score}/100 ({level}) across {len(components)} signals.",
        "components": {k: round(v, 1) for k, v in components.items()},
        "weights": {k: round(v / total_w, 2) for k, v in weights.items()} if total_w > 0 else {},
    }


def get_accuracy_quality_label(accuracy_m: float | None) -> str:
    """
    Standard quality label for raw uncapped accuracy:
    - Excellent: <= 5 m
    - Good: <= 15 m
    - Fair: <= 50 m
    - Poor: <= 100 m
    - Very poor: > 100 m
    """
    if accuracy_m is None or not math.isfinite(accuracy_m) or accuracy_m < 0:
        return "n/a"
    if accuracy_m <= 5.0:
        return "Excellent"
    if accuracy_m <= 15.0:
        return "Good"
    if accuracy_m <= 50.0:
        return "Fair"
    if accuracy_m <= 100.0:
        return "Poor"
    return "Very poor"
