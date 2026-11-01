import json
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

from app.clock import utc_now_iso
from app.config import get_db_path

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS vehicles (
    vehicle_id TEXT PRIMARY KEY,
    registration_no TEXT UNIQUE NOT NULL,
    type TEXT NOT NULL,
    capacity INTEGER NOT NULL CHECK (capacity > 0),
    status TEXT NOT NULL DEFAULT 'available' CHECK (status IN ('available', 'assigned', 'maintenance', 'inactive')),
    is_demo INTEGER NOT NULL DEFAULT 0,
    demo_key TEXT UNIQUE NULL
);

CREATE TABLE IF NOT EXISTS drivers (
    driver_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT NOT NULL,
    phone_e164 TEXT NULL,
    phone_verification_status TEXT NOT NULL DEFAULT 'unverified',
    phone_carrier TEXT NULL,
    phone_country_code TEXT NULL,
    availability_status TEXT NOT NULL DEFAULT 'available' CHECK (availability_status IN ('available', 'assigned', 'unavailable')),
    is_demo INTEGER NOT NULL DEFAULT 0,
    demo_key TEXT UNIQUE NULL
);

CREATE TABLE IF NOT EXISTS devices (
    device_id TEXT PRIMARY KEY,
    driver_id TEXT NOT NULL REFERENCES drivers(driver_id) ON DELETE CASCADE,
    nickname TEXT NOT NULL,
    device_category TEXT NULL,
    model TEXT NULL,
    os_family TEXT NULL,
    os_version TEXT NULL,
    browser_family TEXT NULL,
    browser_version TEXT NULL,
    platform TEXT NULL,
    screen_res TEXT NULL,
    capabilities_json TEXT NULL,
    permission_status TEXT NOT NULL DEFAULT 'prompt',
    last_ip TEXT NULL,
    registered_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    revoked_at TEXT NULL,
    is_revoked INTEGER NOT NULL DEFAULT 0,
    client_device_token TEXT NULL,
    identity_confidence TEXT NOT NULL DEFAULT 'client_storage_token',
    detection_limitations TEXT NULL
);
CREATE INDEX IF NOT EXISTS idx_devices_driver ON devices(driver_id);

CREATE TABLE IF NOT EXISTS phone_pairing_tokens (
    token TEXT PRIMARY KEY,
    driver_id TEXT NULL REFERENCES drivers(driver_id) ON DELETE CASCADE,
    device_id TEXT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    used INTEGER NOT NULL DEFAULT 0,
    revoked INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_phone_pairing_tokens_tok ON phone_pairing_tokens(token);

CREATE TABLE IF NOT EXISTS driver_sessions (
    session_token_hash TEXT PRIMARY KEY,
    driver_id TEXT NULL REFERENCES drivers(driver_id) ON DELETE CASCADE,
    device_id TEXT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_driver_sessions_hash ON driver_sessions(session_token_hash);

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
    drop_lng REAL NULL,
    is_demo INTEGER NOT NULL DEFAULT 0,
    demo_key TEXT UNIQUE NULL
);

CREATE TABLE IF NOT EXISTS assignments (
    assignment_id TEXT PRIMARY KEY,
    delivery_id TEXT NOT NULL REFERENCES deliveries(delivery_id) ON DELETE CASCADE,
    vehicle_id TEXT NOT NULL REFERENCES vehicles(vehicle_id) ON DELETE CASCADE,
    driver_id TEXT NOT NULL REFERENCES drivers(driver_id) ON DELETE CASCADE,
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

-- Phase 1.8: Enforce append-only integrity on audit_log with SQLite triggers
CREATE TRIGGER IF NOT EXISTS trg_audit_log_no_update
BEFORE UPDATE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'audit_log is append-only: UPDATE is forbidden');
END;

CREATE TRIGGER IF NOT EXISTS trg_audit_log_no_delete
BEFORE DELETE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'audit_log is append-only: DELETE is forbidden');
END;

CREATE TABLE IF NOT EXISTS device_probe_reports (
    report_id TEXT PRIMARY KEY,
    device_id TEXT NULL,
    driver_id TEXT NULL,
    token_used TEXT NULL,
    client_ip TEXT NOT NULL,
    user_agent TEXT NOT NULL,
    is_secure_context INTEGER NOT NULL,
    high_entropy_ch_json TEXT NULL,
    client_probe_json TEXT NOT NULL,
    server_probe_json TEXT NOT NULL,
    discrepancies_json TEXT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_probe_reports_created ON device_probe_reports(created_at DESC);

CREATE TABLE IF NOT EXISTS idempotency_keys (
    key TEXT PRIMARY KEY,
    request_hash TEXT NOT NULL,
    response_status INTEGER NOT NULL,
    response_body TEXT NOT NULL,
    created_at TEXT NOT NULL
);


CREATE TABLE IF NOT EXISTS tracking_sessions (
    session_id TEXT PRIMARY KEY,
    driver_id TEXT NOT NULL REFERENCES drivers(driver_id) ON DELETE CASCADE,
    device_id TEXT NULL REFERENCES devices(device_id) ON DELETE CASCADE,
    vehicle_id TEXT NULL REFERENCES vehicles(vehicle_id) ON DELETE CASCADE,
    delivery_id TEXT NULL REFERENCES deliveries(delivery_id) ON DELETE CASCADE,
    device_info TEXT NULL,
    started_at TEXT NOT NULL,
    stopped_at TEXT NULL,
    last_ping_at TEXT NULL,
    fix_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'stopped', 'stale')),
    is_demo INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS gps_locations (
    location_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES tracking_sessions(session_id) ON DELETE CASCADE,
    driver_id TEXT NOT NULL REFERENCES drivers(driver_id) ON DELETE CASCADE,
    device_id TEXT NULL REFERENCES devices(device_id) ON DELETE CASCADE,
    vehicle_id TEXT NULL REFERENCES vehicles(vehicle_id) ON DELETE CASCADE,
    delivery_id TEXT NULL REFERENCES deliveries(delivery_id) ON DELETE CASCADE,
    latitude REAL NOT NULL CHECK (latitude >= -90.0 AND latitude <= 90.0),
    longitude REAL NOT NULL CHECK (longitude >= -180.0 AND longitude <= 180.0),
    accuracy REAL NOT NULL CHECK (accuracy >= 0),
    altitude REAL NULL,
    altitude_accuracy REAL NULL,
    speed REAL NULL,
    heading REAL NULL,
    derived_speed REAL NULL,
    speed_source TEXT NOT NULL DEFAULT 'reported' CHECK (speed_source IN ('reported', 'derived', 'none')),
    distance_from_prev_m REAL NULL,
    time_delta_prev_s REAL NULL,
    is_implausible_jump INTEGER NOT NULL DEFAULT 0,
    quality_flag TEXT NOT NULL DEFAULT 'accepted' CHECK (quality_flag IN ('accepted', 'flagged_jump', 'low_accuracy', 'stale', 'out_of_order', 'duplicate', 'clock_skew_future')),
    client_ip TEXT NULL,
    device_timestamp TEXT NOT NULL,
    server_timestamp TEXT NOT NULL,
    is_valid INTEGER NOT NULL DEFAULT 1,
    filtered_latitude REAL NULL,
    filtered_longitude REAL NULL,
    filtered_speed REAL NULL,
    filtered_heading REAL NULL,
    is_gated INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'device' CHECK (source IN ('device', 'simulated')),
    kalman_sigma_pos REAL NULL,
    mahalanobis_d2 REAL NULL,
    is_demo INTEGER NOT NULL DEFAULT 0
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


def _on_connect_pragma_hook(conn: sqlite3.Connection) -> None:
    """Connection event hook ensuring foreign_keys=ON on every SQLite connection."""
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA busy_timeout = 30000;")
    fk_active = conn.execute("PRAGMA foreign_keys;").fetchone()[0]
    if fk_active != 1:
        raise RuntimeError("Failed to enable PRAGMA foreign_keys=ON on SQLite connection")


_CONNECTION_HOOKS = [_on_connect_pragma_hook]


def register_connection_hook(hook_fn) -> None:
    if hook_fn not in _CONNECTION_HOOKS:
        _CONNECTION_HOOKS.append(hook_fn)


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    path = db_path or get_db_path()
    conn = sqlite3.connect(path, timeout=30.0, isolation_level=None, check_same_thread=False)
    for hook in _CONNECTION_HOOKS:
        hook(conn)
    return conn


def init_db(db_path: str | None = None) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.executescript(SCHEMA_SQL)
        # Migrate existing tables if columns or foreign key cascades are missing
        _migrate_columns(conn)
        _migrate_cascade_foreign_keys(conn)
    finally:
        conn.close()


def _migrate_cascade_foreign_keys(conn: sqlite3.Connection) -> None:
    """Migrates existing child tables to include ON DELETE CASCADE on foreign keys."""
    import re
    child_tables = ["devices", "phone_pairing_tokens", "assignments", "tracking_sessions", "gps_locations"]
    for tbl in child_tables:
        fks = conn.execute(f"PRAGMA foreign_key_list({tbl})").fetchall()
        has_stale_ref = any("_old_fk_mig" in str(fk["table"]) for fk in fks)
        needs_migration = (
            has_stale_ref
            or (tbl == "phone_pairing_tokens" and len(fks) == 0)
            or any(fk["on_delete"].upper() != "CASCADE" for fk in fks)
        )
        if not needs_migration:
            continue

        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (tbl,)
        ).fetchone()
        if not row or not row["sql"]:
            continue

        old_sql = row["sql"]
        # Clean up any accidental _old_fk_mig references
        fixed_sql = re.sub(r'([a-zA-Z0-9_]+)_old_fk_mig"?', r"\1", old_sql)
        if tbl == "phone_pairing_tokens" and "REFERENCES" not in fixed_sql.upper():
            new_sql = fixed_sql.replace(
                "driver_id TEXT NULL",
                "driver_id TEXT NULL REFERENCES drivers(driver_id) ON DELETE CASCADE",
            )
        else:
            new_sql = re.sub(
                r"REFERENCES\s+\"?([a-zA-Z0-9_]+)\"?\s*\(([^)]+)\)(?!\s+ON\s+DELETE\s+CASCADE)",
                r"REFERENCES \1(\2) ON DELETE CASCADE",
                fixed_sql,
                flags=re.IGNORECASE,
            )

        if new_sql == old_sql:
            continue

        # Save existing indexes on this table
        idx_rows = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name=? AND sql IS NOT NULL",
            (tbl,),
        ).fetchall()
        saved_indexes = [r["sql"] for r in idx_rows]

        conn.execute("PRAGMA foreign_keys = OFF;")
        conn.execute("PRAGMA legacy_alter_table = ON;")
        try:
            conn.execute("BEGIN IMMEDIATE;")
            conn.execute(f"ALTER TABLE {tbl} RENAME TO {tbl}_old_fk_mig;")
            conn.execute(new_sql)
            cols = [c["name"] for c in conn.execute(f"PRAGMA table_info({tbl})").fetchall()]
            old_cols = {c["name"] for c in conn.execute(f"PRAGMA table_info({tbl}_old_fk_mig)").fetchall()}
            common_cols = [c for c in cols if c in old_cols]
            col_csv = ", ".join(common_cols)
            conn.execute(
                f"INSERT OR IGNORE INTO {tbl} ({col_csv}) SELECT {col_csv} FROM {tbl}_old_fk_mig;"
            )
            conn.execute(f"DROP TABLE {tbl}_old_fk_mig;")
            for idx_sql in saved_indexes:
                conn.execute(idx_sql)
            conn.execute("COMMIT;")
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK;")
            raise
        finally:
            conn.execute("PRAGMA legacy_alter_table = OFF;")
            conn.execute("PRAGMA foreign_keys = ON;")


def _migrate_columns(conn: sqlite3.Connection) -> None:
    def add_col_if_missing(table: str, col: str, col_type: str):
        info = conn.execute(f"PRAGMA table_info({table})").fetchall()
        existing_cols = {row["name"] for row in info}
        if col not in existing_cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type};")

    # Demo and GPS Pipeline columns
    add_col_if_missing("vehicles", "is_demo", "INTEGER NOT NULL DEFAULT 0")
    add_col_if_missing("vehicles", "demo_key", "TEXT NULL")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_vehicles_demo_key ON vehicles(demo_key);")

    add_col_if_missing("drivers", "is_demo", "INTEGER NOT NULL DEFAULT 0")
    add_col_if_missing("drivers", "demo_key", "TEXT NULL")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_drivers_demo_key ON drivers(demo_key);")

    add_col_if_missing("deliveries", "is_demo", "INTEGER NOT NULL DEFAULT 0")
    add_col_if_missing("deliveries", "demo_key", "TEXT NULL")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_deliveries_demo_key ON deliveries(demo_key);")

    add_col_if_missing("tracking_sessions", "is_demo", "INTEGER NOT NULL DEFAULT 0")
    add_col_if_missing("gps_locations", "is_demo", "INTEGER NOT NULL DEFAULT 0")
    add_col_if_missing("phone_pairing_tokens", "used", "INTEGER NOT NULL DEFAULT 0")
    add_col_if_missing("gps_locations", "filtered_latitude", "REAL NULL")
    add_col_if_missing("gps_locations", "filtered_longitude", "REAL NULL")
    add_col_if_missing("gps_locations", "filtered_speed", "REAL NULL")
    add_col_if_missing("gps_locations", "filtered_heading", "REAL NULL")
    add_col_if_missing("gps_locations", "is_gated", "INTEGER NOT NULL DEFAULT 0")
    add_col_if_missing("gps_locations", "source", "TEXT NOT NULL DEFAULT 'device'")
    add_col_if_missing("gps_locations", "kalman_sigma_pos", "REAL NULL")
    add_col_if_missing("gps_locations", "mahalanobis_d2", "REAL NULL")


    # Devices
    add_col_if_missing("devices", "device_category", "TEXT NULL")
    add_col_if_missing("devices", "model", "TEXT NULL")
    add_col_if_missing("devices", "os_version", "TEXT NULL")
    add_col_if_missing("devices", "browser_version", "TEXT NULL")
    add_col_if_missing("devices", "client_device_token", "TEXT NULL")
    add_col_if_missing("devices", "identity_confidence", "TEXT NOT NULL DEFAULT 'client_storage_token'")
    add_col_if_missing("devices", "detection_limitations", "TEXT NULL")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_devices_client_token ON devices(client_device_token);")

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
    add_col_if_missing("gps_locations", "altitude", "REAL NULL")
    add_col_if_missing("gps_locations", "altitude_accuracy", "REAL NULL")
    add_col_if_missing("gps_locations", "derived_speed", "REAL NULL")
    add_col_if_missing("gps_locations", "speed_source", "TEXT NOT NULL DEFAULT 'reported'")
    add_col_if_missing("gps_locations", "distance_from_prev_m", "REAL NULL")
    add_col_if_missing("gps_locations", "time_delta_prev_s", "REAL NULL")
    add_col_if_missing("gps_locations", "is_implausible_jump", "INTEGER NOT NULL DEFAULT 0")
    add_col_if_missing("gps_locations", "quality_flag", "TEXT NOT NULL DEFAULT 'accepted'")
    add_col_if_missing("gps_locations", "client_ip", "TEXT NULL")
    add_col_if_missing("gps_locations", "raw_payload_json", "TEXT NULL")
    add_col_if_missing("gps_locations", "clock_skew_seconds", "REAL NULL")
    add_col_if_missing("gps_locations", "is_late_delivered", "INTEGER NOT NULL DEFAULT 0")

    # Tracking Sessions tokens and consent
    add_col_if_missing("tracking_sessions", "tracking_token", "TEXT NULL")
    add_col_if_missing("tracking_sessions", "token_expires_at", "TEXT NULL")
    add_col_if_missing("tracking_sessions", "token_revoked", "INTEGER NOT NULL DEFAULT 0")
    add_col_if_missing("tracking_sessions", "consent_given", "INTEGER NOT NULL DEFAULT 0")
    add_col_if_missing("tracking_sessions", "consent_timestamp", "TEXT NULL")
    add_col_if_missing("tracking_sessions", "single_device_token", "TEXT NULL")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tracking_sessions_token ON tracking_sessions(tracking_token);")


def purge_old_gps_telemetry(conn: sqlite3.Connection, retention_days: int) -> int:
    """Auto-purges raw GPS telemetry older than retention_days."""
    if retention_days <= 0:
        return 0
    cutoff = (datetime.now(UTC) - timedelta(days=retention_days)).isoformat()
    cur = conn.execute("DELETE FROM gps_locations WHERE server_timestamp < ?", (cutoff,))
    return cur.rowcount


@contextmanager
def read_conn(db_path: str | None = None) -> Generator[sqlite3.Connection, None, None]:
    conn = get_connection(db_path)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def immediate_transaction(db_path: str | None = None) -> Generator[sqlite3.Connection, None, None]:
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
    before: Any | None = None,
    after: Any | None = None,
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


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)
