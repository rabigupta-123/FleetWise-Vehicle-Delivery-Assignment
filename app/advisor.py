from datetime import datetime, timezone
from typing import Any, Optional
import sqlite3

PRIORITY_WEIGHTS = {"urgent": 4, "high": 3, "normal": 2, "low": 1}


def get_recommendations_for_delivery(delivery_id: str, conn: sqlite3.Connection) -> dict[str, Any]:
    del_row = conn.execute("SELECT * FROM deliveries WHERE delivery_id = ?", (delivery_id,)).fetchone()
    if not del_row:
        return {"delivery_id": delivery_id, "recommendations": [], "error": "NOT_FOUND"}
    delivery = dict(del_row)
    req_cap = delivery.get("required_capacity")

    # Fetch eligible vehicles: available and not in active assignment
    veh_rows = conn.execute(
        """
        SELECT v.vehicle_id, v.registration_no, v.type, v.capacity, v.status
        FROM vehicles v
        WHERE v.status = 'available'
          AND NOT EXISTS (
              SELECT 1 FROM assignments a WHERE a.vehicle_id = v.vehicle_id AND a.released_at IS NULL
          )
        """
    ).fetchall()
    vehicles = [dict(r) for r in veh_rows]

    # Filter by capacity if required
    if req_cap is not None:
        eligible_vehicles = [v for v in vehicles if v["capacity"] >= req_cap]
    else:
        eligible_vehicles = vehicles

    # Fetch eligible drivers: available and not in active assignment
    drv_rows = conn.execute(
        """
        SELECT d.driver_id, d.name, d.phone, d.availability_status,
               (SELECT COUNT(*) FROM assignments a WHERE a.driver_id = d.driver_id AND a.released_at IS NOT NULL) AS completed_count
        FROM drivers d
        WHERE d.availability_status = 'available'
          AND NOT EXISTS (
              SELECT 1 FROM assignments a WHERE a.driver_id = d.driver_id AND a.released_at IS NULL
          )
        """
    ).fetchall()
    eligible_drivers = [dict(r) for r in drv_rows]

    recommendations = []
    for v in eligible_vehicles:
        # Vehicle score: best capacity fit (smallest sufficient capacity)
        if req_cap is not None and req_cap > 0:
            excess = v["capacity"] - req_cap
            # Higher score for lower excess capacity
            v_score = max(50.0, 100.0 - (excess / req_cap * 50.0))
            v_reason = f"Optimal capacity fit: {v['capacity']} kg covers required {req_cap} kg with {excess} kg buffer."
        else:
            v_score = 85.0
            v_reason = f"Available vehicle ({v['capacity']} kg capacity)."

        for dr in eligible_drivers:
            # Driver score: fairness (fewer completed deliveries = higher score)
            c_count = dr.get("completed_count", 0)
            dr_score = max(40.0, 100.0 - (c_count * 15.0))
            dr_reason = f"Fair workload: driver has completed {c_count} deliveries."

            total_score = round(0.5 * v_score + 0.5 * dr_score, 1)
            reason = f"{v_reason} {dr_reason}"

            recommendations.append({
                "vehicle": v,
                "driver": dr,
                "vehicle_score": round(v_score, 1),
                "driver_score": round(dr_score, 1),
                "total_score": total_score,
                "reason": reason,
            })

    # Sort descending by total_score, then ascending by vehicle capacity
    recommendations.sort(key=lambda x: (-x["total_score"], x["vehicle"]["capacity"]))

    return {
        "delivery_id": delivery_id,
        "required_capacity": req_cap,
        "eligible_vehicle_count": len(eligible_vehicles),
        "eligible_driver_count": len(eligible_drivers),
        "recommendations": recommendations[:5],  # top 5 ranked
    }


def get_dispatch_next_delivery(conn: sqlite3.Connection) -> Optional[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT * FROM deliveries
        WHERE status = 'pending'
          AND NOT EXISTS (SELECT 1 FROM assignments a WHERE a.delivery_id = deliveries.delivery_id AND a.released_at IS NULL)
        """
    ).fetchall()
    if not rows:
        return None

    items = [dict(r) for r in rows]
    # Sort: priority weight desc, then scheduled_time asc
    items.sort(key=lambda d: (-PRIORITY_WEIGHTS.get(d.get("priority", "normal"), 2), d.get("scheduled_time", "")))
    top_del = items[0]
    rec_info = get_recommendations_for_delivery(top_del["delivery_id"], conn)
    top_del["recommendations"] = rec_info.get("recommendations", [])
    return top_del

