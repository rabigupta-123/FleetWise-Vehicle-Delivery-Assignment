import csv
import io
import json
import re
import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Any

from app.db import utc_now_iso
from app.errors import AppError

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
MAX_ROWS = 5000

VALID_VEHICLE_STATUSES = {"available", "maintenance", "inactive"}
VALID_DRIVER_STATUSES = {"available", "unavailable"}
VALID_PRIORITIES = {"low", "normal", "high", "urgent"}

PHONE_REGEX = re.compile(r"^\+?[0-9\-\s\(\)]{7,30}$")

TEMPLATES = {
    "vehicles": "vehicle_id,registration_no,type,capacity,status\n",
    "drivers": "driver_id,name,phone,availability_status\n",
    "deliveries": "delivery_id,pickup,dropoff,scheduled_time,priority,required_capacity,pickup_lat,pickup_lng,drop_lat,drop_lng\n",
}


def sanitize_csv_cell(value: Any) -> str:
    """Prefix cells starting with =, +, -, @, \\t, or \\r with a single quote to prevent CSV formula injection."""
    if value is None:
        return ""
    s = str(value)
    if s and s[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + s
    return s


def parse_upload_content(filename: str, content_bytes: bytes) -> list[dict[str, Any]]:
    # Size check
    if len(content_bytes) > MAX_FILE_SIZE:
        raise AppError(400, "FILE_TOO_LARGE", f"File size ({len(content_bytes)} bytes) exceeds maximum limit of 5 MB.")

    fn_lower = (filename or "").lower()
    if not (fn_lower.endswith(".csv") or fn_lower.endswith(".json")):
        raise AppError(400, "VALIDATION_ERROR", "Invalid file extension. Only .csv and .json files are accepted.")

    # Content sniffing: reject binary files (presence of null bytes)
    if b"\x00" in content_bytes[:4096]:
        raise AppError(400, "VALIDATION_ERROR", "File content is not valid text (binary detected).")

    # Decode UTF-8 with BOM handling
    try:
        text = content_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise AppError(400, "VALIDATION_ERROR", "File encoding must be UTF-8 or UTF-8 with BOM.") from None

    text = text.strip()
    if not text:
        return []

    is_json = fn_lower.endswith(".json") or text.startswith("[") or text.startswith("{")

    if is_json:
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                data = [data]
            if not isinstance(data, list):
                raise ValueError("JSON content must be an array of objects.")
            if len(data) > MAX_ROWS:
                raise AppError(400, "ROW_LIMIT_EXCEEDED", f"Upload contains {len(data)} rows; maximum allowed is {MAX_ROWS}.")
            return data
        except AppError:
            raise
        except Exception as e:
            raise AppError(400, "VALIDATION_ERROR", f"Invalid JSON format: {str(e)}") from e
    else:
        # CSV parsing with CRLF and quoted-comma handling
        try:
            reader = csv.DictReader(io.StringIO(text))
            rows = []
            for r in reader:
                clean_row = {}
                for k, v in r.items():
                    if k is not None:
                        clean_row[k.strip()] = v.strip() if isinstance(v, str) else v
                rows.append(clean_row)
                if len(rows) > MAX_ROWS:
                    raise AppError(400, "ROW_LIMIT_EXCEEDED", f"Upload contains more than {MAX_ROWS} rows; maximum allowed is {MAX_ROWS}.")
            return rows
        except AppError:
            raise
        except Exception as e:
            raise AppError(400, "VALIDATION_ERROR", f"Invalid CSV format: {str(e)}") from e


def validate_iso8601(val: str) -> bool:
    if not val or not isinstance(val, str):
        return False
    clean = val.strip()
    try:
        norm = clean[:-1] + "+00:00" if clean.endswith("Z") else clean
        datetime.fromisoformat(norm)
        return True
    except Exception:
        return False


def validate_vehicles_rows(rows: list[dict[str, Any]], conn: sqlite3.Connection) -> tuple[list[dict], list[dict]]:
    validated_rows = []
    all_errors = []

    seen_ids = set()
    seen_regs = set()

    existing_ids = {r[0] for r in conn.execute("SELECT vehicle_id FROM vehicles").fetchall()}
    existing_regs = {r[0].upper() for r in conn.execute("SELECT registration_no FROM vehicles").fetchall()}

    max_id_num = 0
    for vid in existing_ids:
        m = re.match(r"^V-(\d+)$", vid, re.IGNORECASE)
        if m:
            max_id_num = max(max_id_num, int(m.group(1)))

    for idx, r in enumerate(rows, start=1):
        row_errors = []
        raw_id = str(r.get("vehicle_id") or "").strip()
        reg_no = str(r.get("registration_no") or "").strip().upper()
        v_type = str(r.get("type") or "").strip()
        raw_cap = r.get("capacity")
        raw_status = str(r.get("status") or "available").strip().lower()

        # Registration validation
        if not reg_no:
            row_errors.append({"row": idx, "field": "registration_no", "code": "VALIDATION_ERROR", "reason": "registration_no is required"})
        elif len(reg_no) > 50:
            row_errors.append({"row": idx, "field": "registration_no", "code": "VALIDATION_ERROR", "reason": "registration_no exceeds max length of 50"})
        elif reg_no in existing_regs:
            row_errors.append({"row": idx, "field": "registration_no", "code": "DUPLICATE", "reason": f"Registration '{reg_no}' already exists in database"})
        elif reg_no in seen_regs:
            row_errors.append({"row": idx, "field": "registration_no", "code": "DUPLICATE", "reason": f"Duplicate registration '{reg_no}' within file"})
        else:
            seen_regs.add(reg_no)

        # Type validation
        if not v_type:
            row_errors.append({"row": idx, "field": "type", "code": "VALIDATION_ERROR", "reason": "type is required"})
        elif len(v_type) > 50:
            row_errors.append({"row": idx, "field": "type", "code": "VALIDATION_ERROR", "reason": "type exceeds max length of 50"})

        # Capacity validation (must be positive integer)
        cap = 0
        try:
            if raw_cap is None or str(raw_cap).strip() == "":
                row_errors.append({"row": idx, "field": "capacity", "code": "VALIDATION_ERROR", "reason": "capacity is required"})
            else:
                f_val = float(raw_cap)
                if not f_val.is_integer() or int(f_val) <= 0:
                    row_errors.append({"row": idx, "field": "capacity", "code": "VALIDATION_ERROR", "reason": "capacity must be a positive integer"})
                else:
                    cap = int(f_val)
        except Exception:
            row_errors.append({"row": idx, "field": "capacity", "code": "VALIDATION_ERROR", "reason": "capacity must be a valid positive integer"})

        # Status validation (state-bypass guard)
        if raw_status in ("assigned", "in_transit"):
            row_errors.append({
                "row": idx,
                "field": "status",
                "code": "INVALID_TRANSITION",
                "reason": f"State bypass forbidden: vehicles cannot be imported with status '{raw_status}'. Allowed: {', '.join(sorted(VALID_VEHICLE_STATUSES))}"
            })
        elif raw_status not in VALID_VEHICLE_STATUSES:
            row_errors.append({
                "row": idx,
                "field": "status",
                "code": "VALIDATION_ERROR",
                "reason": f"Invalid vehicle status '{raw_status}'. Allowed: {', '.join(sorted(VALID_VEHICLE_STATUSES))}"
            })

        # Vehicle ID validation/generation
        final_id = raw_id
        if raw_id:
            if len(raw_id) > 50:
                row_errors.append({"row": idx, "field": "vehicle_id", "code": "VALIDATION_ERROR", "reason": "vehicle_id exceeds max length of 50"})
            elif raw_id in existing_ids:
                row_errors.append({"row": idx, "field": "vehicle_id", "code": "DUPLICATE", "reason": f"vehicle_id '{raw_id}' already exists in database"})
            elif raw_id in seen_ids:
                row_errors.append({"row": idx, "field": "vehicle_id", "code": "DUPLICATE", "reason": f"Duplicate vehicle_id '{raw_id}' within file"})
            else:
                seen_ids.add(raw_id)
        else:
            max_id_num += 1
            final_id = f"V-{max_id_num:03d}"
            while final_id in existing_ids or final_id in seen_ids:
                max_id_num += 1
                final_id = f"V-{max_id_num:03d}"
            seen_ids.add(final_id)

        all_errors.extend(row_errors)
        validated_rows.append({
            "row": idx,
            "data": {
                "vehicle_id": final_id,
                "registration_no": reg_no,
                "type": v_type,
                "capacity": cap,
                "status": raw_status,
            },
            "errors": row_errors,
        })

    return validated_rows, all_errors


def validate_drivers_rows(rows: list[dict[str, Any]], conn: sqlite3.Connection) -> tuple[list[dict], list[dict]]:
    validated_rows = []
    all_errors = []

    seen_ids = set()
    existing_ids = {r[0] for r in conn.execute("SELECT driver_id FROM drivers").fetchall()}

    max_id_num = 0
    for drid in existing_ids:
        m = re.match(r"^DR-(\d+)$", drid, re.IGNORECASE)
        if m:
            max_id_num = max(max_id_num, int(m.group(1)))

    for idx, r in enumerate(rows, start=1):
        row_errors = []
        raw_id = str(r.get("driver_id") or "").strip()
        name = str(r.get("name") or "").strip()
        phone = str(r.get("phone") or "").strip()
        raw_status = str(r.get("availability_status") or r.get("status") or "available").strip().lower()
        if raw_status == "inactive":
            raw_status = "unavailable"

        if not name:
            row_errors.append({"row": idx, "field": "name", "code": "VALIDATION_ERROR", "reason": "name is required"})
        elif len(name) > 100:
            row_errors.append({"row": idx, "field": "name", "code": "VALIDATION_ERROR", "reason": "name exceeds max length of 100"})

        if not phone:
            row_errors.append({"row": idx, "field": "phone", "code": "VALIDATION_ERROR", "reason": "phone is required"})
        elif not PHONE_REGEX.match(phone):
            row_errors.append({"row": idx, "field": "phone", "code": "VALIDATION_ERROR", "reason": f"Invalid phone format: '{phone}'"})
        elif len(phone) > 30:
            row_errors.append({"row": idx, "field": "phone", "code": "VALIDATION_ERROR", "reason": "phone exceeds max length of 30"})

        # State-bypass check
        if raw_status in ("assigned", "in_transit"):
            row_errors.append({
                "row": idx,
                "field": "availability_status",
                "code": "INVALID_TRANSITION",
                "reason": f"State bypass forbidden: drivers cannot be imported with status '{raw_status}'. Allowed: {', '.join(sorted(VALID_DRIVER_STATUSES))}"
            })
        elif raw_status not in VALID_DRIVER_STATUSES:
            row_errors.append({
                "row": idx,
                "field": "availability_status",
                "code": "VALIDATION_ERROR",
                "reason": f"Invalid driver availability_status '{raw_status}'. Allowed: {', '.join(sorted(VALID_DRIVER_STATUSES))}"
            })

        final_id = raw_id
        if raw_id:
            if len(raw_id) > 50:
                row_errors.append({"row": idx, "field": "driver_id", "code": "VALIDATION_ERROR", "reason": "driver_id exceeds max length of 50"})
            elif raw_id in existing_ids:
                row_errors.append({"row": idx, "field": "driver_id", "code": "DUPLICATE", "reason": f"driver_id '{raw_id}' already exists in database"})
            elif raw_id in seen_ids:
                row_errors.append({"row": idx, "field": "driver_id", "code": "DUPLICATE", "reason": f"Duplicate driver_id '{raw_id}' within file"})
            else:
                seen_ids.add(raw_id)
        else:
            max_id_num += 1
            final_id = f"DR-{max_id_num:03d}"
            while final_id in existing_ids or final_id in seen_ids:
                max_id_num += 1
                final_id = f"DR-{max_id_num:03d}"
            seen_ids.add(final_id)

        all_errors.extend(row_errors)
        validated_rows.append({
            "row": idx,
            "data": {
                "driver_id": final_id,
                "name": name,
                "phone": phone,
                "availability_status": raw_status,
            },
            "errors": row_errors,
        })

    return validated_rows, all_errors


def validate_deliveries_rows(rows: list[dict[str, Any]], conn: sqlite3.Connection) -> tuple[list[dict], list[dict]]:
    validated_rows = []
    all_errors = []

    seen_ids = set()
    existing_ids = {r[0] for r in conn.execute("SELECT delivery_id FROM deliveries").fetchall()}

    max_id_num = 0
    for delid in existing_ids:
        m = re.match(r"^D-(\d+)$", delid, re.IGNORECASE)
        if m:
            max_id_num = max(max_id_num, int(m.group(1)))

    for idx, r in enumerate(rows, start=1):
        row_errors = []
        raw_id = str(r.get("delivery_id") or "").strip()
        pickup = str(r.get("pickup") or r.get("pickup_address") or "").strip()
        dropoff = str(r.get("dropoff") or r.get("delivery_address") or "").strip()
        sched_time = str(r.get("scheduled_time") or "").strip()
        if not sched_time:
            # Automatic graceful fallback to 4 hours ahead in UTC ISO-8601
            sched_time = (datetime.now(UTC) + timedelta(hours=4)).isoformat()
        priority = str(r.get("priority") or "normal").strip().lower()
        if priority == "medium":
            priority = "normal"
        raw_cap = r.get("required_capacity")
        raw_status = str(r.get("status") or "pending").strip().lower()

        # State bypass check: deliveries MUST always enter as pending
        if raw_status != "pending":
            row_errors.append({
                "row": idx,
                "field": "status",
                "code": "INVALID_TRANSITION",
                "reason": f"State bypass forbidden: deliveries must always import with status 'pending', got '{raw_status}'."
            })

        if not pickup:
            row_errors.append({"row": idx, "field": "pickup", "code": "VALIDATION_ERROR", "reason": "pickup location is required"})
        elif len(pickup) > 255:
            row_errors.append({"row": idx, "field": "pickup", "code": "VALIDATION_ERROR", "reason": "pickup exceeds max length of 255"})

        if not dropoff:
            row_errors.append({"row": idx, "field": "dropoff", "code": "VALIDATION_ERROR", "reason": "dropoff location is required"})
        elif len(dropoff) > 255:
            row_errors.append({"row": idx, "field": "dropoff", "code": "VALIDATION_ERROR", "reason": "dropoff exceeds max length of 255"})

        if not sched_time:
            row_errors.append({"row": idx, "field": "scheduled_time", "code": "VALIDATION_ERROR", "reason": "scheduled_time is required"})
        elif not validate_iso8601(sched_time):
            row_errors.append({"row": idx, "field": "scheduled_time", "code": "VALIDATION_ERROR", "reason": f"scheduled_time '{sched_time}' is not valid ISO 8601"})

        if priority not in VALID_PRIORITIES:
            row_errors.append({
                "row": idx,
                "field": "priority",
                "code": "VALIDATION_ERROR",
                "reason": f"Invalid priority '{priority}'. Allowed: {', '.join(sorted(VALID_PRIORITIES))}"
            })

        req_cap = None
        if raw_cap is not None and str(raw_cap).strip() != "":
            try:
                f_cap = float(raw_cap)
                if not f_cap.is_integer() or int(f_cap) <= 0:
                    row_errors.append({"row": idx, "field": "required_capacity", "code": "VALIDATION_ERROR", "reason": "required_capacity must be a positive integer"})
                else:
                    req_cap = int(f_cap)
            except Exception:
                row_errors.append({"row": idx, "field": "required_capacity", "code": "VALIDATION_ERROR", "reason": "required_capacity must be a valid positive integer"})

        # Coordinates parsing
        p_lat = float(r["pickup_lat"]) if r.get("pickup_lat") is not None and str(r.get("pickup_lat")).strip() != "" else None
        p_lng = float(r["pickup_lng"]) if r.get("pickup_lng") is not None and str(r.get("pickup_lng")).strip() != "" else None
        d_lat = float(r["drop_lat"]) if r.get("drop_lat") is not None and str(r.get("drop_lat")).strip() != "" else None
        d_lng = float(r["drop_lng"]) if r.get("drop_lng") is not None and str(r.get("drop_lng")).strip() != "" else None

        final_id = raw_id
        if raw_id:
            if len(raw_id) > 50:
                row_errors.append({"row": idx, "field": "delivery_id", "code": "VALIDATION_ERROR", "reason": "delivery_id exceeds max length of 50"})
            elif raw_id in existing_ids:
                row_errors.append({"row": idx, "field": "delivery_id", "code": "DUPLICATE", "reason": f"delivery_id '{raw_id}' already exists in database"})
            elif raw_id in seen_ids:
                row_errors.append({"row": idx, "field": "delivery_id", "code": "DUPLICATE", "reason": f"Duplicate delivery_id '{raw_id}' within file"})
            else:
                seen_ids.add(raw_id)
        else:
            max_id_num += 1
            final_id = f"D-{max_id_num:03d}"
            while final_id in existing_ids or final_id in seen_ids:
                max_id_num += 1
                final_id = f"D-{max_id_num:03d}"
            seen_ids.add(final_id)

        all_errors.extend(row_errors)
        validated_rows.append({
            "row": idx,
            "data": {
                "delivery_id": final_id,
                "pickup": pickup,
                "dropoff": dropoff,
                "scheduled_time": sched_time,
                "priority": priority,
                "required_capacity": req_cap,
                "status": "pending",
                "created_at": utc_now_iso(),
                "version": 1,
                "pickup_lat": p_lat,
                "pickup_lng": p_lng,
                "drop_lat": d_lat,
                "drop_lng": d_lng,
            },
            "errors": row_errors,
        })

    return validated_rows, all_errors
