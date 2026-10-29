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
    availability_status TEXT NOT NULL DEFAULT 'available' CHECK (availability_status IN ('available', 'assigned', 'unavailable'))
);

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
    vehicle_id TEXT NULL REFERENCES vehicles(vehicle_id),
    delivery_id TEXT NULL REFERENCES deliveries(delivery_id),
    device_info TEXT NULL,
    started_at TEXT NOT NULL,
    stopped_at TEXT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'stopped', 'stale'))
);

CREATE TABLE IF NOT EXISTS gps_locations (
    location_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES tracking_sessions(session_id),
    driver_id TEXT NOT NULL REFERENCES drivers(driver_id),
    vehicle_id TEXT NULL REFERENCES vehicles(vehicle_id),
    delivery_id TEXT NULL REFERENCES deliveries(delivery_id),
    latitude REAL NOT NULL CHECK (latitude >= -90.0 AND latitude <= 90.0),
    longitude REAL NOT NULL CHECK (longitude >= -180.0 AND longitude <= 180.0),
    accuracy REAL NOT NULL CHECK (accuracy >= 0),
    speed REAL NULL,
    heading REAL NULL,
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
    finally:
        conn.close()


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
