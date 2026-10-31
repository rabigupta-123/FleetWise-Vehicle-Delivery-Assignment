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
