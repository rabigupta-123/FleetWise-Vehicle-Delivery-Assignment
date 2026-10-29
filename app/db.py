import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator, Optional

from app.config import get_db_path

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS vehicles (
    vehicle_id TEXT PRIMARY KEY,
    registration_no TEXT UNIQUE NOT NULL,
    type TEXT NOT NULL,
    capacity INTEGER NOT NULL CHECK (capacity > 0),
    status TEXT NOT NULL DEFAULT 'available' CHECK (status IN ('available', 'assigned', 'maintenance', 'inactive'))
);

CREATE TABLE IF NOT EXISTS drivers (
    driver_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT NOT NULL,
    phone_e164 TEXT NULL,
    phone_verification_status TEXT NOT NULL DEFAULT 'unverified' CHECK (phone_verification_status IN ('unverified', 'pending', 'verified', 'failed')),
    phone_carrier TEXT NULL,
    phone_country_code TEXT NULL,
    availability_status TEXT NOT NULL DEFAULT 'available' CHECK (availability_status IN ('available', 'assigned', 'unavailable'))
);

CREATE TABLE IF NOT EXISTS devices (
    device_id TEXT PRIMARY KEY,
    driver_id TEXT NOT NULL REFERENCES drivers(driver_id),
    nickname TEXT NOT NULL,
    os_family TEXT NULL,
    browser_family TEXT NULL,
    platform TEXT NULL,
    screen_res TEXT NULL,
    capabilities_json TEXT NULL,
    permission_status TEXT NOT NULL DEFAULT 'prompt',
    last_ip TEXT NULL,
    registered_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    revoked_at TEXT NULL,
    is_revoked INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_devices_driver ON devices(driver_id);

CREATE TABLE IF NOT EXISTS phone_verifications (
    verification_id TEXT PRIMARY KEY,
    driver_id TEXT NOT NULL REFERENCES drivers(driver_id),
    phone_e164 TEXT NOT NULL,
    code_hash TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    attempts_remaining INTEGER NOT NULL DEFAULT 3,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'verified', 'expired', 'failed')),
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_phone_verifications_driver ON phone_verifications(driver_id);

CREATE TABLE IF NOT EXISTS deliveries (
    delivery_id TEXT PRIMARY KEY,
    pickup TEXT NOT NULL,
    dropoff TEXT NOT NULL,
    scheduled_time TEXT NOT NULL,
    priority TEXT NOT NULL CHECK (priority IN ('low', 'normal', 'high', 'urgent')),
    required_capacity INTEGER NULL CHECK (required_capacity IS NULL OR required_capacity > 0),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'assigned', 'in_transit', 'delivered', 'cancelled')),
    created_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    pickup_lat REAL NULL,
    pickup_lng REAL NULL,
    drop_lat REAL NULL,
    drop_lng REAL NULL
);

CREATE TABLE IF NOT EXISTS assignments (
    assignment_id TEXT PRIMARY KEY,
    delivery_id TEXT NOT NULL REFERENCES deliveries(delivery_id),
    vehicle_id TEXT NOT NULL REFERENCES vehicles(vehicle_id),
    driver_id TEXT NOT NULL REFERENCES drivers(driver_id),
    assigned_at TEXT NOT NULL,
    released_at TEXT NULL,
    release_reason TEXT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    entity TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    before_json TEXT NULL,
    after_json TEXT NULL
);

CREATE TABLE IF NOT EXISTS idempotency_keys (
    key TEXT PRIMARY KEY,
    request_hash TEXT NOT NULL,
    response_status INTEGER NOT NULL,
    response_body TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('dispatcher', 'fleet_manager', 'ops_lead')),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tracking_sessions (
    session_id TEXT PRIMARY KEY,
    driver_id TEXT NOT NULL REFERENCES drivers(driver_id),
    device_id TEXT NULL REFERENCES devices(device_id),
    vehicle_id TEXT NULL REFERENCES vehicles(vehicle_id),
    delivery_id TEXT NULL REFERENCES deliveries(delivery_id),
    device_info TEXT NULL,
    started_at TEXT NOT NULL,
    stopped_at TEXT NULL,
    last_ping_at TEXT NULL,
    fix_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'stopped', 'stale'))
);

CREATE TABLE IF NOT EXISTS gps_locations (
    location_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES tracking_sessions(session_id),
    driver_id TEXT NOT NULL REFERENCES drivers(driver_id),
    device_id TEXT NULL REFERENCES devices(device_id),
    vehicle_id TEXT NULL REFERENCES vehicles(vehicle_id),
    delivery_id TEXT NULL REFERENCES deliveries(delivery_id),
    latitude REAL NOT NULL CHECK (latitude >= -90.0 AND latitude <= 90.0),
    longitude REAL NOT NULL CHECK (longitude >= -180.0 AND longitude <= 180.0),
    accuracy REAL NOT NULL CHECK (accuracy >= 0),
    speed REAL NULL,
    heading REAL NULL,
    derived_speed REAL NULL,
    speed_source TEXT NOT NULL DEFAULT 'reported' CHECK (speed_source IN ('reported', 'derived', 'none')),
    distance_from_prev_m REAL NULL,
    time_delta_prev_s REAL NULL,
    is_implausible_jump INTEGER NOT NULL DEFAULT 0,
    quality_flag TEXT NOT NULL DEFAULT 'accepted' CHECK (quality_flag IN ('accepted', 'flagged_jump', 'low_accuracy', 'stale')),
    client_ip TEXT NULL,
    device_timestamp TEXT NOT NULL,
    server_timestamp TEXT NOT NULL,
    is_valid INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_gps_driver_ts ON gps_locations(driver_id, server_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_gps_vehicle_ts ON gps_locations(vehicle_id, server_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_gps_delivery_ts ON gps_locations(delivery_id, server_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_gps_session_ts ON gps_locations(session_id, server_timestamp ASC);

CREATE UNIQUE INDEX IF NOT EXISTS idx_assignments_active_vehicle
    ON assignments(vehicle_id) WHERE released_at IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_assignments_active_driver
    ON assignments(driver_id) WHERE released_at IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_assignments_active_delivery
    ON assignments(delivery_id) WHERE released_at IS NULL;
"""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or get_db_path()
    conn = sqlite3.connect(path, timeout=30.0, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA busy_timeout = 30000;")
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        # Migrate existing tables if columns are missing
        _migrate_columns(conn)
    finally:
        conn.close()


def _migrate_columns(conn: sqlite3.Connection) -> None:
    def add_col_if_missing(table: str, col: str, col_type: str):
        info = conn.execute(f"PRAGMA table_info({table})").fetchall()
        existing_cols = {row["name"] for row in info}
        if col not in existing_cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type};")

    # Drivers
    add_col_if_missing("drivers", "phone_e164", "TEXT NULL")
    add_col_if_missing("drivers", "phone_verification_status", "TEXT NOT NULL DEFAULT 'unverified'")
    add_col_if_missing("drivers", "phone_carrier", "TEXT NULL")
    add_col_if_missing("drivers", "phone_country_code", "TEXT NULL")

    # Tracking Sessions
    add_col_if_missing("tracking_sessions", "device_id", "TEXT NULL")
    add_col_if_missing("tracking_sessions", "last_ping_at", "TEXT NULL")
    add_col_if_missing("tracking_sessions", "fix_count", "INTEGER NOT NULL DEFAULT 0")

    # GPS Locations
    add_col_if_missing("gps_locations", "device_id", "TEXT NULL")
    add_col_if_missing("gps_locations", "derived_speed", "REAL NULL")
    add_col_if_missing("gps_locations", "speed_source", "TEXT NOT NULL DEFAULT 'reported'")
    add_col_if_missing("gps_locations", "distance_from_prev_m", "REAL NULL")
    add_col_if_missing("gps_locations", "time_delta_prev_s", "REAL NULL")
    add_col_if_missing("gps_locations", "is_implausible_jump", "INTEGER NOT NULL DEFAULT 0")
    add_col_if_missing("gps_locations", "quality_flag", "TEXT NOT NULL DEFAULT 'accepted'")
    add_col_if_missing("gps_locations", "client_ip", "TEXT NULL")


@contextmanager
def read_conn(db_path: Optional[str] = None) -> Iterator[sqlite3.Connection]:
    conn = get_connection(db_path)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def immediate_transaction(db_path: Optional[str] = None) -> Iterator[sqlite3.Connection]:
    """
    Open a connection and start an explicit BEGIN IMMEDIATE transaction.
    Commits on clean exit; rolls back on any exception so zero partial updates occur.
    """
    conn = get_connection(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
            if conn.in_transaction:
                conn.execute("COMMIT")
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()


def write_audit(
    conn: sqlite3.Connection,
    *,
    actor: str = "operator",
    action: str,
    entity: str,
    entity_id: str,
    before: Optional[Any] = None,
    after: Optional[Any] = None,
) -> None:
    conn.execute(
        """
        INSERT INTO audit_log (ts, actor, action, entity, entity_id, before_json, after_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            utc_now_iso(),
            actor,
            action,
            entity,
            entity_id,
            json.dumps(before, sort_keys=True) if before is not None else None,
            json.dumps(after, sort_keys=True) if after is not None else None,
        ),
    )


def row_to_dict(row: Optional[sqlite3.Row]) -> Optional[dict[str, Any]]:
    if row is None:
        return None
    return dict(row)
