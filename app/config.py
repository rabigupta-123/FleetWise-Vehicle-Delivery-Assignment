import os

from dotenv import load_dotenv

load_dotenv()


def get_db_path() -> str:
    """Return the configured SQLite database file path from environment."""
    return os.environ.get("DATABASE_PATH", "fleetwise.db")


def get_host() -> str:
    return os.environ.get("HOST", "127.0.0.1")


def get_port() -> int:
    return int(os.environ.get("PORT", "8000"))


def get_https_port() -> int:
    return int(os.environ.get("HTTPS_PORT", "8443"))


# =====================================================================
# FEATURE FLAGS (Configurable via environment variables)
# =====================================================================
def is_gps_tracking_enabled() -> bool:
    """Feature flag for real-time smartphone GPS telematics ingestion."""
    return os.environ.get("FEATURE_GPS_TRACKING", "true").lower() in ("true", "1", "yes")


def is_otp_verification_enabled() -> bool:
    """Feature flag for driver phone OTP verification challenge flows."""
    return os.environ.get("FEATURE_OTP_VERIFICATION", "true").lower() in ("true", "1", "yes")


def is_phone_verification_enabled() -> bool:
    """Feature flag for strict driver phone ownership checks."""
    return os.environ.get("FEATURE_PHONE_VERIFICATION", "true").lower() in ("true", "1", "yes")


def get_gps_retention_days() -> int:
    """Number of days to retain raw GPS location telemetry before auto-purge."""
    return int(os.environ.get("GPS_RETENTION_DAYS", "30"))


# =====================================================================
# MAP TILE SETTINGS (Configurable in .env; all libraries vendored locally)
# =====================================================================
MAP_TILE_URL: str = os.environ.get(
    "MAP_TILE_URL",
    "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
)

MAP_TILE_ATTRIBUTION: str = os.environ.get(
    "MAP_TILE_ATTRIBUTION",
    '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors',
)

# =====================================================================
# SMS PROVIDER SETTINGS (Dev mode indicator if no real provider configured)
# =====================================================================
SMS_PROVIDER: str = os.environ.get("SMS_PROVIDER", "").strip().lower()


def is_real_sms_configured() -> bool:
    """Returns True if a real SMS provider (e.g. twilio, aws_sns) is configured with credentials."""
    return SMS_PROVIDER in ("twilio", "aws_sns", "vonage") and bool(os.environ.get("SMS_API_KEY"))


# =====================================================================
# HEURISTIC CONSTANTS (Explicitly labeled as empirical heuristics)
# =====================================================================
# Exponential decay scale for GPS accuracy precision score: Q_gps = 100 * exp(-accuracy / 50.0m)
HEURISTIC_GPS_ACCURACY_DECAY_M: float = 50.0

# Exponential decay scale for telemetry freshness score: Q_freshness = 100 * exp(-age / 120.0s)
HEURISTIC_FRESHNESS_DECAY_S: float = 120.0

# Composite telemetry quality weighting coefficients (sum to 1.0)
HEURISTIC_TELEMETRY_WEIGHT_GPS: float = 0.40
HEURISTIC_TELEMETRY_WEIGHT_FRESHNESS: float = 0.30
HEURISTIC_TELEMETRY_WEIGHT_MOVEMENT: float = 0.20
HEURISTIC_TELEMETRY_WEIGHT_COMPLETENESS: float = 0.10

# Kinematic jump filter thresholds
# Speeds exceeding 50 m/s (180 km/h) are flagged as impossible kinematic anomalies for urban delivery fleet
HEURISTIC_JUMP_SPEED_MAX_MPS: float = 50.0

# Distance jumps exceeding 300 meters within 2 seconds are flagged as sensor teleport glitches
HEURISTIC_JUMP_DIST_MAX_M: float = 300.0
HEURISTIC_JUMP_TIME_MIN_S: float = 2.0

# Telemetry freshness threshold categories
# Points received within 90 seconds are considered LIVE
HEURISTIC_FRESH_THRESHOLD_S: float = 90.0

# Points between 90 and 300 seconds are STALE; beyond 300 seconds are OFFLINE
HEURISTIC_STALE_THRESHOLD_S: float = 300.0

# Rate limiting minimum interval between device location fixes per tracking session
HEURISTIC_MIN_GPS_INTERVAL_S: float = 0.5

# =====================================================================
# ACCURACY & KALMAN FILTER PIPELINE CONSTANTS (Empirical heuristics)
# =====================================================================
# Browser reported accuracy radius divisor to estimate 1-sigma standard deviation
# Android reports 68% radius (1 sigma); W3C spec specifies 95% (approx 2 sigma)
ACCURACY_SIGMA_DIVISOR: float = float(os.environ.get("ACCURACY_SIGMA_DIVISOR", "1.0"))

# Kalman filter process noise: acceleration standard deviation in m/s^2
KALMAN_SIGMA_A: float = float(os.environ.get("KALMAN_SIGMA_A", "1.5"))

# Kalman filter measurement noise minimum floor in meters
KALMAN_SIGMA_M_MIN: float = 3.0

# Outlier gating threshold (chi-square 2 DOF at 99% confidence level)
MAHALANOBIS_OUTLIER_THRESHOLD: float = 9.21

# Stationary position freeze thresholds
STATIONARY_SPEED_THRESHOLD_MPS: float = 0.5
STATIONARY_DURATION_MIN_S: float = 10.0

# Heading calculation minimum speed in m/s
HEADING_MIN_SPEED_MPS: float = 1.0

# Geofence arrival defaults
GEOFENCE_RADIUS_M: float = float(os.environ.get("GEOFENCE_RADIUS_M", "50.0"))
GEOFENCE_CONFIDENCE_THRESHOLD: float = 0.90
GEOFENCE_SUSTAINED_S: float = 20.0

# Route factor and ETA calculations
ROUTE_FACTOR: float = float(os.environ.get("ROUTE_FACTOR", "1.3"))
ETA_SPEED_FLOOR_KMH: float = 5.0
ETA_EWMA_ALPHA: float = 0.20

# Demo location defaults
DEMO_CENTER_LAT: float = float(os.environ.get("DEMO_CENTER_LAT", "12.9716"))
DEMO_CENTER_LON: float = float(os.environ.get("DEMO_CENTER_LON", "77.5946"))
