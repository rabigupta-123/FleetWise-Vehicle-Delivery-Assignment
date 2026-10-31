import asyncio
import csv
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import tempfile
import time
import uuid
from collections.abc import AsyncGenerator
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.advisor import get_dispatch_next_delivery, get_recommendations_for_delivery
from app.analytics.accuracy_engine import (
    calculate_telemetry_quality_score,
)
from app.analytics.confidence_engine import (
    evaluate_assignment_confidence,
    evaluate_device_identity_confidence,
)
from app.analytics.deep_analysis import (
    analyze_delivery_performance,
    analyze_driver_performance,
    analyze_driver_utilization,
    analyze_fleet_utilization,
    analyze_vehicle_performance,
    detect_operational_anomalies,
)
from app.auth import (
    SESSION_COOKIE_NAME,
    check_login_rate_limit,
    check_permission,
    clear_session_cookie,
    get_current_user,
    is_auth_enabled,
    record_login_failure,
    record_login_success,
    set_session_cookie,
    verify_password,
)
from app.clock import get_current_time, utc_now_iso
from app.config import get_gps_retention_days
from app.db import (
    get_connection,
    immediate_transaction,
    init_db,
    purge_old_gps_telemetry,
    read_conn,
    write_audit,
)
from app.errors import AppError, register_exception_handlers
from app.importer import (
    TEMPLATES,
    parse_upload_content,
    sanitize_csv_cell,
    validate_deliveries_rows,
    validate_drivers_rows,
    validate_vehicles_rows,
)
from app.schemas import (
    AssignRequest,
    DeliveryCreate,
    DeliveryStatusPatch,
    DeviceRegisterRequest,
    DeviceRenameRequest,
    DeviceRevokeRequest,
    DriverCreate,
    DriverPhonePatch,
    DriverStatusPatch,
    GPSLocationCreate,
    PhoneVerifyCodeRequest,
    TrackingConsentUpdate,
    TrackingSessionStart,
    TrackingSessionStop,
    VehicleCreate,
    VehicleStatusPatch,
)
from app.telematics import (
    compute_freshness_status,
    evaluate_telemetry_step,
    evaluate_timestamp_validity,
    normalize_phone_number,
)

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

# Event bus for Server-Sent Events (SSE)
SSE_SUBSCRIBERS: set[asyncio.Queue] = set()


def broadcast_event(event_type: str, data: Any):
    payload = json.dumps({"type": event_type, "data": data, "ts": utc_now_iso()})
    for queue in list(SSE_SUBSCRIBERS):
        try:
            queue.put_nowait(payload)
        except Exception:
            SSE_SUBSCRIBERS.discard(queue)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    retention_days = get_gps_retention_days()
    # Purge expired GPS fixes on startup
    with immediate_transaction() as conn:
        purge_old_gps_telemetry(conn, retention_days)

    # Recurring background task: purge expired GPS fixes every hour
    async def _recurring_gps_purge():
        while True:
            try:
                await asyncio.sleep(3600)
                r_days = get_gps_retention_days()
                with immediate_transaction() as p_conn:
                    purge_old_gps_telemetry(p_conn, r_days)
            except asyncio.CancelledError:
                break
            except Exception:
                pass

    purge_task = None
    if not os.environ.get("PYTEST_CURRENT_TEST"):
        purge_task = asyncio.create_task(_recurring_gps_purge())

    try:
        yield
    finally:
        if purge_task is not None:
            purge_task.cancel()
            try:
                await purge_task
            except asyncio.CancelledError:
                pass


enable_docs = os.environ.get("FLEETWISE_ENABLE_DOCS") == "1"
app = FastAPI(
    title="FleetWise — Vehicle & Delivery Assignment",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs" if enable_docs else None,
    redoc_url="/redoc" if enable_docs else None,
    openapi_url="/openapi.json" if enable_docs else None,
)

register_exception_handlers(app)


# Security Headers & Exception Handling Middleware
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: https://*.tile.openstreetmap.org https://tile.openstreetmap.org;"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.middleware("http")
async def require_auth_middleware(request: Request, call_next):
    path = request.url.path
    public_allowlist = {"/", "/health", "/auth/login", "/probe", "/probe/report"}
    is_public = path in public_allowlist or path.startswith("/static")

    # API docs authorization
    if path in ("/docs", "/redoc", "/openapi.json"):
        if not enable_docs:
            return JSONResponse(status_code=404, content={"error": "NOT_FOUND", "message": "Documentation disabled."})
        user = get_current_user(request)
        if not user or user.get("role") != "ops_lead":
            return JSONResponse(status_code=403, content={"error": "FORBIDDEN", "message": "API documentation requires ops_lead privilege."})
        return await call_next(request)

    # Auth verification on non-public routes
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
    is_tunnel = any(d in host.lower() for d in [".loca.lt", ".ngrok-free.app", ".trycloudflare.com"])

    if (is_auth_enabled() or is_tunnel) and not is_public:
        user = get_current_user(request)
        if user is None:
            return JSONResponse(
                status_code=401,
                content={"error": "UNAUTHORIZED", "message": "Authentication required. Please log in."},
            )

        # CSRF origin verification on state-changing requests using cookie auth
        if request.method in ("POST", "PUT", "PATCH", "DELETE") and request.cookies.get(SESSION_COOKIE_NAME):
            origin = request.headers.get("origin")
            referer = request.headers.get("referer")
            host = request.headers.get("host", "").split(":")[0]
            check_url = origin or referer
            if check_url and host:
                check_host = check_url.split("://")[-1].split("/")[0].split(":")[0]
                if check_host.lower() not in (host.lower(), "localhost", "127.0.0.1"):
                    return JSONResponse(
                        status_code=403,
                        content={"error": "CSRF_FAILED", "message": "Cross-site request forgery protection rejected this request."},
                    )

    return await call_next(request)


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
def serve_index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/probe", include_in_schema=False)
def serve_probe():
    return FileResponse(str(STATIC_DIR / "probe.html"))


@app.post("/probe/report")
async def record_probe_report(request: Request):
    """Stores client device capability and battery diagnostics probe report."""
    try:
        body = await request.json()
    except Exception:
        raise AppError(400, "VALIDATION_ERROR", "Invalid JSON payload.") from None

    report_id = f"prb_{secrets.token_hex(8)}"
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    is_secure = int(request.headers.get("x-forwarded-proto") == "https" or request.url.scheme == "https")
    now_iso = datetime.now(UTC).isoformat()

    device_id = body.get("device_id")
    driver_id = body.get("driver_id")
    token_used = body.get("token")
    high_entropy = json.dumps(body.get("high_entropy_ch", {}))
    client_probe = json.dumps(body)
    server_probe = json.dumps({
        "received_at": now_iso,
        "client_ip": client_ip,
        "headers": dict(request.headers),
    })
    discrepancies = json.dumps(body.get("discrepancies", []))

    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO device_probe_reports (
                report_id, device_id, driver_id, token_used,
                client_ip, user_agent, is_secure_context,
                high_entropy_ch_json, client_probe_json,
                server_probe_json, discrepancies_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report_id, device_id, driver_id, token_used,
                client_ip, user_agent, is_secure,
                high_entropy, client_probe,
                server_probe, discrepancies, now_iso
            )
        )
        conn.commit()
    finally:
        conn.close()

    return {"status": "ok", "report_id": report_id, "received_at": now_iso}


@app.get("/devices/probe-reports")
def list_probe_reports(limit: int = 50):
    """Retrieves list of captured device probe reports."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT report_id, device_id, driver_id, client_ip, user_agent, is_secure_context, created_at "
            "FROM device_probe_reports ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# -------------------------------------------------------------------------
# AUTHENTICATION & RBAC (B5)
# -------------------------------------------------------------------------
@app.post("/auth/login")
async def login(request: Request, response: Response):
    try:
        body = await request.json()
    except Exception:
        raise AppError(400, "VALIDATION_ERROR", "Invalid JSON payload.") from None
    username = str(body.get("username") or "").strip()
    password = str(body.get("password") or "").strip()
    if not username or not password:
        raise AppError(400, "VALIDATION_ERROR", "Username and password are required.")

    check_login_rate_limit(username)

    with read_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if not row or not verify_password(password, row["password_hash"]):
            record_login_failure(username)
            raise AppError(401, "UNAUTHORIZED", "Invalid username or password.")
        record_login_success(username)
        user_data = {
            "username": row["username"],
            "role": row["role"],
            "must_change_password": bool(row["must_change_password"]) if "must_change_password" in row.keys() else False,
        }

    token = set_session_cookie(response, user_data, request)
    return {"message": "Logged in successfully", "user": user_data, "token": token}


@app.post("/auth/logout")
def logout(request: Request, response: Response):
    clear_session_cookie(response, request)
    return {"message": "Logged out successfully"}


@app.get("/auth/me")
def get_me(request: Request):
    user = get_current_user(request)
    if not user:
        return {"authenticated": False, "user": None}
    return {"authenticated": True, "user": user}


# -------------------------------------------------------------------------
# HEALTH & METRICS
# -------------------------------------------------------------------------
@app.get("/health")
def health_check():
    with read_conn() as conn:
        journal_mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
        fk_enabled = conn.execute("PRAGMA foreign_keys;").fetchone()[0]
        v_count = conn.execute("SELECT COUNT(*) FROM vehicles;").fetchone()[0]
        dr_count = conn.execute("SELECT COUNT(*) FROM drivers;").fetchone()[0]
        del_count = conn.execute("SELECT COUNT(*) FROM deliveries;").fetchone()[0]
    return {
        "status": "ok",
        "journal_mode": journal_mode,
        "foreign_keys": bool(fk_enabled),
        "counts": {
            "vehicles": v_count,
            "drivers": dr_count,
            "deliveries": del_count,
        },
    }


@app.get("/network-info")
def get_network_info():
    import socket
    ip = "127.0.0.1"
    usable = []
    try:
        _, _, ips = socket.gethostbyname_ex(socket.gethostname())
        # Filter loopback and APIPA
        usable = [a for a in ips if not a.startswith("169.254.") and not a.startswith("127.")]
        # Prioritize physical Wi-Fi / LAN (10.x.x.x, standard 192.168.x.x)
        for cand in usable:
            if cand.startswith("10."):
                ip = cand
                break
        if ip == "127.0.0.1":
            for cand in usable:
                if cand.startswith("192.168.") and not cand.startswith("192.168.84.") and not cand.startswith("192.168.152."):
                    ip = cand
                    break
        if ip == "127.0.0.1" and usable:
            ip = usable[0]
    except Exception:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            usable = [ip]
        except Exception:
            ip = "127.0.0.1"
            usable = ["127.0.0.1"]

    has_ssl = os.path.exists("certs/cert.pem") and os.path.exists("certs/key.pem")
    cert_info: dict[str, Any] = {}
    if has_ssl:
        try:
            from scripts.generate_ssl_certs import TRUST_INSTRUCTIONS, inspect_cert
            cert_info = inspect_cert("certs/cert.pem")
            cert_info["trust_guide"] = TRUST_INSTRUCTIONS
        except Exception:
            pass

    return {
        "local_ip": ip,
        "all_lan_ips": usable,
        "port": 8000,
        "https_port": 8443,
        "lan_url": f"http://{ip}:8000",
        "lan_https_url": f"https://{ip}:8443",
        "localhost_url": "http://127.0.0.1:8000",
        "localhost_https_url": "https://127.0.0.1:8443",
        "has_ssl_certs": has_ssl,
        "cert_details": cert_info,
        "secure_context_hint": "Modern mobile browsers require HTTPS (:8443) or a secure public tunnel to grant GPS location permission.",
    }


@app.get("/system/host-power")
def get_system_host_power():
    """Returns server host physical power telemetry (Win32 kernel GetSystemPowerStatus / psutil)."""
    from app.power import get_server_host_power_status
    return get_server_host_power_status()


@app.get("/metrics")
def get_metrics():
    with read_conn() as conn:
        total_veh = conn.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0]
        avail_veh = conn.execute(
            """
            SELECT COUNT(*) FROM vehicles v
            WHERE v.status = 'available'
            AND NOT EXISTS (SELECT 1 FROM assignments a WHERE a.vehicle_id = v.vehicle_id AND a.released_at IS NULL)
            """
        ).fetchone()[0]
        assigned_veh = conn.execute(
            """
            SELECT COUNT(*) FROM vehicles v
            WHERE v.status = 'assigned'
            OR EXISTS (SELECT 1 FROM assignments a WHERE a.vehicle_id = v.vehicle_id AND a.released_at IS NULL)
            """
        ).fetchone()[0]
        maint_veh = conn.execute("SELECT COUNT(*) FROM vehicles WHERE status = 'maintenance'").fetchone()[0]
        inact_veh = conn.execute("SELECT COUNT(*) FROM vehicles WHERE status = 'inactive'").fetchone()[0]

        total_drv = conn.execute("SELECT COUNT(*) FROM drivers").fetchone()[0]
        avail_drv = conn.execute(
            """
            SELECT COUNT(*) FROM drivers d
            WHERE d.availability_status = 'available'
            AND NOT EXISTS (SELECT 1 FROM assignments a WHERE a.driver_id = d.driver_id AND a.released_at IS NULL)
            """
        ).fetchone()[0]

        active_del = conn.execute("SELECT COUNT(*) FROM deliveries WHERE status IN ('assigned', 'in_transit')").fetchone()[0]
        pending_del = conn.execute("SELECT COUNT(*) FROM deliveries WHERE status = 'pending'").fetchone()[0]
        delivered_del = conn.execute("SELECT COUNT(*) FROM deliveries WHERE status = 'delivered'").fetchone()[0]
        cancelled_del = conn.execute("SELECT COUNT(*) FROM deliveries WHERE status = 'cancelled'").fetchone()[0]

        utilisation = (assigned_veh / total_veh * 100.0) if total_veh > 0 else 0.0

    return {
        "available_fleet": avail_veh,
        "total_vehicles": total_veh,
        "assigned_vehicles": assigned_veh,
        "maintenance_vehicles": maint_veh,
        "inactive_vehicles": inact_veh,
        "available_drivers": avail_drv,
        "total_drivers": total_drv,
        "active_deliveries": active_del,
        "pending_deliveries": pending_del,
        "delivered_count": delivered_del,
        "cancelled_count": cancelled_del,
        "utilisation_pct": round(utilisation, 1),
    }


@app.get("/audit")
def get_audit():
    with read_conn() as conn:
        rows = conn.execute(
            "SELECT id, ts, actor, action, entity, entity_id, before_json, after_json FROM audit_log ORDER BY id DESC LIMIT 500"
        ).fetchall()
        return [dict(r) for r in rows]


# -------------------------------------------------------------------------
# REAL-TIME SERVER-SENT EVENTS (B3)
# -------------------------------------------------------------------------
@app.get("/events")
async def sse_events(request: Request, single_ping: bool = False):
    queue: asyncio.Queue = asyncio.Queue()
    SSE_SUBSCRIBERS.add(queue)

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            yield "event: ping\ndata: connected\n\n"
            if single_ping:
                return
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=20.0)
                    yield f"event: state_change\ndata: {payload}\n\n"
                except TimeoutError:
                    yield "event: ping\ndata: keep-alive\n\n"
        finally:
            SSE_SUBSCRIBERS.discard(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# -------------------------------------------------------------------------
# VEHICLES
# -------------------------------------------------------------------------
@app.get("/vehicles")
def list_vehicles():
    with read_conn() as conn:
        rows = conn.execute(
            """
            SELECT v.vehicle_id, v.registration_no, v.type, v.capacity, v.status,
                   a.delivery_id AS active_delivery_id
            FROM vehicles v
            LEFT JOIN assignments a ON a.vehicle_id = v.vehicle_id AND a.released_at IS NULL
            ORDER BY v.vehicle_id ASC
            """
        ).fetchall()
        return [dict(r) for r in rows]


@app.post("/vehicles", status_code=201)
def create_vehicle(body: VehicleCreate, request: Request):
    user = get_current_user(request)
    check_permission(user, "vehicles", request=request)
    actor = user["username"] if user else "operator"

    norm_reg = body.registration_no.strip().upper()

    with immediate_transaction() as conn:
        existing = conn.execute(
            "SELECT vehicle_id FROM vehicles WHERE UPPER(registration_no) = UPPER(?)",
            (norm_reg,),
        ).fetchone()
        if existing:
            raise AppError(409, "DUPLICATE", f"Vehicle registration '{norm_reg}' already exists.")

        final_id = body.vehicle_id
        if final_id:
            if conn.execute("SELECT 1 FROM vehicles WHERE vehicle_id = ?", (final_id,)).fetchone():
                raise AppError(409, "DUPLICATE", f"Vehicle ID '{final_id}' already exists.")
        else:
            all_ids = [r[0] for r in conn.execute("SELECT vehicle_id FROM vehicles").fetchall()]
            max_num = 0
            for vid in all_ids:
                m = re.match(r"^V-(\d+)$", vid, re.IGNORECASE)
                if m:
                    max_num = max(max_num, int(m.group(1)))
            max_num += 1
            final_id = f"V-{max_num:03d}"
            while final_id in all_ids:
                max_num += 1
                final_id = f"V-{max_num:03d}"

        conn.execute(
            """
            INSERT INTO vehicles (vehicle_id, registration_no, type, capacity, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (final_id, norm_reg, body.type, body.capacity, body.status),
        )

        after_data = {
            "vehicle_id": final_id,
            "registration_no": norm_reg,
            "type": body.type,
            "capacity": body.capacity,
            "status": body.status,
        }
        write_audit(conn, actor=actor, action="create", entity="vehicle", entity_id=final_id, after=after_data)

    broadcast_event("vehicle_created", after_data)
    return after_data


@app.patch("/vehicles/{vehicle_id}/status")
def patch_vehicle_status(vehicle_id: str, body: VehicleStatusPatch, request: Request):
    user = get_current_user(request)
    check_permission(user, "vehicles", request=request)
    actor = user["username"] if user else "operator"

    # State-bypass check: vehicles can never be patched directly to assigned or in_transit
    if body.status in ("assigned", "in_transit"):
        raise AppError(400, "VALIDATION_ERROR", f"Cannot patch vehicle directly to '{body.status}'.")

    with immediate_transaction() as conn:
        row = conn.execute("SELECT * FROM vehicles WHERE vehicle_id = ?", (vehicle_id,)).fetchone()
        if not row:
            raise AppError(404, "NOT_FOUND", f"Vehicle '{vehicle_id}' not found.")
        current_veh = dict(row)

        active_asg = conn.execute(
            "SELECT assignment_id, delivery_id FROM assignments WHERE vehicle_id = ? AND released_at IS NULL",
            (vehicle_id,),
        ).fetchone()

        if active_asg and body.status in ("maintenance", "inactive"):
            raise AppError(
                409,
                "VEHICLE_UNAVAILABLE",
                f"Cannot change vehicle {vehicle_id} to '{body.status}' while assigned to active delivery {active_asg['delivery_id']}.",
            )

        conn.execute("UPDATE vehicles SET status = ? WHERE vehicle_id = ?", (body.status, vehicle_id))
        after_veh = {**current_veh, "status": body.status}
        write_audit(conn, actor=actor, action="update_status", entity="vehicle", entity_id=vehicle_id, before=current_veh, after=after_veh)

    broadcast_event("vehicle_status_changed", after_veh)
    return after_veh


# -------------------------------------------------------------------------
# DRIVERS
# -------------------------------------------------------------------------
@app.get("/drivers")
def list_drivers():
    with read_conn() as conn:
        rows = conn.execute(
            """
            SELECT d.driver_id, d.name, d.phone, d.phone_e164, d.phone_verification_status,
                   d.phone_country_code, d.phone_carrier, d.availability_status,
                   a.delivery_id AS active_delivery_id
            FROM drivers d
            LEFT JOIN assignments a ON a.driver_id = d.driver_id AND a.released_at IS NULL
            ORDER BY d.driver_id ASC
            """
        ).fetchall()
        return [dict(r) for r in rows]


@app.post("/drivers", status_code=201)
def create_driver(body: DriverCreate, request: Request):
    user = get_current_user(request)
    check_permission(user, "drivers", request=request)
    actor = user["username"] if user else "operator"

    with immediate_transaction() as conn:
        final_id = body.driver_id
        if final_id:
            if conn.execute("SELECT 1 FROM drivers WHERE driver_id = ?", (final_id,)).fetchone():
                raise AppError(409, "DUPLICATE", f"Driver ID '{final_id}' already exists.")
        else:
            all_ids = [r[0] for r in conn.execute("SELECT driver_id FROM drivers").fetchall()]
            max_num = 0
            for did in all_ids:
                m = re.match(r"^DR-(\d+)$", did, re.IGNORECASE)
                if m:
                    max_num = max(max_num, int(m.group(1)))
            max_num += 1
            final_id = f"DR-{max_num:03d}"
            while final_id in all_ids:
                max_num += 1
                final_id = f"DR-{max_num:03d}"

        norm = normalize_phone_number(body.phone)
        phone_e164 = norm["phone_e164"] if norm["is_valid"] else None
        phone_cc = norm["country_code"] if norm["is_valid"] else None
        phone_carr = norm["carrier_name"] if norm["is_valid"] else None

        conn.execute(
            """
            INSERT INTO drivers (driver_id, name, phone, phone_e164, phone_verification_status, phone_country_code, phone_carrier, availability_status)
            VALUES (?, ?, ?, ?, 'unverified', ?, ?, ?)
            """,
            (final_id, body.name, body.phone, phone_e164, phone_cc, phone_carr, body.availability_status),
        )

        after_data = {
            "driver_id": final_id,
            "name": body.name,
            "phone": body.phone,
            "phone_e164": phone_e164,
            "phone_verification_status": "unverified",
            "phone_country_code": phone_cc,
            "phone_carrier": phone_carr,
            "availability_status": body.availability_status,
        }
        write_audit(conn, actor=actor, action="create", entity="driver", entity_id=final_id, after=after_data)

    broadcast_event("driver_created", after_data)
    return after_data


@app.patch("/drivers/{driver_id}/status")
def patch_driver_status(driver_id: str, body: DriverStatusPatch, request: Request):
    user = get_current_user(request)
    check_permission(user, "drivers", request=request)
    actor = user["username"] if user else "operator"

    # State-bypass check: drivers can never be patched directly to assigned or in_transit
    if body.availability_status in ("assigned", "in_transit"):
        raise AppError(400, "VALIDATION_ERROR", f"Cannot patch driver directly to '{body.availability_status}'.")

    with immediate_transaction() as conn:
        row = conn.execute("SELECT * FROM drivers WHERE driver_id = ?", (driver_id,)).fetchone()
        if not row:
            raise AppError(404, "NOT_FOUND", f"Driver '{driver_id}' not found.")
        current_drv = dict(row)

        active_asg = conn.execute(
            "SELECT assignment_id, delivery_id FROM assignments WHERE driver_id = ? AND released_at IS NULL",
            (driver_id,),
        ).fetchone()

        if active_asg and body.availability_status == "unavailable":
            raise AppError(
                409,
                "DRIVER_UNAVAILABLE",
                f"Cannot change driver {driver_id} to 'unavailable' while assigned to active delivery {active_asg['delivery_id']}.",
            )

        conn.execute("UPDATE drivers SET availability_status = ? WHERE driver_id = ?", (body.availability_status, driver_id))
        after_drv = {**current_drv, "availability_status": body.availability_status}
        write_audit(conn, actor=actor, action="update_status", entity="driver", entity_id=driver_id, before=current_drv, after=after_drv)

    broadcast_event("driver_status_changed", after_drv)
    return after_drv


@app.patch("/drivers/{driver_id}/phone")
def patch_driver_phone(driver_id: str, body: DriverPhonePatch, request: Request):
    user = get_current_user(request)
    check_permission(user, "drivers", request=request)
    actor = user["username"] if user else "operator"

    clean_phone = body.phone.strip()
    norm = normalize_phone_number(clean_phone)
    if not norm["is_valid"]:
        raise AppError(400, "VALIDATION_ERROR", norm["error"] or f"Invalid phone number format: '{clean_phone}'")

    with immediate_transaction() as conn:
        row = conn.execute("SELECT * FROM drivers WHERE driver_id = ?", (driver_id,)).fetchone()
        if not row:
            raise AppError(404, "NOT_FOUND", f"Driver '{driver_id}' not found.")
        current_drv = dict(row)

        conn.execute(
            """
            UPDATE drivers
            SET phone = ?, phone_e164 = ?, phone_country_code = ?, phone_carrier = ?, phone_verification_status = 'unverified'
            WHERE driver_id = ?
            """,
            (clean_phone, norm["phone_e164"], norm["country_code"], norm["carrier_name"], driver_id),
        )
        after_drv = {
            **current_drv,
            "phone": clean_phone,
            "phone_e164": norm["phone_e164"],
            "phone_country_code": norm["country_code"],
            "phone_carrier": norm["carrier_name"],
            "phone_verification_status": "unverified",
        }
        write_audit(conn, actor=actor, action="update_phone", entity="driver", entity_id=driver_id, before=current_drv, after=after_drv)

    broadcast_event("driver_phone_updated", after_drv)
    return after_drv


@app.post("/drivers/{driver_id}/phone/request-verification")
def request_driver_phone_verification(driver_id: str, request: Request):
    user = get_current_user(request)
    check_permission(user, "drivers", request=request)
    actor = user["username"] if user else "operator"

    with immediate_transaction() as conn:
        row = conn.execute("SELECT * FROM drivers WHERE driver_id = ?", (driver_id,)).fetchone()
        if not row:
            raise AppError(404, "NOT_FOUND", f"Driver '{driver_id}' not found.")
        drv = dict(row)
        phone_e164 = drv.get("phone_e164") or drv.get("phone")

        # Rate limit verification requests (max 5 in 10 minutes)
        recent_cnt = conn.execute(
            """
            SELECT COUNT(*) as cnt FROM phone_verifications
            WHERE driver_id = ? AND created_at >= datetime('now', '-10 minutes')
            """,
            (driver_id,),
        ).fetchone()["cnt"]

        if recent_cnt >= 5:
            raise AppError(429, "RATE_LIMITED", "Too many verification requests. Please wait 10 minutes before requesting a new challenge.")

        # Expire any previous pending verifications
        conn.execute(
            "UPDATE phone_verifications SET status = 'expired' WHERE driver_id = ? AND status = 'pending'",
            (driver_id,),
        )

        code = f"{secrets.randbelow(900000) + 100000}"
        salt = secrets.token_hex(16)
        server_secret = os.environ.get("SESSION_SECRET_KEY", "fleetwise_default_super_secret_session_key_32bytes").encode("utf-8")
        code_digest = hmac.new(server_secret, (salt + code).encode("utf-8"), hashlib.sha256).hexdigest()
        code_hash = f"{salt}:{code_digest}"
        verification_id = f"VRF-{uuid.uuid4().hex[:10].upper()}"
        now_str = utc_now_iso()
        exp_str = (datetime.now(UTC) + timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")

        conn.execute(
            """
            INSERT INTO phone_verifications (
                verification_id, driver_id, phone_e164, code_hash, expires_at, attempts_remaining, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, 3, 'pending', ?)
            """,
            (verification_id, driver_id, phone_e164, code_hash, exp_str, now_str),
        )

        conn.execute(
            "UPDATE drivers SET phone_verification_status = 'pending' WHERE driver_id = ?",
            (driver_id,),
        )

        sms_configured = bool(os.environ.get("SMS_PROVIDER_API_KEY") or os.environ.get("TWILIO_ACCOUNT_SID"))
        is_dev_mode = (not sms_configured) or os.environ.get("APP_ENV", "development").lower() == "development"
        challenge_data = {
            "verification_id": verification_id,
            "driver_id": driver_id,
            "phone_e164": phone_e164,
            "status": "pending",
            "expires_at": exp_str,
            "mode": "development" if is_dev_mode else "production",
            "is_dev_mode": is_dev_mode,
            "disclaimer": "DEV MODE - no SMS is sent" if not sms_configured else "SMS verification code dispatched",
            "dev_verification_code": code if is_dev_mode else None,
            "dev_challenge_code": code if is_dev_mode else None,
            "message": f"Verification challenge created for {phone_e164}. Enter the 6-digit code to complete verification.",
        }
        write_audit(conn, actor=actor, action="request_phone_verification", entity="driver", entity_id=driver_id, after={"verification_id": verification_id, "phone_e164": phone_e164})

    return challenge_data


@app.post("/drivers/{driver_id}/phone/verify")
def verify_driver_phone(driver_id: str, body: PhoneVerifyCodeRequest, request: Request):
    user = get_current_user(request)
    check_permission(user, "drivers", request=request)
    actor = user["username"] if user else "operator"

    with immediate_transaction() as conn:
        row = conn.execute("SELECT * FROM drivers WHERE driver_id = ?", (driver_id,)).fetchone()
        if not row:
            raise AppError(404, "NOT_FOUND", f"Driver '{driver_id}' not found.")

        vrf_row = conn.execute(
            "SELECT * FROM phone_verifications WHERE verification_id = ? AND driver_id = ?",
            (body.verification_id, driver_id),
        ).fetchone()

        if not vrf_row:
            raise AppError(404, "NOT_FOUND", f"Verification challenge '{body.verification_id}' not found.")

        vrf = dict(vrf_row)
        if vrf["status"] != "pending":
            raise AppError(400, "CHALLENGE_INACTIVE", f"Verification challenge is already '{vrf['status']}'.")

        if vrf["attempts_remaining"] <= 0:
            conn.execute("UPDATE phone_verifications SET status = 'failed' WHERE verification_id = ?", (body.verification_id,))
            raise AppError(400, "MAX_ATTEMPTS_EXCEEDED", "Maximum verification attempts exceeded. Please request a new code.")

        try:
            exp_time = datetime.fromisoformat(vrf["expires_at"].replace("Z", "+00:00"))
            if datetime.now(UTC) > exp_time:
                conn.execute("UPDATE phone_verifications SET status = 'expired' WHERE verification_id = ?", (body.verification_id,))
                raise AppError(400, "CHALLENGE_EXPIRED", "Verification code has expired. Please request a new code.")
        except ValueError:
            pass

        server_secret = os.environ.get("SESSION_SECRET_KEY", "fleetwise_default_super_secret_session_key_32bytes").encode("utf-8")
        stored_hash = vrf["code_hash"]
        if ":" in stored_hash:
            salt, stored_digest = stored_hash.split(":", 1)
            expected_digest = hmac.new(server_secret, (salt + body.code.strip()).encode("utf-8"), hashlib.sha256).hexdigest()
            is_valid_code = hmac.compare_digest(expected_digest, stored_digest)
        else:
            expected_hash = hashlib.sha256((body.code.strip() + driver_id).encode()).hexdigest()
            is_valid_code = hmac.compare_digest(expected_hash, stored_hash)

        if is_valid_code:
            conn.execute("UPDATE phone_verifications SET status = 'verified' WHERE verification_id = ?", (body.verification_id,))
            conn.execute("UPDATE drivers SET phone_verification_status = 'verified' WHERE driver_id = ?", (driver_id,))
            result = {
                "status": "verified",
                "verified": True,
                "driver_id": driver_id,
                "phone_e164": vrf["phone_e164"],
                "message": "Phone number successfully verified.",
            }
            write_audit(conn, actor=actor, action="verify_phone_success", entity="driver", entity_id=driver_id, after=result)
            broadcast_event("driver_phone_verified", {"driver_id": driver_id, "status": "verified"})
            return result
        else:
            new_attempts = vrf["attempts_remaining"] - 1
            new_status = "failed" if new_attempts <= 0 else "pending"
            conn.execute(
                "UPDATE phone_verifications SET attempts_remaining = ?, status = ? WHERE verification_id = ?",
                (new_attempts, new_status, body.verification_id),
            )
            if new_attempts <= 0:
                conn.execute("UPDATE drivers SET phone_verification_status = 'failed' WHERE driver_id = ?", (driver_id,))
                raise AppError(400, "INVALID_CODE", "Invalid code. Max attempts exceeded. Please request a new code.")
            raise AppError(400, "INVALID_CODE", f"Incorrect verification code. {new_attempts} attempts remaining.")


# -------------------------------------------------------------------------
# DELIVERIES & SLA RISK RADAR (B2)
# -------------------------------------------------------------------------
def enrich_delivery_sla(d: dict[str, Any]) -> dict[str, Any]:
    sched_str = d.get("scheduled_time")
    if not sched_str:
        d["sla_status"] = "normal"
        d["countdown"] = "—"
        return d

    try:
        norm = sched_str[:-1] + "+00:00" if sched_str.endswith("Z") else sched_str
        target = datetime.fromisoformat(norm)
        now = datetime.now(UTC)
        diff_sec = int((target - now).total_seconds())

        if d.get("status") in ("delivered", "cancelled"):
            d["sla_status"] = "resolved"
            d["countdown"] = "Completed"
            return d

        if diff_sec < 0:
            overdue_min = abs(diff_sec) // 60
            d["sla_status"] = "overdue"
            d["countdown"] = f"Overdue by {overdue_min}m"
        elif diff_sec <= 3600:
            due_min = diff_sec // 60
            d["sla_status"] = "at_risk"
            d["countdown"] = f"Due in {due_min}m"
        else:
            hrs = diff_sec // 3600
            mins = (diff_sec % 3600) // 60
            d["sla_status"] = "normal"
            d["countdown"] = f"Due in {hrs}h {mins}m"
    except Exception:
        d["sla_status"] = "normal"
        d["countdown"] = "—"

    return d


@app.get("/deliveries")
def list_deliveries(status: str | None = Query(None), q: str | None = Query(None)):
    query = """
        SELECT d.delivery_id, d.pickup, d.dropoff, d.scheduled_time, d.priority,
               d.required_capacity, d.status, d.created_at, d.version,
               d.pickup_lat, d.pickup_lng, d.drop_lat, d.drop_lng,
               a.vehicle_id AS active_vehicle_id,
               a.driver_id AS active_driver_id,
               a.assignment_id AS active_assignment_id
        FROM deliveries d
        LEFT JOIN assignments a ON a.delivery_id = d.delivery_id AND a.released_at IS NULL
        WHERE 1=1
    """
    params = []
    if status:
        query += " AND d.status = ?"
        params.append(status.strip())

    if q:
        term = f"%{q.strip().lower()}%"
        query += " AND (LOWER(d.delivery_id) LIKE ? OR LOWER(d.pickup) LIKE ? OR LOWER(d.dropoff) LIKE ?)"
        params.extend([term, term, term])

    query += " ORDER BY d.created_at DESC, d.delivery_id DESC"

    with read_conn() as conn:
        rows = conn.execute(query, params).fetchall()
        return [enrich_delivery_sla(dict(r)) for r in rows]


@app.post("/deliveries", status_code=201)
def create_delivery(body: DeliveryCreate, request: Request):
    user = get_current_user(request)
    check_permission(user, "deliveries", request=request)
    actor = user["username"] if user else "operator"

    with immediate_transaction() as conn:
        final_id = body.delivery_id
        if final_id:
            if conn.execute("SELECT 1 FROM deliveries WHERE delivery_id = ?", (final_id,)).fetchone():
                raise AppError(409, "DUPLICATE", f"Delivery ID '{final_id}' already exists.")
        else:
            all_ids = [r[0] for r in conn.execute("SELECT delivery_id FROM deliveries").fetchall()]
            max_num = 0
            for did in all_ids:
                m = re.match(r"^D-(\d+)$", did, re.IGNORECASE)
                if m:
                    max_num = max(max_num, int(m.group(1)))
            max_num += 1
            final_id = f"D-{max_num:03d}"
            while final_id in all_ids:
                max_num += 1
                final_id = f"D-{max_num:03d}"

        now_str = utc_now_iso()
        conn.execute(
            """
            INSERT INTO deliveries (delivery_id, pickup, dropoff, scheduled_time, priority, required_capacity, status, created_at, version, pickup_lat, pickup_lng, drop_lat, drop_lng)
            VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, 1, ?, ?, ?, ?)
            """,
            (final_id, body.pickup, body.dropoff, body.scheduled_time, body.priority, body.required_capacity, now_str, body.pickup_lat, body.pickup_lng, body.drop_lat, body.drop_lng),
        )

        after_data = {
            "delivery_id": final_id,
            "pickup": body.pickup,
            "dropoff": body.dropoff,
            "scheduled_time": body.scheduled_time,
            "priority": body.priority,
            "required_capacity": body.required_capacity,
            "status": "pending",
            "created_at": now_str,
            "version": 1,
            "pickup_lat": body.pickup_lat,
            "pickup_lng": body.pickup_lng,
            "drop_lat": body.drop_lat,
            "drop_lng": body.drop_lng,
        }
        write_audit(conn, actor=actor, action="create", entity="delivery", entity_id=final_id, after=after_data)

    broadcast_event("delivery_created", after_data)
    return enrich_delivery_sla(after_data)


# -------------------------------------------------------------------------
# SMART DISPATCH ADVISOR & BLOCKED QUEUE (B1 & B2)
# -------------------------------------------------------------------------
@app.get("/deliveries/{delivery_id}/recommendations")
def get_recommendations(delivery_id: str):
    with read_conn() as conn:
        res = get_recommendations_for_delivery(delivery_id, conn)
        if res.get("error") == "NOT_FOUND":
            raise AppError(404, "NOT_FOUND", f"Delivery '{delivery_id}' does not exist.")
        return res


@app.get("/deliveries/dispatch-next")
def dispatch_next():
    with read_conn() as conn:
        next_del = get_dispatch_next_delivery(conn)
        if not next_del:
            return {"has_next": False, "delivery": None}
        return {"has_next": True, "delivery": enrich_delivery_sla(next_del)}


@app.get("/deliveries/blocked")
def get_blocked_queue():
    with read_conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM deliveries
            WHERE status = 'pending'
              AND NOT EXISTS (SELECT 1 FROM assignments a WHERE a.delivery_id = deliveries.delivery_id AND a.released_at IS NULL)
            ORDER BY scheduled_time ASC
            """
        ).fetchall()

        all_pending = [dict(r) for r in rows]
        blocked = []

        total_avail_veh = conn.execute("SELECT COUNT(*) FROM vehicles WHERE status = 'available' AND NOT EXISTS (SELECT 1 FROM assignments a WHERE a.vehicle_id = vehicles.vehicle_id AND a.released_at IS NULL)").fetchone()[0]
        total_avail_drv = conn.execute("SELECT COUNT(*) FROM drivers WHERE availability_status = 'available' AND NOT EXISTS (SELECT 1 FROM assignments a WHERE a.driver_id = drivers.driver_id AND a.released_at IS NULL)").fetchone()[0]

        for d in all_pending:
            req_cap = d.get("required_capacity")
            reasons = []

            if total_avail_drv == 0:
                reasons.append("Zero drivers available in fleet.")

            if total_avail_veh == 0:
                reasons.append("Zero vehicles available in fleet.")
            elif req_cap:
                matching_veh = conn.execute(
                    """
                    SELECT COUNT(*) FROM vehicles v
                    WHERE v.status = 'available'
                      AND v.capacity >= ?
                      AND NOT EXISTS (SELECT 1 FROM assignments a WHERE a.vehicle_id = v.vehicle_id AND a.released_at IS NULL)
                    """,
                    (req_cap,),
                ).fetchone()[0]
                if matching_veh == 0:
                    max_cap = conn.execute("SELECT MAX(capacity) FROM vehicles WHERE status = 'available'").fetchone()[0] or 0
                    reasons.append(f"Insufficient capacity: required {req_cap} kg, highest available vehicle capacity is {max_cap} kg.")

            if reasons:
                d["block_reasons"] = reasons
                blocked.append(enrich_delivery_sla(d))

        return {"count": len(blocked), "blocked_deliveries": blocked}


@app.post("/deliveries/auto-assign")
def auto_assign_all(request: Request, dry_run: bool = Query(True)):
    user = get_current_user(request)
    check_permission(user, "assign", request=request)

    with read_conn() as conn:
        delivs = conn.execute(
            """
            SELECT * FROM deliveries
            WHERE status = 'pending'
              AND NOT EXISTS (SELECT 1 FROM assignments a WHERE a.delivery_id = deliveries.delivery_id AND a.released_at IS NULL)
            """
        ).fetchall()
        pending_list = [dict(r) for r in delivs]

    # Sort urgent first, then scheduled_time
    pending_list.sort(key=lambda d: (
        -({"urgent": 4, "high": 3, "normal": 2, "low": 1}.get(d.get("priority", "normal"), 2)),
        d.get("scheduled_time", ""),
    ))

    plan = []
    assigned_count = 0
    failures = []

    if dry_run:
        with read_conn() as conn:
            used_vehicles = set()
            used_drivers = set()
            for d in pending_list:
                rec = get_recommendations_for_delivery(d["delivery_id"], conn)
                candidates = [
                    c for c in rec.get("recommendations", [])
                    if c["vehicle"]["vehicle_id"] not in used_vehicles and c["driver"]["driver_id"] not in used_drivers
                ]
                if candidates:
                    chosen = candidates[0]
                    used_vehicles.add(chosen["vehicle"]["vehicle_id"])
                    used_drivers.add(chosen["driver"]["driver_id"])
                    plan.append({
                        "delivery_id": d["delivery_id"],
                        "vehicle_id": chosen["vehicle"]["vehicle_id"],
                        "driver_id": chosen["driver"]["driver_id"],
                        "score": chosen["total_score"],
                        "reason": chosen["reason"],
                    })
                else:
                    failures.append({"delivery_id": d["delivery_id"], "reason": "No unreserved eligible vehicle/driver available."})
        return {
            "dry_run": True,
            "total_pending": len(pending_list),
            "matchable_count": len(plan),
            "plan": plan,
            "failures": failures,
        }

    # Real Commit: execute each match in an atomic transaction
    results = []
    for d in pending_list:
        with read_conn() as conn:
            rec = get_recommendations_for_delivery(d["delivery_id"], conn)
            cands = rec.get("recommendations", [])
            if not cands:
                failures.append({"delivery_id": d["delivery_id"], "reason": "No eligible vehicle or driver available at execution time."})
                continue
            chosen = cands[0]

        try:
            assign_req = AssignRequest(vehicle_id=chosen["vehicle"]["vehicle_id"], driver_id=chosen["driver"]["driver_id"])
            asg = assign_delivery(d["delivery_id"], assign_req, request=request)
            results.append(asg)
            assigned_count += 1
        except Exception as e:
            failures.append({"delivery_id": d["delivery_id"], "reason": str(e)})

    return {
        "dry_run": False,
        "total_pending": len(pending_list),
        "assigned_count": assigned_count,
        "assigned": results,
        "failures": failures,
    }


# -------------------------------------------------------------------------
# ASSIGNMENT LOGIC (CORE RULE ENGINE + IDEMPOTENCY + STALE-STATE)
# -------------------------------------------------------------------------
@app.post("/deliveries/{delivery_id}/assign", status_code=201)
def assign_delivery(
    delivery_id: str,
    body: AssignRequest,
    request: Request,
):
    """
    Atomically assign a vehicle and driver to a pending delivery.
    Opens transaction with BEGIN IMMEDIATE, re-reading and re-validating everything.
    Supports Idempotency-Key and If-Match stale-state protection.
    """
    user = get_current_user(request) if request else None
    check_permission(user, "assign", request=request)
    actor = user["username"] if user else "operator"

    idempotency_key = request.headers.get("Idempotency-Key") if request else None
    if_match = request.headers.get("If-Match") if request else None

    payload_hash = hashlib.sha256(f"ASSIGN:{delivery_id}:{body.vehicle_id}:{body.driver_id}".encode()).hexdigest()

    # 0. Check Idempotency-Key
    if idempotency_key:
        with read_conn() as conn:
            existing_key = conn.execute("SELECT * FROM idempotency_keys WHERE key = ?", (idempotency_key,)).fetchone()
            if existing_key:
                if existing_key["request_hash"] == payload_hash:
                    # Return original cached response directly
                    cached_body = json.loads(existing_key["response_body"])
                    return JSONResponse(status_code=existing_key["response_status"], content=cached_body)
                else:
                    raise AppError(409, "CONFLICT", f"Idempotency-Key '{idempotency_key}' reused with different request payload.")

    with immediate_transaction() as conn:
        # 1. Fetch delivery
        del_row = conn.execute("SELECT * FROM deliveries WHERE delivery_id = ?", (delivery_id,)).fetchone()
        if not del_row:
            raise AppError(404, "NOT_FOUND", f"Delivery '{delivery_id}' does not exist.")
        delivery = dict(del_row)

        # Stale-state version check (If-Match or body.version)
        req_version = body.version
        if if_match:
            try:
                clean_im = if_match.strip().strip('"')
                req_version = int(clean_im)
            except Exception:
                pass

        if req_version is not None and delivery["version"] != req_version:
            raise AppError(
                409,
                "STALE_STATE",
                f"Delivery version mismatch. Current version is {delivery['version']}, requested was {req_version}.",
            )

        # 2. Check if delivery is pending
        active_del_asg = conn.execute(
            "SELECT assignment_id FROM assignments WHERE delivery_id = ? AND released_at IS NULL",
            (delivery_id,),
        ).fetchone()

        if delivery["status"] != "pending" or active_del_asg:
            raise AppError(
                409,
                "DELIVERY_NOT_PENDING",
                f"Delivery '{delivery_id}' is currently '{delivery['status']}' and cannot be assigned.",
            )

        # 3. Fetch vehicle & driver
        veh_row = conn.execute("SELECT * FROM vehicles WHERE vehicle_id = ?", (body.vehicle_id,)).fetchone()
        if not veh_row:
            raise AppError(404, "NOT_FOUND", f"Vehicle '{body.vehicle_id}' does not exist.")
        vehicle = dict(veh_row)

        drv_row = conn.execute("SELECT * FROM drivers WHERE driver_id = ?", (body.driver_id,)).fetchone()
        if not drv_row:
            raise AppError(404, "NOT_FOUND", f"Driver '{body.driver_id}' does not exist.")
        driver = dict(drv_row)

        # 4. Check vehicle availability & active assignments
        veh_active_asg = conn.execute(
            "SELECT assignment_id, delivery_id FROM assignments WHERE vehicle_id = ? AND released_at IS NULL",
            (body.vehicle_id,),
        ).fetchone()
        veh_occupied = bool(veh_active_asg)
        veh_available = vehicle["status"] == "available" and not veh_occupied

        # 5. Check driver availability & active assignments
        drv_active_asg = conn.execute(
            "SELECT assignment_id, delivery_id FROM assignments WHERE driver_id = ? AND released_at IS NULL",
            (body.driver_id,),
        ).fetchone()
        drv_occupied = bool(drv_active_asg)
        drv_available = driver["availability_status"] == "available" and not drv_occupied

        veh_reason = None
        if not veh_available:
            if veh_occupied:
                veh_reason = f"Vehicle '{body.vehicle_id}' is occupied by active delivery {veh_active_asg['delivery_id']}"
            else:
                veh_reason = f"Vehicle '{body.vehicle_id}' is in status '{vehicle['status']}'"

        drv_reason = None
        if not drv_available:
            if drv_occupied:
                drv_reason = f"Driver '{body.driver_id}' is occupied by active delivery {drv_active_asg['delivery_id']}"
            else:
                drv_reason = f"Driver '{body.driver_id}' is in status '{driver['availability_status']}'"

        if not veh_available and not drv_available:
            raise AppError(
                409,
                "RESOURCES_UNAVAILABLE",
                f"Both resources unavailable: {veh_reason}; {drv_reason}.",
            )

        if not veh_available:
            raise AppError(409, "VEHICLE_UNAVAILABLE", veh_reason or "Vehicle unavailable.")

        if not drv_available:
            raise AppError(409, "DRIVER_UNAVAILABLE", drv_reason or "Driver unavailable.")

        # 6. Check Capacity
        req_cap = delivery.get("required_capacity")
        if req_cap is not None and vehicle["capacity"] < req_cap:
            raise AppError(
                409,
                "CAPACITY_MISMATCH",
                f"Vehicle capacity ({vehicle['capacity']} kg) is insufficient for required capacity ({req_cap} kg).",
            )

        # 7. Atomic Insert and State Mutation
        asg_id = f"ASG-{uuid.uuid4().hex[:8].upper()}"
        now_str = utc_now_iso()

        conn.execute(
            """
            INSERT INTO assignments (assignment_id, delivery_id, vehicle_id, driver_id, assigned_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (asg_id, delivery_id, body.vehicle_id, body.driver_id, now_str),
        )

        conn.execute("UPDATE vehicles SET status = 'assigned' WHERE vehicle_id = ?", (body.vehicle_id,))
        conn.execute("UPDATE drivers SET availability_status = 'assigned' WHERE driver_id = ?", (body.driver_id,))
        conn.execute("UPDATE deliveries SET status = 'assigned', version = version + 1 WHERE delivery_id = ?", (delivery_id,))

        after_asg = {
            "assignment_id": asg_id,
            "delivery_id": delivery_id,
            "vehicle_id": body.vehicle_id,
            "driver_id": body.driver_id,
            "status": "assigned",
            "assigned_at": now_str,
            "new_version": delivery["version"] + 1,
        }
        write_audit(
            conn,
            actor=actor,
            action="assign",
            entity="assignment",
            entity_id=asg_id,
            after={
                "assignment": after_asg,
                "delivery_id": delivery_id,
                "vehicle_id": body.vehicle_id,
                "driver_id": body.driver_id,
            },
        )

        # Save idempotency record
        if idempotency_key:
            conn.execute(
                """
                INSERT INTO idempotency_keys (key, request_hash, response_status, response_body, created_at)
                VALUES (?, ?, 201, ?, ?)
                """,
                (idempotency_key, payload_hash, json.dumps(after_asg), now_str),
            )

    broadcast_event("delivery_assigned", after_asg)
    return after_asg


# -------------------------------------------------------------------------
# DELIVERY STATUS TRANSITIONS
# -------------------------------------------------------------------------
ALLOWED_TRANSITIONS = {
    # pending -> assigned is handled exclusively by POST /deliveries/{id}/assign
    "assigned": {"in_transit", "cancelled"},
    "in_transit": {"delivered"},
    "pending": {"cancelled"},
}


@app.patch("/deliveries/{delivery_id}/status")
def patch_delivery_status(
    delivery_id: str,
    body: DeliveryStatusPatch,
    request: Request,
):
    user = get_current_user(request) if request else None
    check_permission(user, "status", request=request)
    actor = user["username"] if user else "operator"

    idempotency_key = request.headers.get("Idempotency-Key") if request else None
    if_match = request.headers.get("If-Match") if request else None

    target_status = body.status.strip().lower()
    payload_hash = hashlib.sha256(f"STATUS:{delivery_id}:{target_status}".encode()).hexdigest()

    if idempotency_key:
        with read_conn() as conn:
            existing_key = conn.execute("SELECT * FROM idempotency_keys WHERE key = ?", (idempotency_key,)).fetchone()
            if existing_key:
                if existing_key["request_hash"] == payload_hash:
                    cached_body = json.loads(existing_key["response_body"])
                    return JSONResponse(status_code=existing_key["response_status"], content=cached_body)
                else:
                    raise AppError(409, "CONFLICT", f"Idempotency-Key '{idempotency_key}' reused with different request payload.")

    with immediate_transaction() as conn:
        del_row = conn.execute("SELECT * FROM deliveries WHERE delivery_id = ?", (delivery_id,)).fetchone()
        if not del_row:
            raise AppError(404, "NOT_FOUND", f"Delivery '{delivery_id}' does not exist.")
        delivery = dict(del_row)
        current_status = delivery["status"]

        # Version check
        req_version = body.version
        if if_match:
            try:
                clean_im = if_match.strip().strip('"')
                req_version = int(clean_im)
            except Exception:
                pass

        if req_version is not None and delivery["version"] != req_version:
            raise AppError(
                409,
                "STALE_STATE",
                f"Delivery version mismatch. Current version is {delivery['version']}, requested was {req_version}.",
            )

        allowed_next = ALLOWED_TRANSITIONS.get(current_status, set())
        if target_status not in allowed_next:
            raise AppError(
                409,
                "INVALID_TRANSITION",
                f"Transition from '{current_status}' to '{target_status}' is not permitted. (Allowed: {', '.join(sorted(allowed_next)) if allowed_next else 'None'})",
            )

        now_str = utc_now_iso()

        # If transitioning to delivered or cancelled: release resources atomically
        if target_status in ("delivered", "cancelled"):
            asg_row = conn.execute(
                "SELECT * FROM assignments WHERE delivery_id = ? AND released_at IS NULL",
                (delivery_id,),
            ).fetchone()

            if asg_row:
                asg = dict(asg_row)
                conn.execute(
                    """
                    UPDATE assignments
                    SET released_at = ?, release_reason = ?
                    WHERE assignment_id = ?
                    """,
                    (now_str, target_status, asg["assignment_id"]),
                )
                conn.execute("UPDATE vehicles SET status = 'available' WHERE vehicle_id = ?", (asg["vehicle_id"],))
                conn.execute("UPDATE drivers SET availability_status = 'available' WHERE driver_id = ?", (asg["driver_id"],))

        new_version = delivery["version"] + 1
        conn.execute("UPDATE deliveries SET status = ?, version = ? WHERE delivery_id = ?", (target_status, new_version, delivery_id))

        after_data = {**delivery, "status": target_status, "version": new_version}
        write_audit(
            conn,
            actor=actor,
            action="update_status",
            entity="delivery",
            entity_id=delivery_id,
            before=delivery,
            after=after_data,
        )

        if idempotency_key:
            conn.execute(
                """
                INSERT INTO idempotency_keys (key, request_hash, response_status, response_body, created_at)
                VALUES (?, ?, 200, ?, ?)
                """,
                (idempotency_key, payload_hash, json.dumps(after_data), now_str),
            )

    broadcast_event("delivery_status_changed", after_data)
    return enrich_delivery_sla(after_data)


# -------------------------------------------------------------------------
# CSV EXPORT PIPELINE (FORMULA INJECTION SAFE - B8)
# -------------------------------------------------------------------------
@app.get("/export/{entity}.csv")
def export_csv(entity: str):
    ent = entity.strip().lower()
    if ent not in ("vehicles", "drivers", "deliveries", "audit"):
        raise AppError(404, "NOT_FOUND", f"Unknown export entity '{entity}'.")

    with read_conn() as conn:
        if ent == "vehicles":
            rows = conn.execute("SELECT vehicle_id, registration_no, type, capacity, status FROM vehicles ORDER BY vehicle_id").fetchall()
            fieldnames = ["vehicle_id", "registration_no", "type", "capacity", "status"]
        elif ent == "drivers":
            rows = conn.execute("SELECT driver_id, name, phone, availability_status FROM drivers ORDER BY driver_id").fetchall()
            fieldnames = ["driver_id", "name", "phone", "availability_status"]
        elif ent == "deliveries":
            rows = conn.execute("SELECT delivery_id, pickup, dropoff, scheduled_time, priority, required_capacity, status, version FROM deliveries ORDER BY delivery_id").fetchall()
            fieldnames = ["delivery_id", "pickup", "dropoff", "scheduled_time", "priority", "required_capacity", "status", "version"]
        else:
            rows = conn.execute("SELECT id, ts, actor, action, entity, entity_id, before_json, after_json FROM audit_log ORDER BY id DESC").fetchall()
            fieldnames = ["id", "ts", "actor", "action", "entity", "entity_id", "before_json", "after_json"]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(fieldnames)

    for r in rows:
        row_dict = dict(r)
        # Apply formula injection sanitization on every single cell
        sanitized_row = [sanitize_csv_cell(row_dict.get(fn)) for fn in fieldnames]
        writer.writerow(sanitized_row)

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="fleetwise_{ent}_export.csv"'},
    )


# -------------------------------------------------------------------------
# IMPORT PIPELINE
# -------------------------------------------------------------------------
@app.get("/import/templates/{entity}.csv")
def download_template(entity: str):
    ent = entity.strip().lower()
    if ent not in TEMPLATES:
        raise AppError(404, "NOT_FOUND", f"Unknown template entity '{entity}'. Choose from vehicles, drivers, deliveries.")
    return PlainTextResponse(
        content=TEMPLATES[ent],
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{ent}_template.csv"'},
    )


@app.post("/import/{entity}")
async def import_entity(
    entity: str,
    request: Request,
    file: UploadFile = File(...),
    dry_run: bool = Query(True),
):
    user = get_current_user(request) if request else None
    check_permission(user, "import", request=request)
    actor = user["username"] if user else "operator"

    ent = entity.strip().lower()
    if ent not in ("vehicles", "drivers", "deliveries"):
        raise AppError(400, "VALIDATION_ERROR", f"Invalid import entity '{entity}'. Must be vehicles, drivers, or deliveries.")

    content = await file.read()
    raw_rows = parse_upload_content(file.filename or "", content)

    if not raw_rows:
        return {
            "entity": ent,
            "dry_run": dry_run,
            "total_rows": 0,
            "valid_rows": 0,
            "invalid_rows": 0,
            "errors": [],
            "rows": [],
            "inserted_count": 0,
        }

    with immediate_transaction() as conn:
        if ent == "vehicles":
            val_rows, errors = validate_vehicles_rows(raw_rows, conn)
        elif ent == "drivers":
            val_rows, errors = validate_drivers_rows(raw_rows, conn)
        else:
            val_rows, errors = validate_deliveries_rows(raw_rows, conn)

        total_rows = len(val_rows)
        invalid_rows = len({e["row"] for e in errors})
        valid_rows = total_rows - invalid_rows

        if dry_run:
            conn.execute("ROLLBACK")
            return {
                "entity": ent,
                "dry_run": True,
                "total_rows": total_rows,
                "valid_rows": valid_rows,
                "invalid_rows": invalid_rows,
                "errors": errors,
                "rows": val_rows,
                "inserted_count": 0,
            }

        # Commit run: must be 100% valid
        if invalid_rows > 0:
            conn.execute("ROLLBACK")
            raise AppError(
                400,
                "VALIDATION_ERROR",
                f"Import rejected: {invalid_rows} invalid row(s) detected. All rows must be valid for atomic commit.",
            )

        # Insert all rows
        if ent == "vehicles":
            for r in val_rows:
                d = r["data"]
                conn.execute(
                    "INSERT INTO vehicles (vehicle_id, registration_no, type, capacity, status) VALUES (?, ?, ?, ?, ?)",
                    (d["vehicle_id"], d["registration_no"], d["type"], d["capacity"], d["status"]),
                )
        elif ent == "drivers":
            for r in val_rows:
                d = r["data"]
                conn.execute(
                    "INSERT INTO drivers (driver_id, name, phone, availability_status) VALUES (?, ?, ?, ?)",
                    (d["driver_id"], d["name"], d["phone"], d["availability_status"]),
                )
        else:
            for r in val_rows:
                d = r["data"]
                conn.execute(
                    """
                    INSERT INTO deliveries (delivery_id, pickup, dropoff, scheduled_time, priority, required_capacity, status, created_at, version, pickup_lat, pickup_lng, drop_lat, drop_lng)
                    VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, 1, ?, ?, ?, ?)
                    """,
                    (d["delivery_id"], d["pickup"], d["dropoff"], d["scheduled_time"], d["priority"], d["required_capacity"], d["created_at"], d.get("pickup_lat"), d.get("pickup_lng"), d.get("drop_lat"), d.get("drop_lng")),
                )

        write_audit(
            conn,
            actor=actor,
            action="import",
            entity=ent,
            entity_id=f"BATCH-{total_rows}",
            after={"count": total_rows, "filename": file.filename},
        )

    broadcast_event(f"{ent}_imported", {"count": total_rows})
    return {
        "entity": ent,
        "dry_run": False,
        "total_rows": total_rows,
        "valid_rows": valid_rows,
        "invalid_rows": 0,
        "errors": [],
        "inserted_count": total_rows,
    }


# -------------------------------------------------------------------------
# RACE LAB: PARALLEL ASSIGNMENT CONCURRENCY STRESS TEST (B4)
# -------------------------------------------------------------------------
@app.post("/diagnostics/concurrency-test")
def run_concurrency_race_lab(workers: int = Query(20, ge=2, le=100)):
    """
    Executes N parallel assignment attempts against an ISOLATED temporary database
    (never touching real database data), returning full thread metrics and timeline.
    Proves that at most 1 attempt succeeds and all N-1 get 409 Conflict.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        temp_db_path = str(Path(tmp_dir) / "race_lab_isolated.db")
        init_db(temp_db_path)

        # Seed isolated test resources
        with immediate_transaction(temp_db_path) as conn:
            conn.execute("INSERT INTO vehicles (vehicle_id, registration_no, type, capacity, status) VALUES ('V-RACE', 'KA-RACE-01', 'Van', 2000, 'available')")
            conn.execute("INSERT INTO drivers (driver_id, name, phone, availability_status) VALUES ('DR-RACE', 'Race Driver', '+91-9999999999', 'available')")
            for i in range(1, workers + 1):
                conn.execute(
                    "INSERT INTO deliveries (delivery_id, pickup, dropoff, scheduled_time, priority, required_capacity, status, created_at, version) VALUES (?, 'Start', 'Goal', '2026-10-30T10:00:00Z', 'urgent', 1000, 'pending', '2026-10-29T12:00:00Z', 1)",
                    (f"D-RACE-{i:03d}",),
                )

        timeline = []
        t_start = time.perf_counter()

        def worker_task(del_id: str) -> dict[str, Any]:
            w_start = time.perf_counter()
            conn = get_connection(temp_db_path)
            try:
                conn.execute("BEGIN IMMEDIATE")
                # Re-validate
                deliv = conn.execute("SELECT status FROM deliveries WHERE delivery_id = ?", (del_id,)).fetchone()
                if not deliv or deliv["status"] != "pending":
                    conn.execute("ROLLBACK")
                    return {"delivery_id": del_id, "status_code": 409, "error": "DELIVERY_NOT_PENDING", "duration_ms": round((time.perf_counter() - w_start) * 1000, 2)}
                veh_asg = conn.execute("SELECT assignment_id FROM assignments WHERE vehicle_id = 'V-RACE' AND released_at IS NULL").fetchone()
                drv_asg = conn.execute("SELECT assignment_id FROM assignments WHERE driver_id = 'DR-RACE' AND released_at IS NULL").fetchone()

                if veh_asg or drv_asg:
                    conn.execute("ROLLBACK")
                    return {"delivery_id": del_id, "status_code": 409, "error": "RESOURCES_UNAVAILABLE", "duration_ms": round((time.perf_counter() - w_start) * 1000, 2)}

                # Perform assignment
                asg_id = f"ASG-{uuid.uuid4().hex[:6].upper()}"
                conn.execute("INSERT INTO assignments (assignment_id, delivery_id, vehicle_id, driver_id, assigned_at) VALUES (?, ?, 'V-RACE', 'DR-RACE', datetime('now'))", (asg_id, del_id))
                conn.execute("UPDATE vehicles SET status = 'assigned' WHERE vehicle_id = 'V-RACE'")
                conn.execute("UPDATE drivers SET availability_status = 'assigned' WHERE driver_id = 'DR-RACE'")
                conn.execute("UPDATE deliveries SET status = 'assigned' WHERE delivery_id = ?", (del_id,))
                conn.execute("COMMIT")
                return {"delivery_id": del_id, "status_code": 201, "assignment_id": asg_id, "duration_ms": round((time.perf_counter() - w_start) * 1000, 2)}
            except Exception as exc:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                return {"delivery_id": del_id, "status_code": 500, "error": str(exc), "duration_ms": round((time.perf_counter() - w_start) * 1000, 2)}
            finally:
                conn.close()

        deliv_ids = [f"D-RACE-{i:03d}" for i in range(1, workers + 1)]
        with ThreadPoolExecutor(max_workers=workers) as executor:
            timeline = list(executor.map(worker_task, deliv_ids))

        total_duration = round((time.perf_counter() - t_start) * 1000, 2)
        successes = [t for t in timeline if t["status_code"] == 201]
        conflicts = [t for t in timeline if t["status_code"] == 409]
        errors = [t for t in timeline if t["status_code"] >= 500]

        return {
            "test_name": "Race Lab Concurrency Stress Test",
            "workers_dispatched": workers,
            "success_count": len(successes),
            "conflict_count": len(conflicts),
            "error_count": len(errors),
            "total_duration_ms": total_duration,
            "winner_delivery": successes[0]["delivery_id"] if successes else None,
            "core_invariant_preserved": len(successes) == 1 and len(errors) == 0,
            "guarantee": "SQLite BEGIN IMMEDIATE serialization + partial unique index guaranteed exactly one winner with zero corruptions.",
            "timeline": timeline,
        }


# -------------------------------------------------------------------------
# ANALYTICS & ROUTE VIEW (B6 & B7)
# -------------------------------------------------------------------------
@app.get("/analytics/summary")
def get_analytics_summary():
    with read_conn() as conn:
        total_veh = conn.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0]
        assigned_veh = conn.execute("SELECT COUNT(*) FROM vehicles WHERE status = 'assigned'").fetchone()[0]
        total_del = conn.execute("SELECT COUNT(*) FROM deliveries").fetchone()[0]
        delivered_del = conn.execute("SELECT COUNT(*) FROM deliveries WHERE status = 'delivered'").fetchone()[0]
        pending_del = conn.execute("SELECT COUNT(*) FROM deliveries WHERE status = 'pending'").fetchone()[0]
        in_transit_del = conn.execute("SELECT COUNT(*) FROM deliveries WHERE status = 'in_transit'").fetchone()[0]
        cancelled_del = conn.execute("SELECT COUNT(*) FROM deliveries WHERE status = 'cancelled'").fetchone()[0]

        driver_workload = [
            dict(r)
            for r in conn.execute(
                """
                SELECT d.name, COUNT(a.assignment_id) as total_trips
                FROM drivers d
                LEFT JOIN assignments a ON a.driver_id = d.driver_id
                GROUP BY d.driver_id
                ORDER BY total_trips DESC LIMIT 8
                """
            ).fetchall()
        ]

    on_time_pct = round((delivered_del / total_del * 100.0), 1) if total_del > 0 else 100.0
    util_pct = round((assigned_veh / total_veh * 100.0), 1) if total_veh > 0 else 0.0

    return {
        "utilisation_pct": util_pct,
        "on_time_pct": on_time_pct,
        "funnel": {
            "pending": pending_del,
            "assigned": assigned_veh,
            "in_transit": in_transit_del,
            "delivered": delivered_del,
            "cancelled": cancelled_del,
        },
        "driver_workload": driver_workload,
    }


@app.get("/analytics/overview")
def get_analytics_overview():
    """Executive operational overview combining fleet, driver, and delivery KPIs."""
    with read_conn() as conn:
        fleet = analyze_fleet_utilization(conn)
        drivers = analyze_driver_utilization(conn)
        deliveries = analyze_delivery_performance(conn)
        anomalies = detect_operational_anomalies(conn, limit=5)

    return {
        "fleet": fleet,
        "drivers": drivers,
        "deliveries": deliveries,
        "recent_anomalies_count": len(anomalies),
        "recent_anomalies": anomalies,
        "timestamp": utc_now_iso(),
    }


@app.get("/analytics/fleet")
def get_fleet_analytics():
    """Fleet utilization breakdown and operational performance per vehicle."""
    with read_conn() as conn:
        utilization = analyze_fleet_utilization(conn)
        vehicles = analyze_vehicle_performance(conn)
    return {
        "utilization": utilization,
        "vehicles": vehicles,
        "timestamp": utc_now_iso(),
    }


@app.get("/analytics/drivers")
def get_driver_analytics():
    """Driver utilization and individual performance metrics."""
    with read_conn() as conn:
        utilization = analyze_driver_utilization(conn)
        drivers = analyze_driver_performance(conn)
    return {
        "utilization": utilization,
        "drivers": drivers,
        "timestamp": utc_now_iso(),
    }


@app.get("/analytics/deliveries")
def get_delivery_analytics():
    """Comprehensive delivery completion and on-time performance breakdown."""
    with read_conn() as conn:
        perf = analyze_delivery_performance(conn)
    return {**perf, "timestamp": utc_now_iso()}


@app.get("/analytics/telemetry")
def get_telemetry_analytics():
    """Aggregated telemetry volume, quality distribution, and kinematics statistics."""
    with read_conn() as conn:
        stats = conn.execute(
            """
            SELECT 
                COUNT(*) as total_fixes,
                COUNT(DISTINCT session_id) as total_sessions,
                COUNT(DISTINCT driver_id) as drivers_tracked,
                AVG(CASE WHEN accuracy IS NOT NULL THEN accuracy ELSE NULL END) as avg_accuracy_m,
                SUM(CASE WHEN is_implausible_jump = 1 THEN 1 ELSE 0 END) as jump_anomalies,
                SUM(CASE WHEN quality_flag = 'accepted' THEN 1 ELSE 0 END) as accepted_fixes,
                SUM(CASE WHEN quality_flag = 'low_accuracy' THEN 1 ELSE 0 END) as low_accuracy_fixes,
                SUM(CASE WHEN quality_flag = 'stale' THEN 1 ELSE 0 END) as stale_fixes,
                SUM(CASE WHEN quality_flag = 'out_of_order' THEN 1 ELSE 0 END) as out_of_order_fixes,
                SUM(CASE WHEN quality_flag = 'duplicate' THEN 1 ELSE 0 END) as duplicate_fixes
            FROM gps_locations
            """
        ).fetchone()

        recent_fixes = [dict(r) for r in conn.execute(
            "SELECT location_id, session_id, driver_id, vehicle_id, latitude, longitude, accuracy, speed, quality_flag, server_timestamp FROM gps_locations ORDER BY server_timestamp DESC LIMIT 10"
        ).fetchall()]

    return {
        "summary": dict(stats),
        "recent_fixes": recent_fixes,
        "timestamp": utc_now_iso(),
    }


@app.get("/analytics/accuracy")
def get_accuracy_analytics():
    """Calculates granular Telemetry Quality Scores across active tracking sessions."""
    with read_conn() as conn:
        sessions = conn.execute(
            "SELECT session_id, driver_id, vehicle_id, status FROM tracking_sessions ORDER BY started_at DESC LIMIT 10"
        ).fetchall()

        session_scores = []
        for s in sessions:
            sid = s["session_id"]
            rows = conn.execute(
                "SELECT * FROM gps_locations WHERE session_id = ? ORDER BY server_timestamp DESC LIMIT 2",
                (sid,),
            ).fetchall()
            if rows:
                curr = dict(rows[0])
                prev = dict(rows[1]) if len(rows) > 1 else None
                score_data = calculate_telemetry_quality_score(curr, prev)
                session_scores.append({
                    "session_id": sid,
                    "driver_id": s["driver_id"],
                    "vehicle_id": s["vehicle_id"],
                    "status": s["status"],
                    "telemetry_quality": score_data,
                })

    return {
        "sessions_analyzed": len(session_scores),
        "session_scores": session_scores,
        "formula_description": "Telemetry Quality Score = 0.40 * GPS Quality + 0.30 * Freshness + 0.20 * Movement + 0.10 * Completeness",
        "timestamp": utc_now_iso(),
    }


@app.get("/analytics/confidence")
def get_confidence_analytics():
    """Calculates Evidence Confidence Scores across device identity and active fleet assignments."""
    with read_conn() as conn:
        # 1. Device identity confidence
        dev_rows = conn.execute(
            "SELECT d.*, dr.phone_verification_status FROM devices d JOIN drivers dr ON dr.driver_id = d.driver_id ORDER BY d.last_seen_at DESC LIMIT 15"
        ).fetchall()
        device_evals = []
        for d in dev_rows:
            conf = evaluate_device_identity_confidence(
                is_authenticated=True,
                has_registered_device=True,
                is_revoked=bool(d["is_revoked"]),
                token_type=d["identity_confidence"],
                phone_verified=d["phone_verification_status"] == "verified",
                driver_id_match=True,
            )
            device_evals.append({
                "device_id": d["device_id"],
                "driver_id": d["driver_id"],
                "nickname": d["nickname"],
                "confidence": conf,
            })

        # 2. Assignment confidence for pending deliveries
        pending_dels = conn.execute("SELECT * FROM deliveries WHERE status = 'pending' LIMIT 5").fetchall()
        assignment_evals = []
        for d in pending_dels:
            rec_result = get_recommendations_for_delivery(d["delivery_id"], conn)
            recs = rec_result.get("recommendations", [])
            if recs:
                top = recs[0]
                conf = evaluate_assignment_confidence(
                    vehicle=top["vehicle"],
                    driver=top["driver"],
                    delivery=dict(d),
                    has_active_vehicle_assignment=False,
                    has_active_driver_assignment=False,
                )
                assignment_evals.append({
                    "delivery_id": d["delivery_id"],
                    "recommended_pair": {"vehicle_id": top["vehicle"]["vehicle_id"], "driver_id": top["driver"]["driver_id"]},
                    "confidence": conf,
                })

    return {
        "device_identity_confidence": device_evals,
        "assignment_confidence": assignment_evals,
        "label": "Evidence Confidence Score — Heuristic",
        "timestamp": utc_now_iso(),
    }


@app.get("/analytics/anomalies")
def get_anomalies_analytics(limit: int = Query(50, ge=1, le=200)):
    """Retrieves operational and kinematic anomalies detected across telemetry and events."""
    with read_conn() as conn:
        anomalies = detect_operational_anomalies(conn, limit=limit)
    return {
        "anomalies_count": len(anomalies),
        "anomalies": anomalies,
        "timestamp": utc_now_iso(),
    }


@app.get("/analytics/vehicles/{vehicle_id}")
def get_single_vehicle_analytics(vehicle_id: str):
    """Detailed operational metrics and telemetry stats for a single vehicle."""
    with read_conn() as conn:
        res = analyze_vehicle_performance(conn, vehicle_id=vehicle_id)
        if not res:
            raise AppError(404, "NOT_FOUND", f"Vehicle '{vehicle_id}' not found.")
    return res[0]


@app.get("/analytics/drivers/{driver_id}")
def get_single_driver_analytics(driver_id: str):
    """Detailed operational metrics and delivery performance for a single driver."""
    with read_conn() as conn:
        res = analyze_driver_performance(conn, driver_id=driver_id)
        if not res:
            raise AppError(404, "NOT_FOUND", f"Driver '{driver_id}' not found.")
    return res[0]



@app.get("/deliveries/routes")
def get_routes():
    with read_conn() as conn:
        rows = conn.execute(
            """
            SELECT d.delivery_id, d.pickup, d.dropoff, d.status, d.priority,
                   d.pickup_lat, d.pickup_lng, d.drop_lat, d.drop_lng,
                   a.vehicle_id, a.driver_id
            FROM deliveries d
            LEFT JOIN assignments a ON a.delivery_id = d.delivery_id AND a.released_at IS NULL
            WHERE d.status IN ('assigned', 'in_transit')
               OR (d.pickup_lat IS NOT NULL AND d.drop_lat IS NOT NULL)
            LIMIT 50
            """
        ).fetchall()
        return [dict(r) for r in rows]


# -------------------------------------------------------------------------
# AUTHENTICATED DEVICE INVENTORY & MANAGEMENT (PHASE 2)
# -------------------------------------------------------------------------
@app.post("/devices/register", status_code=201)
def register_device(body: DeviceRegisterRequest, request: Request):
    user = get_current_user(request)
    check_permission(user, "drivers", request=request)
    actor = user["username"] if user else "operator"

    client_ip = request.client.host if request.client else "127.0.0.1"

    with immediate_transaction() as conn:
        drv = conn.execute("SELECT * FROM drivers WHERE driver_id = ?", (body.driver_id,)).fetchone()
        if not drv:
            raise AppError(404, "NOT_FOUND", f"Driver '{body.driver_id}' not found.")

        now_str = utc_now_iso()
        caps_str = json.dumps(body.capabilities or {})

        # 1. Reject if this persistent client token was permanently revoked
        if body.client_device_token:
            rev_row = conn.execute(
                "SELECT device_id FROM devices WHERE client_device_token = ? AND is_revoked = 1",
                (body.client_device_token,),
            ).fetchone()
            if rev_row:
                raise AppError(403, "DEVICE_REVOKED", f"Device '{rev_row['device_id']}' has been permanently revoked.")

        # 2. Check for existing active device:
        # Prioritize persistent client_device_token (differentiates multiple physical phones of the same driver)
        existing = None
        if body.client_device_token:
            existing = conn.execute(
                "SELECT * FROM devices WHERE client_device_token = ? AND is_revoked = 0 ORDER BY registered_at DESC LIMIT 1",
                (body.client_device_token,),
            ).fetchone()
        if not existing:
            existing = conn.execute(
                """
                SELECT * FROM devices 
                WHERE driver_id = ? AND nickname = ? AND is_revoked = 0 
                ORDER BY registered_at DESC LIMIT 1
                """,
                (body.driver_id, body.nickname),
            ).fetchone()

        confidence = body.identity_confidence or ("client_storage_token" if body.client_device_token else "ephemeral_session")
        limitations = body.detection_limitations or "Browser storage token. Private browsing or clearing storage resets token."

        if existing:
            device_id = existing["device_id"]
            conn.execute(
                """
                UPDATE devices 
                SET driver_id = ?, nickname = ?, last_seen_at = ?, last_ip = ?, capabilities_json = ?, permission_status = ?,
                    device_category = COALESCE(?, device_category),
                    model = COALESCE(?, model),
                    os_family = COALESCE(?, os_family),
                    os_version = COALESCE(?, os_version),
                    browser_family = COALESCE(?, browser_family),
                    browser_version = COALESCE(?, browser_version),
                    platform = COALESCE(?, platform),
                    screen_res = COALESCE(?, screen_res),
                    client_device_token = COALESCE(?, client_device_token),
                    identity_confidence = ?,
                    detection_limitations = ?
                WHERE device_id = ?
                """,
                (
                    body.driver_id, body.nickname, now_str, client_ip, caps_str, body.permission_status,
                    body.device_category, body.model, body.os_family, body.os_version,
                    body.browser_family, body.browser_version, body.platform, body.screen_res,
                    body.client_device_token, confidence, limitations,
                    device_id,
                ),
            )
            device_profile = {
                "device_id": device_id,
                "driver_id": body.driver_id,
                "driver_name": drv["name"],
                "nickname": body.nickname,
                "device_category": body.device_category or existing["device_category"],
                "model": body.model or existing["model"],
                "os_family": body.os_family or existing["os_family"],
                "os_version": body.os_version or existing["os_version"],
                "browser_family": body.browser_family or existing["browser_family"],
                "browser_version": body.browser_version or existing["browser_version"],
                "platform": body.platform or existing["platform"],
                "screen_res": body.screen_res or existing["screen_res"],
                "client_device_token": body.client_device_token or existing["client_device_token"],
                "identity_confidence": confidence,
                "detection_limitations": limitations,
                "capabilities": body.capabilities or {},
                "permission_status": body.permission_status,
                "last_ip": client_ip,
                "registered_at": existing["registered_at"],
                "last_seen_at": now_str,
                "is_revoked": False,
                "is_reused": True,
            }
            write_audit(conn, actor=actor, action="update_device_registration", entity="device", entity_id=device_id, after=device_profile)
            broadcast_event("device_updated", device_profile)
            return device_profile

        device_id = f"DEV-{uuid.uuid4().hex[:8].upper()}"

        conn.execute(
            """
            INSERT INTO devices (
                device_id, driver_id, nickname, device_category, model,
                os_family, os_version, browser_family, browser_version,
                platform, screen_res, capabilities_json, permission_status,
                last_ip, registered_at, last_seen_at, is_revoked,
                client_device_token, identity_confidence, detection_limitations
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)
            """,
            (
                device_id,
                body.driver_id,
                body.nickname,
                body.device_category,
                body.model,
                body.os_family,
                body.os_version,
                body.browser_family,
                body.browser_version,
                body.platform,
                body.screen_res,
                caps_str,
                body.permission_status,
                client_ip,
                now_str,
                now_str,
                body.client_device_token,
                confidence,
                limitations,
            ),
        )

        device_profile = {
            "device_id": device_id,
            "driver_id": body.driver_id,
            "driver_name": drv["name"],
            "nickname": body.nickname,
            "device_category": body.device_category,
            "model": body.model,
            "os_family": body.os_family,
            "os_version": body.os_version,
            "browser_family": body.browser_family,
            "browser_version": body.browser_version,
            "platform": body.platform,
            "screen_res": body.screen_res,
            "client_device_token": body.client_device_token,
            "identity_confidence": confidence,
            "detection_limitations": limitations,
            "capabilities": body.capabilities or {},
            "permission_status": body.permission_status,
            "last_ip": client_ip,
            "registered_at": now_str,
            "last_seen_at": now_str,
            "is_revoked": False,
        }
        write_audit(conn, actor=actor, action="register_device", entity="device", entity_id=device_id, after=device_profile)

    broadcast_event("device_registered", device_profile)
    return device_profile


@app.get("/devices")
def list_devices(
    driver_id: str | None = Query(None),
    is_revoked: bool | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    with read_conn() as conn:
        conditions = []
        params: list[Any] = []
        if driver_id:
            conditions.append("d.driver_id = ?")
            params.append(driver_id)
        if is_revoked is not None:
            conditions.append("d.is_revoked = ?")
            params.append(1 if is_revoked else 0)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"""
            SELECT d.*, dr.name as driver_name, dr.phone as driver_phone
            FROM devices d
            JOIN drivers dr ON dr.driver_id = d.driver_id
            {where_clause}
            ORDER BY d.last_seen_at DESC
            LIMIT ?
        """
        params.append(limit)
        rows = conn.execute(query, tuple(params)).fetchall()

        devices = []
        for r in rows:
            dev = dict(r)
            dev["is_revoked"] = bool(dev["is_revoked"])
            try:
                dev["capabilities"] = json.loads(dev.get("capabilities_json") or "{}")
            except Exception:
                dev["capabilities"] = {}
            devices.append(dev)
        return devices


@app.get("/devices/{device_id}")
def get_device_details(device_id: str):
    with read_conn() as conn:
        row = conn.execute(
            """
            SELECT d.*, dr.name as driver_name, dr.phone as driver_phone
            FROM devices d
            JOIN drivers dr ON dr.driver_id = d.driver_id
            WHERE d.device_id = ?
            """,
            (device_id,),
        ).fetchone()
        if not row:
            raise AppError(404, "NOT_FOUND", f"Device '{device_id}' not found.")

        dev = dict(row)
        dev["is_revoked"] = bool(dev["is_revoked"])
        try:
            dev["capabilities"] = json.loads(dev.get("capabilities_json") or "{}")
        except Exception:
            dev["capabilities"] = {}

        sess = conn.execute(
            "SELECT * FROM tracking_sessions WHERE device_id = ? AND status = 'active' ORDER BY started_at DESC LIMIT 1",
            (device_id,),
        ).fetchone()
        dev["active_session"] = dict(sess) if sess else None

        last_fix = conn.execute(
            "SELECT * FROM gps_locations WHERE device_id = ? ORDER BY server_timestamp DESC, rowid DESC LIMIT 1",
            (device_id,),
        ).fetchone()
        dev["latest_location"] = dict(last_fix) if last_fix else None
        return dev


@app.patch("/devices/{device_id}/rename")
def rename_device(device_id: str, body: DeviceRenameRequest, request: Request):
    user = get_current_user(request)
    check_permission(user, "drivers", request=request)
    actor = user["username"] if user else "operator"

    with immediate_transaction() as conn:
        row = conn.execute("SELECT * FROM devices WHERE device_id = ?", (device_id,)).fetchone()
        if not row:
            raise AppError(404, "NOT_FOUND", f"Device '{device_id}' not found.")
        dev = dict(row)
        if dev["is_revoked"]:
            raise AppError(403, "DEVICE_REVOKED", f"Device '{device_id}' is revoked and cannot be renamed.")

        conn.execute("UPDATE devices SET nickname = ? WHERE device_id = ?", (body.nickname, device_id))
        after = {**dev, "nickname": body.nickname}
        write_audit(conn, actor=actor, action="rename_device", entity="device", entity_id=device_id, before=dev, after=after)

    broadcast_event("device_renamed", after)
    return after



@app.post("/devices/{device_id}/revoke")
def revoke_device(device_id: str, request: Request, body: DeviceRevokeRequest | None = None):
    user = get_current_user(request)
    check_permission(user, "drivers", request=request)
    actor = user["username"] if user else "operator"

    with immediate_transaction() as conn:
        row = conn.execute("SELECT * FROM devices WHERE device_id = ?", (device_id,)).fetchone()
        if not row:
            raise AppError(404, "NOT_FOUND", f"Device '{device_id}' not found.")

        dev = dict(row)
        if dev["is_revoked"]:
            return {**dev, "is_revoked": True, "message": "Device is already revoked."}

        now_str = utc_now_iso()
        conn.execute(
            "UPDATE devices SET is_revoked = 1, revoked_at = ? WHERE device_id = ?",
            (now_str, device_id),
        )

        conn.execute(
            "UPDATE tracking_sessions SET status = 'stopped', stopped_at = ? WHERE device_id = ? AND status = 'active'",
            (now_str, device_id),
        )

        revoke_reason = body.reason if body else "Administrative revocation"
        after_dev = {**dev, "is_revoked": True, "revoked_at": now_str, "revoke_reason": revoke_reason}
        write_audit(conn, actor=actor, action="revoke_device", entity="device", entity_id=device_id, before=dev, after=after_dev)

    broadcast_event("device_revoked", after_dev)
    return after_dev


@app.get("/devices/{device_id}/telemetry")
def get_device_telemetry(device_id: str, limit: int = Query(100, ge=1, le=500)):
    with read_conn() as conn:
        row = conn.execute("SELECT * FROM devices WHERE device_id = ?", (device_id,)).fetchone()
        if not row:
            raise AppError(404, "NOT_FOUND", f"Device '{device_id}' not found.")

        fixes = conn.execute(
            """
            SELECT location_id, session_id, latitude, longitude, accuracy, speed, derived_speed, heading,
                   quality_flag, is_implausible_jump, device_timestamp, server_timestamp
            FROM gps_locations
            WHERE device_id = ?
            ORDER BY server_timestamp DESC, rowid DESC
            LIMIT ?
            """,
            (device_id, limit),
        ).fetchall()
        return [dict(f) for f in fixes]


# -------------------------------------------------------------------------
# REAL PHONE GPS TRACKING, VEHICLE & DELIVERY TELEMETRY & STREET VIEW
# -------------------------------------------------------------------------
def make_street_view_url(lat: float | None, lng: float | None) -> str | None:
    if lat is None or lng is None:
        return None
    return f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={lat:.6f},{lng:.6f}"


@app.post("/tracking/sessions/start", status_code=201)
def start_tracking_session(body: TrackingSessionStart, request: Request):
    user = get_current_user(request)
    check_permission(user, "drivers", request=request)
    actor = user["username"] if user else "operator"

    with immediate_transaction() as conn:
        drv_row = conn.execute("SELECT * FROM drivers WHERE driver_id = ?", (body.driver_id,)).fetchone()
        if not drv_row:
            raise AppError(404, "NOT_FOUND", f"Driver '{body.driver_id}' not found.")

        # Check device authorization if device_id provided
        if body.device_id:
            dev_row = conn.execute("SELECT * FROM devices WHERE device_id = ?", (body.device_id,)).fetchone()
            if not dev_row:
                raise AppError(404, "NOT_FOUND", f"Device '{body.device_id}' not found.")
            if dev_row["is_revoked"]:
                raise AppError(403, "DEVICE_REVOKED", f"Device '{body.device_id}' has been revoked.")
            if dev_row["driver_id"] != body.driver_id:
                raise AppError(403, "DEVICE_DRIVER_MISMATCH", f"Device '{body.device_id}' is registered to another driver.")

        # Check if driver is actively assigned to any delivery/vehicle
        asg_row = conn.execute(
            """
            SELECT assignment_id, vehicle_id, delivery_id
            FROM assignments
            WHERE driver_id = ? AND released_at IS NULL
            """,
            (body.driver_id,),
        ).fetchone()

        vehicle_id = asg_row["vehicle_id"] if asg_row else None
        delivery_id = asg_row["delivery_id"] if asg_row else None

        now_str = utc_now_iso()
        # Mark prior active sessions for this driver as stopped
        conn.execute(
            "UPDATE tracking_sessions SET status = 'stopped', stopped_at = ? WHERE driver_id = ? AND status = 'active'",
            (now_str, body.driver_id),
        )

        session_id = f"TRK-{uuid.uuid4().hex[:10].upper()}"
        dev_info = body.device_info or "Mobile Browser Geolocation"
        consent_int = 1 if body.consent_given else 0
        consent_ts = now_str if body.consent_given else None
        conn.execute(
            """
            INSERT INTO tracking_sessions (
                session_id, driver_id, device_id, vehicle_id, delivery_id,
                device_info, started_at, status, consent_given, consent_timestamp
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
            """,
            (session_id, body.driver_id, body.device_id, vehicle_id, delivery_id, dev_info, now_str, consent_int, consent_ts),
        )

        session_data = {
            "session_id": session_id,
            "driver_id": body.driver_id,
            "device_id": body.device_id,
            "driver_name": drv_row["name"],
            "driver_phone": drv_row["phone"],
            "vehicle_id": vehicle_id,
            "delivery_id": delivery_id,
            "device_info": dev_info,
            "started_at": now_str,
            "status": "active",
            "consent_given": bool(body.consent_given),
            "consent_timestamp": consent_ts,
        }
        write_audit(conn, actor=actor, action="start_tracking", entity="tracking_session", entity_id=session_id, after=session_data)

    broadcast_event("tracking_session_started", session_data)
    return session_data


@app.post("/tracking/sessions/{session_id}/consent")
def update_tracking_session_consent(session_id: str, body: TrackingConsentUpdate, request: Request):
    """Explicitly grants or revokes driver location tracking consent."""
    user = get_current_user(request)
    check_permission(user, "drivers", request=request)
    actor = user["username"] if user else "operator"

    with immediate_transaction() as conn:
        row = conn.execute("SELECT * FROM tracking_sessions WHERE session_id = ?", (session_id,)).fetchone()
        if not row:
            raise AppError(404, "NOT_FOUND", f"Tracking session '{session_id}' not found.")
        now_str = utc_now_iso()
        consent_int = 1 if body.consent_given else 0
        consent_ts = now_str if body.consent_given else None
        conn.execute(
            "UPDATE tracking_sessions SET consent_given = ?, consent_timestamp = ? WHERE session_id = ?",
            (consent_int, consent_ts, session_id),
        )
        data = {
            "session_id": session_id,
            "consent_given": body.consent_given,
            "consent_timestamp": consent_ts,
            "message": "Consent recorded successfully." if body.consent_given else "Consent revoked.",
        }
        write_audit(conn, actor=actor, action="update_tracking_consent", entity="tracking_session", entity_id=session_id, after=data)
        return data


@app.post("/tracking/sessions/stop")
def stop_tracking_session(body: TrackingSessionStop, request: Request):
    user = get_current_user(request)
    check_permission(user, "drivers", request=request)
    actor = user["username"] if user else "operator"

    with immediate_transaction() as conn:
        row = conn.execute("SELECT * FROM tracking_sessions WHERE session_id = ?", (body.session_id,)).fetchone()
        if not row:
            raise AppError(404, "NOT_FOUND", f"Tracking session '{body.session_id}' not found.")

        now_str = utc_now_iso()
        conn.execute(
            "UPDATE tracking_sessions SET status = 'stopped', stopped_at = ? WHERE session_id = ?",
            (now_str, body.session_id),
        )
        updated_data = {**dict(row), "status": "stopped", "stopped_at": now_str}
        write_audit(conn, actor=actor, action="stop_tracking", entity="tracking_session", entity_id=body.session_id, after=updated_data)

    broadcast_event("tracking_session_stopped", updated_data)
    return updated_data


@app.post("/tracking/location", status_code=201)
def record_gps_location(body: GPSLocationCreate, request: Request):
    with immediate_transaction() as conn:
        sess_row = conn.execute("SELECT * FROM tracking_sessions WHERE session_id = ?", (body.session_id,)).fetchone()
        if not sess_row:
            raise AppError(404, "NOT_FOUND", f"Tracking session '{body.session_id}' not found.")
        session = dict(sess_row)
        driver_id = session["driver_id"]

        # Prevent spoofing telemetry under another driver's identity
        if body.driver_id and body.driver_id != driver_id:
            raise AppError(403, "DRIVER_MISMATCH", f"Telemetry driver '{body.driver_id}' does not match session driver '{driver_id}'.")

        # Check device authorization & ownership (must precede session status check so revoked devices get 403)
        device_id = body.device_id or session.get("device_id")
        if device_id:
            dev_row = conn.execute("SELECT driver_id, is_revoked FROM devices WHERE device_id = ?", (device_id,)).fetchone()
            if not dev_row:
                raise AppError(404, "NOT_FOUND", f"Device '{device_id}' not found.")
            if dev_row["is_revoked"]:
                raise AppError(403, "DEVICE_REVOKED", "The device associated with this tracking session has been revoked.")
            if dev_row["driver_id"] != driver_id:
                raise AppError(403, "DEVICE_DRIVER_MISMATCH", f"Device '{device_id}' is registered to another driver.")

        if session["status"] != "active":
            raise AppError(400, "SESSION_INACTIVE", f"Tracking session '{body.session_id}' is currently '{session['status']}'.")

        # Driver explicit GPS tracking consent verification
        if not session.get("consent_given"):
            raise AppError(403, "CONSENT_REQUIRED", "Driver GPS consent is required before streaming location coordinates.")

        # Anti-flooding rate limit (minimum 0.8s between fixes per session)
        last_fix = conn.execute(
            """
            SELECT latitude, longitude, speed, server_timestamp, device_timestamp
            FROM gps_locations
            WHERE session_id = ?
            ORDER BY server_timestamp DESC, rowid DESC
            LIMIT 1
            """,
            (body.session_id,),
        ).fetchone()

        now_str = utc_now_iso()
        now_dt = get_current_time()
        ts_validity = evaluate_timestamp_validity(body.device_timestamp, now_str)

        if last_fix:
            try:
                prev_srv_dt = datetime.fromisoformat(last_fix["server_timestamp"].replace("Z", "+00:00"))
                delta_srv_s = (now_dt - prev_srv_dt).total_seconds()
            except Exception:
                delta_srv_s = 999.0

            try:
                prev_dev_ts = datetime.fromisoformat(last_fix["device_timestamp"].replace("Z", "+00:00"))
                curr_dev_ts = datetime.fromisoformat(body.device_timestamp.replace("Z", "+00:00"))
                delta_dev_s = (curr_dev_ts - prev_dev_ts).total_seconds()
            except Exception:
                delta_dev_s = delta_srv_s

            # 1. Duplicate device submission with identical timestamp and coordinates
            if delta_dev_s == 0.0 and abs(body.latitude - last_fix["latitude"]) < 0.00001 and abs(body.longitude - last_fix["longitude"]) < 0.00001:
                raise AppError(409, "DUPLICATE_FIX", "Duplicate GPS fix detected with identical timestamp and coordinates.")

            # 2. Rate limit throttled (minimum 0.8s interval between sequential fixes)
            if abs(delta_dev_s) < 0.8:
                raise AppError(429, "RATE_LIMITED", "GPS update throttled: minimum interval between fixes is 1 second.")

        # Re-verify active vehicle & delivery assignment
        asg_row = conn.execute(
            "SELECT vehicle_id, delivery_id FROM assignments WHERE driver_id = ? AND released_at IS NULL",
            (driver_id,),
        ).fetchone()

        vehicle_id = asg_row["vehicle_id"] if asg_row else session.get("vehicle_id")
        delivery_id = asg_row["delivery_id"] if asg_row else session.get("delivery_id")

        # Evaluate step kinematics, jump detection, and timestamp anomalies
        if last_fix:
            prev_fix = dict(last_fix)
            prev_ts = prev_fix["device_timestamp"] if prev_fix.get("device_timestamp") else prev_fix["server_timestamp"]
            curr_ts = body.device_timestamp if body.device_timestamp else now_str
            kin = evaluate_telemetry_step(
                prev_fix["latitude"],
                prev_fix["longitude"],
                prev_ts,
                body.latitude,
                body.longitude,
                curr_ts,
                body.speed,
                accuracy_m=body.accuracy,
            )
        else:
            quality = "low_accuracy" if body.accuracy > 150.0 else "accepted"
            kin = {
                "distance_m": 0.0,
                "time_delta_s": 0.0,
                "derived_speed_mps": None,
                "derived_speed_kmh": None,
                "is_implausible_jump": 0,
                "quality_flag": quality,
            }

        if ts_validity.get("status") == "clock_skew_high" and kin.get("quality_flag") == "accepted":
            kin["quality_flag"] = "clock_skew"

        client_ip = request.client.host if request.client else "127.0.0.1"
        loc_id = f"LOC-{uuid.uuid4().hex[:10].upper()}"
        speed_source = "reported" if body.speed is not None else ("derived" if kin["derived_speed_mps"] is not None else "none")

        conn.execute(
            """
            INSERT INTO gps_locations (
                location_id, session_id, driver_id, device_id, vehicle_id, delivery_id,
                latitude, longitude, accuracy, altitude, altitude_accuracy, speed, heading,
                derived_speed, speed_source, distance_from_prev_m, time_delta_prev_s,
                is_implausible_jump, quality_flag, client_ip, device_timestamp, server_timestamp, is_valid
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                loc_id,
                body.session_id,
                driver_id,
                device_id,
                vehicle_id,
                delivery_id,
                body.latitude,
                body.longitude,
                body.accuracy,
                body.altitude,
                body.altitude_accuracy,
                body.speed,
                body.heading,
                kin["derived_speed_mps"],
                speed_source,
                kin["distance_m"],
                kin["time_delta_s"],
                kin["is_implausible_jump"],
                kin["quality_flag"],
                client_ip,
                body.device_timestamp,
                now_str,
            ),
        )

        # Update session ping & fix count
        conn.execute(
            "UPDATE tracking_sessions SET last_ping_at = ?, fix_count = fix_count + 1 WHERE session_id = ?",
            (now_str, body.session_id),
        )

        # Update device last seen
        if device_id:
            conn.execute(
                "UPDATE devices SET last_seen_at = ?, last_ip = ? WHERE device_id = ?",
                (now_str, client_ip, device_id),
            )

        record = {
            "location_id": loc_id,
            "session_id": body.session_id,
            "driver_id": driver_id,
            "device_id": device_id,
            "vehicle_id": vehicle_id,
            "delivery_id": delivery_id,
            "latitude": body.latitude,
            "longitude": body.longitude,
            "accuracy": body.accuracy,
            "altitude": body.altitude,
            "altitude_accuracy": body.altitude_accuracy,
            "speed": body.speed,
            "derived_speed_kmh": kin["derived_speed_kmh"],
            "speed_source": speed_source,
            "heading": body.heading,
            "distance_from_prev_m": kin["distance_m"],
            "is_implausible_jump": bool(kin["is_implausible_jump"]),
            "quality_flag": kin["quality_flag"],
            "device_timestamp": body.device_timestamp,
            "server_timestamp": now_str,
            "is_valid": True,
            "street_view_url": make_street_view_url(body.latitude, body.longitude),
        }

    broadcast_event("gps_location_update", record)
    return record


@app.get("/tracking/drivers/{driver_id}/latest")
def get_driver_latest_location(driver_id: str):
    with read_conn() as conn:
        drv = conn.execute("SELECT * FROM drivers WHERE driver_id = ?", (driver_id,)).fetchone()
        if not drv:
            raise AppError(404, "NOT_FOUND", f"Driver '{driver_id}' not found.")

        row = conn.execute(
            """
            SELECT * FROM gps_locations
            WHERE driver_id = ?
            ORDER BY server_timestamp DESC, rowid DESC
            LIMIT 1
            """,
            (driver_id,),
        ).fetchone()

        if not row:
            return {
                "driver_id": driver_id,
                "driver_name": drv["name"],
                "driver_phone": drv["phone"],
                "has_gps": False,
                "status": "no_signal",
                "message": "No GPS telemetry has been received for this driver yet.",
            }

        rec = dict(row)
        freshness = compute_freshness_status(rec["server_timestamp"])
        rec["has_gps"] = True
        rec["is_stale"] = freshness["is_stale"]
        rec["is_live"] = freshness["is_live"]
        rec["is_offline"] = freshness["is_offline"]
        rec["age_seconds"] = freshness["age_seconds"]
        rec["tracking_status"] = freshness["tracking_status"]
        rec["street_view_url"] = make_street_view_url(rec["latitude"], rec["longitude"])
        rec["driver_name"] = drv["name"]
        rec["driver_phone"] = drv["phone"]
        rec["phone_e164"] = drv["phone_e164"]
        rec["phone_verification_status"] = drv["phone_verification_status"]
        return rec


@app.get("/tracking/vehicles/{vehicle_id}/latest")
def get_vehicle_latest_location(vehicle_id: str):
    with read_conn() as conn:
        veh = conn.execute("SELECT * FROM vehicles WHERE vehicle_id = ?", (vehicle_id,)).fetchone()
        if not veh:
            raise AppError(404, "NOT_FOUND", f"Vehicle '{vehicle_id}' not found.")

        asg = conn.execute(
            """
            SELECT a.*, dr.name as driver_name, dr.name, dr.phone as driver_phone, dr.phone
            FROM assignments a
            JOIN drivers dr ON dr.driver_id = a.driver_id
            WHERE a.vehicle_id = ? AND a.released_at IS NULL
            """,
            (vehicle_id,),
        ).fetchone()

        row = conn.execute(
            """
            SELECT * FROM gps_locations
            WHERE vehicle_id = ?
            ORDER BY server_timestamp DESC, rowid DESC
            LIMIT 1
            """,
            (vehicle_id,),
        ).fetchone()

        if not row and asg:
            row = conn.execute(
                """
                SELECT * FROM gps_locations
                WHERE driver_id = ?
                ORDER BY server_timestamp DESC, rowid DESC
                LIMIT 1
                """,
                (asg["driver_id"],),
            ).fetchone()

        if not row:
            return {
                "vehicle_id": vehicle_id,
                "registration_no": veh["registration_no"],
                "vehicle_type": veh["type"],
                "capacity": veh["capacity"],
                "has_gps": False,
                "status": "offline",
                "assigned_driver": dict(asg) if asg else None,
                "message": "No GPS telemetry has been recorded for this vehicle.",
            }

        rec = dict(row)
        freshness = compute_freshness_status(rec["server_timestamp"])
        rec["has_gps"] = True
        rec["is_stale"] = freshness["is_stale"]
        rec["is_live"] = freshness["is_live"]
        rec["is_offline"] = freshness["is_offline"]
        rec["age_seconds"] = freshness["age_seconds"]
        rec["tracking_status"] = freshness["tracking_status"]
        rec["registration_no"] = veh["registration_no"]
        rec["vehicle_type"] = veh["type"]
        rec["capacity"] = veh["capacity"]
        rec["assigned_driver"] = dict(asg) if asg else None

        # Fetch assigned device if driver has one
        if asg:
            dev = conn.execute(
                "SELECT device_id, nickname, os_family, browser_family, platform, last_seen_at, is_revoked FROM devices WHERE driver_id = ? ORDER BY last_seen_at DESC LIMIT 1",
                (asg["driver_id"],),
            ).fetchone()
            rec["assigned_device"] = dict(dev) if dev else None
        else:
            rec["assigned_device"] = None

        rec["street_view_url"] = make_street_view_url(rec["latitude"], rec["longitude"])
        resp = dict(rec)
        resp["latest_location"] = rec
        resp["vehicle"] = dict(veh)
        return resp


@app.get("/tracking/deliveries/{delivery_id}/latest")
def get_delivery_latest_location(delivery_id: str):
    with read_conn() as conn:
        deliv = conn.execute("SELECT * FROM deliveries WHERE delivery_id = ?", (delivery_id,)).fetchone()
        if not deliv:
            raise AppError(404, "NOT_FOUND", f"Delivery '{delivery_id}' does not exist.")

        d_dict = dict(deliv)

        asg = conn.execute(
            """
            SELECT a.*, v.registration_no, v.type as vehicle_type, dr.name as driver_name, dr.name, dr.phone as driver_phone, dr.phone
            FROM assignments a
            JOIN vehicles v ON v.vehicle_id = a.vehicle_id
            JOIN drivers dr ON dr.driver_id = a.driver_id
            WHERE a.delivery_id = ? AND a.released_at IS NULL
            """,
            (delivery_id,),
        ).fetchone()

        row = conn.execute(
            """
            SELECT * FROM gps_locations
            WHERE delivery_id = ?
            ORDER BY server_timestamp DESC, rowid DESC
            LIMIT 1
            """,
            (delivery_id,),
        ).fetchone()

        if not row and asg:
            row = conn.execute(
                """
                SELECT * FROM gps_locations
                WHERE driver_id = ?
                ORDER BY server_timestamp DESC, rowid DESC
                LIMIT 1
                """,
                (asg["driver_id"],),
            ).fetchone()

        resp: dict[str, Any] = {
            "delivery": d_dict,
            "assignment": dict(asg) if asg else None,
            "pickup_street_view": make_street_view_url(d_dict.get("pickup_lat"), d_dict.get("pickup_lng")),
            "dropoff_street_view": make_street_view_url(d_dict.get("drop_lat"), d_dict.get("drop_lng")),
        }

        if not row:
            resp["has_gps"] = False
            resp["tracking_status"] = "offline"
            resp["message"] = "No live GPS coordinates reported for this delivery yet."
            return resp

        rec = dict(row)
        freshness = compute_freshness_status(rec["server_timestamp"])
        rec["has_gps"] = True
        rec["is_stale"] = freshness["is_stale"]
        rec["is_live"] = freshness["is_live"]
        rec["is_offline"] = freshness["is_offline"]
        rec["age_seconds"] = freshness["age_seconds"]
        rec["tracking_status"] = freshness["tracking_status"]
        rec["current_street_view"] = make_street_view_url(rec["latitude"], rec["longitude"])
        resp["latest_location"] = rec
        resp["has_gps"] = True
        resp["tracking_status"] = rec["tracking_status"]
        return resp


@app.get("/tracking/history")
def get_tracking_history(
    session_id: str | None = Query(None),
    driver_id: str | None = Query(None),
    vehicle_id: str | None = Query(None),
    delivery_id: str | None = Query(None),
    since: str | None = Query(None),
    limit: int = Query(200, ge=1, le=1000),
):
    with read_conn() as conn:
        conditions = ["is_valid = 1"]
        params = []
        if session_id:
            conditions.append("session_id = ?")
            params.append(session_id)
        if driver_id:
            conditions.append("driver_id = ?")
            params.append(driver_id)
        if vehicle_id:
            conditions.append("vehicle_id = ?")
            params.append(vehicle_id)
        if delivery_id:
            conditions.append("delivery_id = ?")
            params.append(delivery_id)
        if since:
            conditions.append("server_timestamp >= ?")
            params.append(since)

        where_clause = " AND ".join(conditions)
        query = f"""
            SELECT location_id, session_id, driver_id, vehicle_id, delivery_id,
                   latitude, longitude, accuracy, speed, heading,
                   device_timestamp, server_timestamp
            FROM gps_locations
            WHERE {where_clause}
            ORDER BY server_timestamp ASC
            LIMIT ?
        """
        params_with_limit: list[Any] = list(params) + [limit]
        rows = conn.execute(query, tuple(params_with_limit)).fetchall()
        trail = [dict(r) for r in rows]
        for pt in trail:
            pt["street_view_url"] = make_street_view_url(pt["latitude"], pt["longitude"])
        return {
            "count": len(trail),
            "trail": trail,
        }


@app.get("/tracking/telemetry-graph")
def get_telemetry_graph(
    driver_id: str | None = Query(None),
    vehicle_id: str | None = Query(None),
    delivery_id: str | None = Query(None),
    session_id: str | None = Query(None),
    limit: int = Query(100, ge=5, le=500),
):
    import math

    with read_conn() as conn:
        conditions = ["is_valid = 1"]
        params = []
        if session_id:
            conditions.append("session_id = ?")
            params.append(session_id)
        elif delivery_id:
            conditions.append("delivery_id = ?")
            params.append(delivery_id)
        elif vehicle_id:
            conditions.append("vehicle_id = ?")
            params.append(vehicle_id)
        elif driver_id:
            conditions.append("driver_id = ?")
            params.append(driver_id)

        where_clause = " AND ".join(conditions)
        query = f"""
            SELECT location_id, latitude, longitude, accuracy, speed, heading, server_timestamp
            FROM gps_locations
            WHERE {where_clause}
            ORDER BY server_timestamp ASC
            LIMIT ?
        """
        params_with_limit: list[Any] = list(params) + [limit]
        rows = conn.execute(query, tuple(params_with_limit)).fetchall()

    def haversine(lat1, lon1, lat2, lon2):
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    points = []
    total_dist_km = 0.0
    prev_pt = None

    for r in rows:
        d_km = 0.0
        if prev_pt:
            d_km = haversine(prev_pt["latitude"], prev_pt["longitude"], r["latitude"], r["longitude"])
            total_dist_km += d_km
        prev_pt = r

        raw_speed = r["speed"]
        speed_kmh = round(raw_speed * 3.6, 1) if raw_speed is not None else 0.0

        points.append({
            "timestamp": r["server_timestamp"],
            "speed_kmh": speed_kmh,
            "accuracy_m": round(r["accuracy"], 1),
            "distance_km": round(total_dist_km, 3),
            "latitude": r["latitude"],
            "longitude": r["longitude"],
        })

    return {
        "data_points": points,
        "points": points,
        "total_distance_km": round(total_dist_km, 3),
        "point_count": len(points),
        "points_count": len(points),
        "max_speed_kmh": max([p["speed_kmh"] for p in points], default=0.0),
        "avg_accuracy_m": round(sum([p["accuracy_m"] for p in points]) / len(points), 1) if points else 0.0,
    }
