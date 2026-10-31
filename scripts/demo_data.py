"""
FleetWise — Demo Data Generator & Autonomous Demo Simulator.
Provides labeled, isolated demo fleets, drivers, and deliveries.
All demo records carry `is_demo = 1` and all simulated telemetry carries `source = 'simulated'`.
Clearing demo data removes ONLY is_demo rows in a single atomic transaction.
"""
import math
import sys
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Ensure root directory is in python path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import DEMO_CENTER_LAT, DEMO_CENTER_LON
from app.db import get_connection, immediate_transaction, write_audit

# Global demo simulator state
_SIMULATOR_THREAD: threading.Thread | None = None
_SIMULATOR_RUNNING = False
_SIMULATOR_LOCK = threading.Lock()


def load_demo_data(center_lat: float = DEMO_CENTER_LAT, center_lon: float = DEMO_CENTER_LON) -> dict:
    """
    Idempotently loads a realistic 12-vehicle, 15-driver, 25-delivery demo dataset.
    All records flagged with is_demo = 1.
    Executes in a single atomic database transaction.
    """
    now = datetime.now(UTC)
    now_iso = now.isoformat()

    # Clear existing demo data first to ensure idempotency
    clear_demo_data()

    # 12 Vehicles across 4 classes
    demo_vehicles = [
        # 3 Bikes
        ("V-DEMO-B01", "KA-01-DM-1001", "bike", 30, "available"),
        ("V-DEMO-B02", "KA-01-DM-1002", "bike", 40, "available"),
        ("V-DEMO-B03", "KA-01-DM-1003", "bike", 50, "maintenance"),
        # 4 Vans
        ("V-DEMO-V01", "KA-02-DM-2001", "van", 900, "available"),
        ("V-DEMO-V02", "KA-02-DM-2002", "van", 1100, "available"),
        ("V-DEMO-V03", "KA-02-DM-2003", "van", 1250, "assigned"),
        ("V-DEMO-V04", "KA-02-DM-2004", "van", 1400, "available"),
        # 3 Mini-trucks
        ("V-DEMO-M01", "KA-03-DM-3001", "mini-truck", 2200, "available"),
        ("V-DEMO-M02", "KA-03-DM-3002", "mini-truck", 2800, "assigned"),
        ("V-DEMO-M03", "KA-03-DM-3003", "mini-truck", 3200, "available"),
        # 2 Heavy Trucks
        ("V-DEMO-T01", "KA-04-DM-4001", "truck", 8500, "available"),
        ("V-DEMO-T02", "KA-04-DM-4002", "truck", 12000, "maintenance"),
    ]

    # 15 Drivers with synthetic names and fake numbers
    demo_drivers = [
        ("DR-DEMO-01", "Alex Mercer [DEMO]", "+91 99999 00001", "available"),
        ("DR-DEMO-02", "Priya Sharma [DEMO]", "+91 99999 00002", "available"),
        ("DR-DEMO-03", "Carlos Mendez [DEMO]", "+91 99999 00003", "available"),
        ("DR-DEMO-04", "Fatima Al-Sayed [DEMO]", "+91 99999 00004", "available"),
        ("DR-DEMO-05", "Rohan Verma [DEMO]", "+91 99999 00005", "assigned"),
        ("DR-DEMO-06", "Li Wei [DEMO]", "+91 99999 00006", "available"),
        ("DR-DEMO-07", "Elena Rostova [DEMO]", "+91 99999 00007", "available"),
        ("DR-DEMO-08", "David Kim [DEMO]", "+91 99999 00008", "assigned"),
        ("DR-DEMO-09", "Aisha Abubakar [DEMO]", "+91 99999 00009", "available"),
        ("DR-DEMO-10", "Marco Rossi [DEMO]", "+91 99999 00010", "unavailable"),
        ("DR-DEMO-11", "Ananya Rao [DEMO]", "+91 99999 00011", "available"),
        ("DR-DEMO-12", "Thomas Becker [DEMO]", "+91 99999 00012", "available"),
        ("DR-DEMO-13", "Siti Nurhaliza [DEMO]", "+91 99999 00013", "available"),
        ("DR-DEMO-14", "Vikram Patel [DEMO]", "+91 99999 00014", "available"),
        ("DR-DEMO-15", "Sarah Connor [DEMO]", "+91 99999 00015", "unavailable"),
    ]

    # 25 Deliveries around center coordinates
    priorities = ["low", "normal", "high", "urgent"]
    capacities = [25, 35, 200, 500, 850, 1100, 2400, 7500]

    with immediate_transaction() as conn:
        # Insert Vehicles
        for vid, reg, vtype, cap, st in demo_vehicles:
            conn.execute(
                """
                INSERT INTO vehicles (vehicle_id, registration_no, type, capacity, status, is_demo)
                VALUES (?, ?, ?, ?, ?, 1)
                """,
                (vid, reg, vtype, cap, st),
            )
            write_audit(conn, actor="demo_loader", action="create_demo", entity="vehicle", entity_id=vid, after={"capacity": cap, "type": vtype})

        # Insert Drivers
        for did, name, phone, st in demo_drivers:
            conn.execute(
                """
                INSERT INTO drivers (driver_id, name, phone, availability_status, is_demo)
                VALUES (?, ?, ?, ?, 1)
                """,
                (did, name, phone, st),
            )
            write_audit(conn, actor="demo_loader", action="create_demo", entity="driver", entity_id=did, after={"name": name})

        # Generate 25 deliveries around center
        created_deliveries = []
        for i in range(1, 26):
            del_id = f"DEL-DEMO-{i:03d}"
            # Scatter coordinates in radius ~ 0.01 - 0.05 deg (~1-5 km)
            angle_p = (i * 2.39996)  # Golden ratio angle
            angle_d = angle_p + 1.2
            r_p = 0.015 + (i % 5) * 0.008
            r_d = 0.025 + (i % 4) * 0.009

            p_lat = round(center_lat + r_p * math.sin(angle_p), 6)
            p_lon = round(center_lon + r_p * math.cos(angle_p), 6)
            d_lat = round(center_lat + r_d * math.sin(angle_d), 6)
            d_lon = round(center_lon + r_d * math.cos(angle_d), 6)

            p_name = f"Demo Hub {chr(65 + (i % 6))}"
            d_name = f"Demo Destination #{i}"
            sched = (now + timedelta(minutes=10 * (i - 12))).strftime("%Y-%m-%dT%H:%M:%SZ")
            prio = priorities[i % len(priorities)]
            req_cap = capacities[i % len(capacities)]

            # Target status: 10 pending, 8 assigned, 4 in_transit, 3 delivered
            status = "pending"
            if i <= 10:
                status = "pending"
            elif i <= 18:
                status = "assigned"
            elif i <= 22:
                status = "in_transit"
            else:
                status = "delivered"

            conn.execute(
                """
                INSERT INTO deliveries (
                    delivery_id, pickup, dropoff, scheduled_time, priority,
                    required_capacity, status, created_at, version, is_demo,
                    pickup_lat, pickup_lng, drop_lat, drop_lng
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 1, ?, ?, ?, ?)
                """,
                (
                    del_id, f"{p_name} ({p_lat},{p_lon})", f"{d_name} ({d_lat},{d_lon})", sched, prio,
                    req_cap, status, now_iso,
                    p_lat, p_lon, d_lat, d_lon,
                ),
            )
            created_deliveries.append((del_id, status, p_lat, p_lon, d_lat, d_lon))

        # Wire assignments and tracking sessions for assigned and en_route deliveries
        # Delivery 11 -> Van 03, Driver 05 (assigned)
        conn.execute(
            """
            INSERT INTO assignments (delivery_id, vehicle_id, driver_id, assigned_at)
            VALUES ('DEL-DEMO-011', 'V-DEMO-V03', 'DR-DEMO-05', ?)
            """,
            (now_iso,),
        )
        # Delivery 19 -> Mini-truck 02, Driver 08 (en_route)
        conn.execute(
            """
            INSERT INTO assignments (delivery_id, vehicle_id, driver_id, assigned_at)
            VALUES ('DEL-DEMO-019', 'V-DEMO-M02', 'DR-DEMO-08', ?)
            """,
            (now_iso,),
        )
        # Create active demo tracking session for DEL-DEMO-019
        sess_id = "TRK-DEMO-SESS-01"
        conn.execute(
            """
            INSERT INTO tracking_sessions (session_id, driver_id, vehicle_id, delivery_id, started_at, status, is_demo)
            VALUES (?, 'DR-DEMO-08', 'V-DEMO-M02', 'DEL-DEMO-019', ?, 'active', 1)
            """,
            (sess_id, now_iso),
        )

        # Pre-seed initial GPS fix for V-DEMO-M02 with source = 'simulated'
        conn.execute(
            """
            INSERT INTO gps_locations (
                session_id, driver_id, vehicle_id, delivery_id, latitude, longitude, accuracy, device_timestamp,
                server_timestamp, speed, heading, source, is_gated
            ) VALUES (?, 'DR-DEMO-08', 'V-DEMO-M02', 'DEL-DEMO-019', ?, ?, 5.0, ?, ?, 8.5, 90.0, 'simulated', 0)
            """,
            (sess_id, center_lat, center_lon, now_iso, now_iso),
        )

    return {
        "status": "loaded",
        "vehicles": len(demo_vehicles),
        "drivers": len(demo_drivers),
        "deliveries": len(created_deliveries),
        "center": {"latitude": center_lat, "longitude": center_lon},
    }


def clear_demo_data() -> dict:
    """
    Halts the demo simulator and atomically removes ONLY rows flagged with is_demo = 1.
    All real production records, devices, and audit history remain strictly intact.
    """
    global _SIMULATOR_RUNNING
    with _SIMULATOR_LOCK:
        _SIMULATOR_RUNNING = False

    with immediate_transaction() as conn:
        # Delete simulated GPS locations
        conn.execute("DELETE FROM gps_locations WHERE source = 'simulated'")

        # Delete demo tracking sessions
        conn.execute("DELETE FROM tracking_sessions WHERE is_demo = 1")

        # Delete demo assignments
        conn.execute(
            "DELETE FROM assignments WHERE delivery_id IN (SELECT delivery_id FROM deliveries WHERE is_demo = 1)"
        )

        # Delete demo deliveries
        del_count = conn.execute("DELETE FROM deliveries WHERE is_demo = 1").rowcount

        # Delete demo drivers
        drv_count = conn.execute("DELETE FROM drivers WHERE is_demo = 1").rowcount

        # Delete demo vehicles
        veh_count = conn.execute("DELETE FROM vehicles WHERE is_demo = 1").rowcount

        # Record demo clearing in append-only audit log
        write_audit(conn, actor="demo_loader", action="clear_demo", entity="demo_system", entity_id="all", after={"vehicles": veh_count, "drivers": drv_count, "deliveries": del_count})

    return {
        "status": "cleared",
        "deleted": {
            "vehicles": veh_count,
            "drivers": drv_count,
            "deliveries": del_count,
        },
    }


def get_demo_status() -> dict:
    """Returns current counts of demo vs real entities."""
    conn = get_connection()
    try:
        demo_v = conn.execute("SELECT COUNT(*) FROM vehicles WHERE is_demo = 1").fetchone()[0]
        real_v = conn.execute("SELECT COUNT(*) FROM vehicles WHERE is_demo = 0").fetchone()[0]
        demo_dr = conn.execute("SELECT COUNT(*) FROM drivers WHERE is_demo = 1").fetchone()[0]
        real_dr = conn.execute("SELECT COUNT(*) FROM drivers WHERE is_demo = 0").fetchone()[0]
        demo_del = conn.execute("SELECT COUNT(*) FROM deliveries WHERE is_demo = 1").fetchone()[0]
        real_del = conn.execute("SELECT COUNT(*) FROM deliveries WHERE is_demo = 0").fetchone()[0]
        sim_gps = conn.execute("SELECT COUNT(*) FROM gps_locations WHERE source = 'simulated'").fetchone()[0]
        real_gps = conn.execute("SELECT COUNT(*) FROM gps_locations WHERE source = 'device'").fetchone()[0]

        return {
            "is_simulator_running": _SIMULATOR_RUNNING,
            "demo": {
                "vehicles": demo_v,
                "drivers": demo_dr,
                "deliveries": demo_del,
                "gps_fixes": sim_gps,
            },
            "real": {
                "vehicles": real_v,
                "drivers": real_dr,
                "deliveries": real_del,
                "gps_fixes": real_gps,
            },
        }
    finally:
        conn.close()


def _simulator_loop():
    """Background simulator advancing demo deliveries along waypoints at 30-40 km/h."""
    global _SIMULATOR_RUNNING
    step = 0
    while True:
        with _SIMULATOR_LOCK:
            if not _SIMULATOR_RUNNING:
                break

        try:
            conn = get_connection()
            try:
                # Find active demo tracking sessions
                sessions = conn.execute(
                    """
                    SELECT s.session_id, s.driver_id, s.vehicle_id, s.delivery_id, d.pickup_lat, d.pickup_lng, d.drop_lat, d.drop_lng
                    FROM tracking_sessions s
                    JOIN deliveries d ON s.delivery_id = d.delivery_id
                    WHERE s.is_demo = 1 AND s.status = 'active'
                    """
                ).fetchall()

                now_iso = datetime.now(UTC).isoformat()
                step += 1
                progress_fraction = (step % 60) / 60.0  # Loops 0.0 -> 1.0 every 60s

                for row in sessions:
                    p_lat = row["pickup_lat"] or DEMO_CENTER_LAT
                    p_lon = row["pickup_lng"] or DEMO_CENTER_LON
                    d_lat = row["drop_lat"] or (DEMO_CENTER_LAT + 0.02)
                    d_lon = row["drop_lng"] or (DEMO_CENTER_LON + 0.02)

                    curr_lat = p_lat + progress_fraction * (d_lat - p_lat)
                    curr_lon = p_lon + progress_fraction * (d_lon - p_lon)
                    speed_mps = 9.7  # ~35 km/h

                    conn.execute(
                        """
                        INSERT INTO gps_locations (
                            session_id, driver_id, vehicle_id, delivery_id, latitude, longitude, accuracy,
                            device_timestamp, server_timestamp, speed, heading, source, is_gated
                        ) VALUES (?, ?, ?, ?, ?, ?, 4.5, ?, ?, ?, 45.0, 'simulated', 0)
                        """,
                        (row["session_id"], row["driver_id"], row["vehicle_id"], row["delivery_id"], curr_lat, curr_lon, now_iso, now_iso, speed_mps),
                    )
            finally:
                conn.close()
        except Exception:
            pass

        time.sleep(1.0)


def toggle_demo_simulator(enable: bool | None = None) -> bool:
    """Starts or pauses the background demo simulator."""
    global _SIMULATOR_RUNNING, _SIMULATOR_THREAD
    with _SIMULATOR_LOCK:
        if enable is None:
            _SIMULATOR_RUNNING = not _SIMULATOR_RUNNING
        else:
            _SIMULATOR_RUNNING = enable

        if _SIMULATOR_RUNNING:
            if _SIMULATOR_THREAD is None or not _SIMULATOR_THREAD.is_alive():
                _SIMULATOR_THREAD = threading.Thread(target=_simulator_loop, daemon=True)
                _SIMULATOR_THREAD.start()
        return _SIMULATOR_RUNNING


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="FleetWise Demo Data Tool")
    parser.add_argument("--load", action="store_true", help="Load demo data")
    parser.add_argument("--clear", action="store_true", help="Clear demo data")
    parser.add_argument("--status", action="store_true", help="Check demo status")
    args = parser.parse_args()

    if args.load:
        res = load_demo_data()
        print("Demo data loaded:", res)
    elif args.clear:
        res = clear_demo_data()
        print("Demo data cleared:", res)
    elif args.status:
        res = get_demo_status()
        print("Demo status:", res)
    else:
        parser.print_help()
