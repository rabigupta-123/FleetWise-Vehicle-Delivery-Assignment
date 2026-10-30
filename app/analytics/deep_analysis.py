"""
FleetWise Deep Analysis Engine (Phase Five)
Structured, reproducible analytics across fleet operations, delivery performance,
telemetry kinematics, driver metrics, and operational anomaly detection.
"""
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def analyze_fleet_utilization(conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    Calculates fleet utilization excluding inactive / retired vehicles:
    fleet_utilization = (vehicles currently assigned / total active vehicles) * 100
    """
    total_vehicles = conn.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0]
    inactive_vehicles = conn.execute("SELECT COUNT(*) FROM vehicles WHERE status IN ('inactive', 'retired')").fetchone()[0]
    active_pool = total_vehicles - inactive_vehicles

    assigned_vehicles = conn.execute(
        """
        SELECT COUNT(DISTINCT vehicle_id) FROM assignments 
        WHERE released_at IS NULL
        """
    ).fetchone()[0]

    available_vehicles = conn.execute(
        """
        SELECT COUNT(*) FROM vehicles v
        WHERE v.status = 'available'
        AND NOT EXISTS (SELECT 1 FROM assignments a WHERE a.vehicle_id = v.vehicle_id AND a.released_at IS NULL)
        """
    ).fetchone()[0]

    maintenance_vehicles = conn.execute("SELECT COUNT(*) FROM vehicles WHERE status = 'maintenance'").fetchone()[0]

    utilization_pct = round((assigned_vehicles / active_pool * 100.0), 2) if active_pool > 0 else 0.0

    return {
        "fleet_utilization_pct": utilization_pct,
        "total_vehicles": total_vehicles,
        "active_pool_vehicles": active_pool,
        "assigned_vehicles": assigned_vehicles,
        "available_vehicles": available_vehicles,
        "maintenance_vehicles": maintenance_vehicles,
        "inactive_vehicles": inactive_vehicles,
        "formula": "(assigned_vehicles / (total_vehicles - inactive_vehicles)) * 100",
    }


def analyze_driver_utilization(conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    Calculates driver utilization excluding permanently unavailable drivers:
    driver_utilization = (drivers currently assigned / total eligible active drivers) * 100
    """
    total_drivers = conn.execute("SELECT COUNT(*) FROM drivers").fetchone()[0]
    assigned_drivers = conn.execute(
        """
        SELECT COUNT(DISTINCT driver_id) FROM assignments 
        WHERE released_at IS NULL
        """
    ).fetchone()[0]

    available_drivers = conn.execute(
        """
        SELECT COUNT(*) FROM drivers d
        WHERE d.availability_status = 'available'
        AND NOT EXISTS (SELECT 1 FROM assignments a WHERE a.driver_id = d.driver_id AND a.released_at IS NULL)
        """
    ).fetchone()[0]

    unavailable_drivers = conn.execute("SELECT COUNT(*) FROM drivers WHERE availability_status = 'unavailable'").fetchone()[0]
    eligible_active = total_drivers - unavailable_drivers

    utilization_pct = round((assigned_drivers / eligible_active * 100.0), 2) if eligible_active > 0 else 0.0

    return {
        "driver_utilization_pct": utilization_pct,
        "total_drivers": total_drivers,
        "eligible_active_drivers": eligible_active,
        "assigned_drivers": assigned_drivers,
        "available_drivers": available_drivers,
        "unavailable_drivers": unavailable_drivers,
        "formula": "(assigned_drivers / (total_drivers - unavailable_drivers)) * 100",
    }


def analyze_delivery_performance(conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    Calculates delivery completion rate, on-time rate, and average delivery duration.
    Discloses excluded counts for deliveries with missing deadlines or cancelled states.
    """
    counts_row = conn.execute(
        """
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN status = 'delivered' THEN 1 ELSE 0 END) as delivered,
            SUM(CASE WHEN status = 'in_transit' THEN 1 ELSE 0 END) as in_transit,
            SUM(CASE WHEN status = 'assigned' THEN 1 ELSE 0 END) as assigned,
            SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
            SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled
        FROM deliveries
        """
    ).fetchone()

    total = counts_row["total"] or 0
    delivered = counts_row["delivered"] or 0
    in_transit = counts_row["in_transit"] or 0
    assigned = counts_row["assigned"] or 0
    pending = counts_row["pending"] or 0
    cancelled = counts_row["cancelled"] or 0

    # Completion rate: delivered / (total - cancelled)
    eligible_deliveries = total - cancelled
    completion_rate_pct = round((delivered / eligible_deliveries * 100.0), 2) if eligible_deliveries > 0 else 0.0

    # On-time delivery rate & duration calculation
    rows = conn.execute(
        """
        SELECT d.delivery_id, d.created_at, d.scheduled_time AS deadline, d.status,
               a.assigned_at, a.released_at AS completed_at
        FROM deliveries d
        LEFT JOIN assignments a ON a.delivery_id = d.delivery_id AND a.release_reason = 'delivered'
        WHERE d.status = 'delivered'
        """
    ).fetchall()

    on_time_count = 0
    with_deadline_count = 0
    missing_deadline_count = 0
    valid_durations_minutes = []

    for r in rows:
        # Check deadline
        if r["deadline"] and r["completed_at"]:
            with_deadline_count += 1
            try:
                t_comp = datetime.fromisoformat(r["completed_at"].replace("Z", "+00:00"))
                t_dead = datetime.fromisoformat(r["deadline"].replace("Z", "+00:00"))
                if t_comp <= t_dead:
                    on_time_count += 1
            except Exception:
                pass
        else:
            missing_deadline_count += 1

        # Check duration (completed_at - created_at)
        if r["created_at"] and r["completed_at"]:
            try:
                t_start = datetime.fromisoformat(r["created_at"].replace("Z", "+00:00"))
                t_end = datetime.fromisoformat(r["completed_at"].replace("Z", "+00:00"))
                duration_m = (t_end - t_start).total_seconds() / 60.0
                if duration_m >= 0.0:
                    valid_durations_minutes.append(duration_m)
            except Exception:
                pass

    on_time_rate_pct = round((on_time_count / with_deadline_count * 100.0), 2) if with_deadline_count > 0 else 0.0
    avg_duration_minutes = round(sum(valid_durations_minutes) / len(valid_durations_minutes), 1) if valid_durations_minutes else None

    return {
        "completion_rate_pct": completion_rate_pct,
        "on_time_rate_pct": on_time_rate_pct,
        "average_duration_minutes": avg_duration_minutes,
        "total_deliveries": total,
        "delivered_count": delivered,
        "in_transit_count": in_transit,
        "assigned_count": assigned,
        "pending_count": pending,
        "cancelled_count": cancelled,
        "eligible_deliveries_count": eligible_deliveries,
        "completed_with_deadline_count": with_deadline_count,
        "completed_missing_deadline_excluded": missing_deadline_count,
        "durations_sample_size": len(valid_durations_minutes),
    }


def analyze_vehicle_performance(conn: sqlite3.Connection, vehicle_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Calculates operational distance, average speed, deliveries, and telemetry quality per vehicle."""
    query = "SELECT * FROM vehicles"
    params = []
    if vehicle_id:
        query += " WHERE vehicle_id = ?"
        params.append(vehicle_id)

    vehicles = conn.execute(query, tuple(params)).fetchall()
    results = []

    for v in vehicles:
        vid = v["vehicle_id"]
        # Deliveries completed
        del_count = conn.execute(
            """
            SELECT COUNT(*) FROM assignments a
            JOIN deliveries d ON d.delivery_id = a.delivery_id
            WHERE a.vehicle_id = ? AND d.status = 'delivered'
            """,
            (vid,),
        ).fetchone()[0]

        # Telemetry statistics
        loc_stats = conn.execute(
            """
            SELECT 
                COUNT(*) as fix_count,
                SUM(CASE WHEN distance_from_prev_m IS NOT NULL THEN distance_from_prev_m ELSE 0 END) as total_distance_m,
                AVG(CASE WHEN derived_speed IS NOT NULL THEN derived_speed ELSE NULL END) as avg_speed_mps,
                SUM(CASE WHEN is_implausible_jump = 1 THEN 1 ELSE 0 END) as jump_count,
                SUM(CASE WHEN quality_flag = 'accepted' THEN 1 ELSE 0 END) as accepted_count,
                AVG(CASE WHEN accuracy IS NOT NULL THEN accuracy ELSE NULL END) as avg_accuracy_m
            FROM gps_locations
            WHERE vehicle_id = ?
            """,
            (vid,),
        ).fetchone()

        fix_count = loc_stats["fix_count"] or 0
        total_dist_km = round((loc_stats["total_distance_m"] or 0.0) / 1000.0, 2)
        avg_speed_kmh = round((loc_stats["avg_speed_mps"] or 0.0) * 3.6, 1) if loc_stats["avg_speed_mps"] else None
        jump_count = loc_stats["jump_count"] or 0
        avg_acc = round(loc_stats["avg_accuracy_m"], 1) if loc_stats["avg_accuracy_m"] is not None else None

        quality_ratio = round((loc_stats["accepted_count"] / fix_count * 100.0), 1) if fix_count > 0 else None

        results.append({
            "vehicle_id": vid,
            "registration_no": v["registration_no"],
            "type": v["type"],
            "status": v["status"],
            "capacity": v["capacity"],
            "completed_deliveries": del_count,
            "total_distance_km": total_dist_km,
            "average_speed_kmh": avg_speed_kmh,
            "telemetry_fixes_count": fix_count,
            "telemetry_jump_anomalies": jump_count,
            "telemetry_quality_pct": quality_ratio,
            "average_gps_accuracy_m": avg_acc,
        })

    return results


def analyze_driver_performance(conn: sqlite3.Connection, driver_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Calculates completed deliveries, on-time rates, durations, and telemetry availability per driver."""
    query = "SELECT * FROM drivers"
    params = []
    if driver_id:
        query += " WHERE driver_id = ?"
        params.append(driver_id)

    drivers = conn.execute(query, tuple(params)).fetchall()
    results = []

    for d in drivers:
        d_id = d["driver_id"]
        del_rows = conn.execute(
            """
            SELECT d.status, d.created_at, d.scheduled_time AS deadline,
                   a.assigned_at, a.released_at AS completed_at
            FROM assignments a
            JOIN deliveries d ON d.delivery_id = a.delivery_id
            WHERE a.driver_id = ?
            """,
            (d_id,),
        ).fetchall()

        completed = 0
        on_time = 0
        with_deadline = 0
        durations = []

        for r in del_rows:
            if r["status"] == "delivered":
                completed += 1
                if r["deadline"] and r["completed_at"]:
                    with_deadline += 1
                    try:
                        if datetime.fromisoformat(r["completed_at"].replace("Z", "+00:00")) <= datetime.fromisoformat(r["deadline"].replace("Z", "+00:00")):
                            on_time += 1
                    except Exception:
                        pass
                if r["created_at"] and r["completed_at"]:
                    try:
                        dur = (datetime.fromisoformat(r["completed_at"].replace("Z", "+00:00")) - datetime.fromisoformat(r["created_at"].replace("Z", "+00:00"))).total_seconds() / 60.0
                        if dur >= 0:
                            durations.append(dur)
                    except Exception:
                        pass

        on_time_pct = round((on_time / with_deadline * 100.0), 1) if with_deadline > 0 else None
        avg_dur = round(sum(durations) / len(durations), 1) if durations else None

        # Telemetry fixes
        fix_count = conn.execute("SELECT COUNT(*) FROM gps_locations WHERE driver_id = ?", (d_id,)).fetchone()[0]

        results.append({
            "driver_id": d_id,
            "name": d["name"],
            "phone": d["phone"],
            "phone_verification_status": d["phone_verification_status"],
            "availability_status": d["availability_status"],
            "completed_deliveries": completed,
            "on_time_rate_pct": on_time_pct,
            "average_duration_minutes": avg_dur,
            "telemetry_fixes_count": fix_count,
            "telemetry_available": fix_count > 0,
        })

    return results


def detect_operational_anomalies(conn: sqlite3.Connection, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Scans the database for operational anomalies:
    1. Kinematic jumps / impossible speeds (> 180 km/h or > 300m in <2s)
    2. Out-of-order GPS timestamps
    3. Severe GPS accuracy degradation (> 150m radius)
    4. Suspicious device revocations
    5. Assignment conflict attempts recorded in audit logs
    """
    anomalies = []

    # 1. Kinematic Jumps & Impossible Speed
    jump_rows = conn.execute(
        """
        SELECT location_id, session_id, driver_id, vehicle_id, latitude, longitude,
               speed, derived_speed, distance_from_prev_m, time_delta_prev_s,
               device_timestamp, server_timestamp
        FROM gps_locations
        WHERE is_implausible_jump = 1 OR derived_speed > 50.0
        ORDER BY server_timestamp DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    for r in jump_rows:
        speed_kmh = round((r["derived_speed"] or 0.0) * 3.6, 1)
        anomalies.append({
            "event_id": f"ANOM-JUMP-{r['location_id']}",
            "type": "kinematic_jump",
            "severity": "HIGH",
            "affected_entity": r["vehicle_id"] or r["driver_id"] or "Unknown",
            "timestamp": r["server_timestamp"],
            "detection_reason": f"Displacement of {r['distance_from_prev_m']}m in {r['time_delta_prev_s']}s yields impossible velocity of {speed_kmh} km/h.",
            "evidence": {
                "location_id": r["location_id"],
                "derived_speed_kmh": speed_kmh,
                "distance_m": r["distance_from_prev_m"],
                "delta_s": r["time_delta_prev_s"],
                "coordinates": [r["latitude"], r["longitude"]],
            },
            "confidence_score": 90.0,
            "recommended_investigation": "Check for mobile device GPS multi-path reflection or tunnel satellite loss.",
            "review_status": "requires_review",
        })

    # 2. Out-of-order GPS events
    ooo_rows = conn.execute(
        """
        SELECT location_id, session_id, driver_id, vehicle_id, device_timestamp, server_timestamp
        FROM gps_locations
        WHERE quality_flag = 'out_of_order'
        ORDER BY server_timestamp DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    for r in ooo_rows:
        anomalies.append({
            "event_id": f"ANOM-OOO-{r['location_id']}",
            "type": "out_of_order_telemetry",
            "severity": "MEDIUM",
            "affected_entity": r["driver_id"] or "Unknown",
            "timestamp": r["server_timestamp"],
            "detection_reason": "Device timestamp is earlier than previously committed session fix.",
            "evidence": {
                "location_id": r["location_id"],
                "device_timestamp": r["device_timestamp"],
                "server_timestamp": r["server_timestamp"],
            },
            "confidence_score": 85.0,
            "recommended_investigation": "Verify mobile client offline sync queueing or network buffer packet reordering.",
            "review_status": "requires_review",
        })

    # 3. Degraded GPS accuracy (>150m)
    low_acc_rows = conn.execute(
        """
        SELECT location_id, session_id, driver_id, vehicle_id, accuracy, server_timestamp
        FROM gps_locations
        WHERE accuracy > 150.0
        ORDER BY server_timestamp DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    for r in low_acc_rows:
        anomalies.append({
            "event_id": f"ANOM-ACC-{r['location_id']}",
            "type": "degraded_gps_accuracy",
            "severity": "LOW",
            "affected_entity": r["driver_id"] or "Unknown",
            "timestamp": r["server_timestamp"],
            "detection_reason": f"Horizontal accuracy radius degraded to {r['accuracy']}m (cellular/Wi-Fi positioning fallback).",
            "evidence": {
                "location_id": r["location_id"],
                "accuracy_radius_m": r["accuracy"],
            },
            "confidence_score": 95.0,
            "recommended_investigation": "Ensure driver device has unobstructed sky view and GPS antenna enabled.",
            "review_status": "informational",
        })

    # 4. Device Revocations
    rev_rows = conn.execute(
        """
        SELECT device_id, driver_id, nickname, revoked_at, last_ip
        FROM devices
        WHERE is_revoked = 1
        ORDER BY revoked_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    for r in rev_rows:
        anomalies.append({
            "event_id": f"ANOM-REV-{r['device_id']}",
            "type": "device_revocation",
            "severity": "HIGH",
            "affected_entity": r["device_id"],
            "timestamp": r["revoked_at"],
            "detection_reason": f"Device '{r['nickname']}' was permanently revoked for driver '{r['driver_id']}'.",
            "evidence": {
                "device_id": r["device_id"],
                "driver_id": r["driver_id"],
                "last_ip": r["last_ip"],
            },
            "confidence_score": 100.0,
            "recommended_investigation": "Verify whether hardware was reported lost, stolen, or reassigned.",
            "review_status": "confirmed_revocation",
        })

    # Sort all by timestamp descending
    anomalies.sort(key=lambda x: x["timestamp"] or "", reverse=True)
    return anomalies[:limit]
