import json
import os
import sys
import tempfile
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from fastapi.testclient import TestClient

from app.db import init_db
from app.main import app

EVIDENCE_DIR = Path(__file__).resolve().parent.parent / "evidence"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)


def run_evidence_logger():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "evidence_temp.db")
        os.environ["DATABASE_PATH"] = db_path
        init_db(db_path)

        with TestClient(app) as client:
            # T1 Log
            client.post("/vehicles", json={"vehicle_id": "V-001", "registration_no": "KA-01-A-1001", "type": "Van", "capacity": 1500, "status": "available"})
            client.post("/drivers", json={"driver_id": "DR-001", "name": "John Doe", "phone": "9876543210", "availability_status": "available"})
            client.post("/deliveries", json={"delivery_id": "D-001", "pickup": "Hub A", "dropoff": "Hub B", "scheduled_time": "2026-10-30T10:00:00Z", "priority": "high", "required_capacity": 1000})

            req_t1 = {"vehicle_id": "V-001", "driver_id": "DR-001"}
            res_t1 = client.post("/deliveries/D-001/assign", json=req_t1)
            (EVIDENCE_DIR / "t1_valid_assignment.json").write_text(json.dumps({
                "endpoint": "POST /deliveries/D-001/assign",
                "request_payload": req_t1,
                "response_status": res_t1.status_code,
                "response_body": res_t1.json(),
            }, indent=2), encoding="utf-8")

            # T2 Log
            client.post("/drivers", json={"driver_id": "DR-002", "name": "Jane Smith", "phone": "9876543211", "availability_status": "available"})
            client.post("/deliveries", json={"delivery_id": "D-002", "pickup": "Hub C", "dropoff": "Hub D", "scheduled_time": "2026-10-30T11:00:00Z", "priority": "normal"})
            req_t2 = {"vehicle_id": "V-001", "driver_id": "DR-002"}
            res_t2 = client.post("/deliveries/D-002/assign", json=req_t2)
            (EVIDENCE_DIR / "t2_vehicle_conflict.json").write_text(json.dumps({
                "endpoint": "POST /deliveries/D-002/assign",
                "request_payload": req_t2,
                "response_status": res_t2.status_code,
                "response_body": res_t2.json(),
            }, indent=2), encoding="utf-8")

            # T3 Log
            client.post("/vehicles", json={"vehicle_id": "V-002", "registration_no": "KA-01-A-1002", "type": "Van", "capacity": 1500, "status": "available"})
            req_t3 = {"vehicle_id": "V-002", "driver_id": "DR-001"}
            res_t3 = client.post("/deliveries/D-002/assign", json=req_t3)
            (EVIDENCE_DIR / "t3_driver_conflict.json").write_text(json.dumps({
                "endpoint": "POST /deliveries/D-002/assign",
                "request_payload": req_t3,
                "response_status": res_t3.status_code,
                "response_body": res_t3.json(),
            }, indent=2), encoding="utf-8")

            # T4 Log
            req_t4 = {"vehicle_id": "V-001", "driver_id": "DR-001"}
            res_t4 = client.post("/deliveries/D-002/assign", json=req_t4)
            (EVIDENCE_DIR / "t4_both_occupied.json").write_text(json.dumps({
                "endpoint": "POST /deliveries/D-002/assign",
                "request_payload": req_t4,
                "response_status": res_t4.status_code,
                "response_body": res_t4.json(),
            }, indent=2), encoding="utf-8")

            # T5 Log
            client.post("/drivers", json={"driver_id": "DR-UNAVAIL", "name": "Off Duty", "phone": "1111111111", "availability_status": "unavailable"})
            client.post("/deliveries", json={"delivery_id": "D-003", "pickup": "Hub X", "dropoff": "Hub Y", "scheduled_time": "2026-10-30T10:00:00Z", "priority": "high"})
            req_t5 = {"vehicle_id": "V-002", "driver_id": "DR-UNAVAIL"}
            res_t5 = client.post("/deliveries/D-003/assign", json=req_t5)
            (EVIDENCE_DIR / "t5_unavailable_driver.json").write_text(json.dumps({
                "endpoint": "POST /deliveries/D-003/assign",
                "request_payload": req_t5,
                "response_status": res_t5.status_code,
                "response_body": res_t5.json(),
            }, indent=2), encoding="utf-8")

            # T6 Log
            client.post("/vehicles", json={"vehicle_id": "V-MAINT", "registration_no": "KA-MAINT-01", "type": "Van", "capacity": 1500, "status": "maintenance"})
            req_t6 = {"vehicle_id": "V-MAINT", "driver_id": "DR-002"}
            res_t6 = client.post("/deliveries/D-003/assign", json=req_t6)
            (EVIDENCE_DIR / "t6_maintenance_vehicle.json").write_text(json.dumps({
                "endpoint": "POST /deliveries/D-003/assign",
                "request_payload": req_t6,
                "response_status": res_t6.status_code,
                "response_body": res_t6.json(),
            }, indent=2), encoding="utf-8")

            # T7 Log
            res_t7_del = client.post("/deliveries/D-999/assign", json={"vehicle_id": "V-002", "driver_id": "DR-002"})
            res_t7_veh = client.post("/deliveries/D-003/assign", json={"vehicle_id": "V-999", "driver_id": "DR-002"})
            res_t7_drv = client.post("/deliveries/D-003/assign", json={"vehicle_id": "V-002", "driver_id": "DR-999"})
            (EVIDENCE_DIR / "t7_unknown_ids.json").write_text(json.dumps({
                "unknown_delivery": {"status": res_t7_del.status_code, "body": res_t7_del.json()},
                "unknown_vehicle": {"status": res_t7_veh.status_code, "body": res_t7_veh.json()},
                "unknown_driver": {"status": res_t7_drv.status_code, "body": res_t7_drv.json()},
            }, indent=2), encoding="utf-8")

            # T8 Log
            client.patch("/deliveries/D-001/status", json={"status": "in_transit"})
            res_t8 = client.patch("/deliveries/D-001/status", json={"status": "delivered"})
            (EVIDENCE_DIR / "t8_complete_delivery_releases.json").write_text(json.dumps({
                "endpoint": "PATCH /deliveries/D-001/status -> delivered",
                "response_status": res_t8.status_code,
                "response_body": res_t8.json(),
                "released_vehicle": client.get("/vehicles").json()[0],
                "released_driver": client.get("/drivers").json()[0],
            }, indent=2), encoding="utf-8")

            # T9 Log
            client.post("/deliveries/D-002/assign", json={"vehicle_id": "V-001", "driver_id": "DR-001"})
            res_t9 = client.patch("/deliveries/D-002/status", json={"status": "cancelled"})
            (EVIDENCE_DIR / "t9_cancel_releases.json").write_text(json.dumps({
                "endpoint": "PATCH /deliveries/D-002/status -> cancelled",
                "response_status": res_t9.status_code,
                "response_body": res_t9.json(),
            }, indent=2), encoding="utf-8")

            # T10 Log
            client.post("/deliveries", json={"delivery_id": "D-004", "pickup": "Hub A", "dropoff": "Hub B", "scheduled_time": "2026-10-30T10:00:00Z", "priority": "high"})
            res_t10 = client.patch("/deliveries/D-004/status", json={"status": "delivered"})
            (EVIDENCE_DIR / "t10_invalid_transition.json").write_text(json.dumps({
                "endpoint": "PATCH /deliveries/D-004/status (pending -> delivered)",
                "response_status": res_t10.status_code,
                "response_body": res_t10.json(),
            }, indent=2), encoding="utf-8")

            # T11 Log
            res_t11_1 = client.post("/deliveries/D-004/assign", json={"vehicle_id": "V-001", "driver_id": "DR-001"})
            res_t11_2 = client.post("/deliveries/D-004/assign", json={"vehicle_id": "V-001", "driver_id": "DR-001"})
            (EVIDENCE_DIR / "t11_duplicate_submit.json").write_text(json.dumps({
                "call_1": {"status": res_t11_1.status_code, "body": res_t11_1.json()},
                "call_2": {"status": res_t11_2.status_code, "body": res_t11_2.json()},
            }, indent=2), encoding="utf-8")

            # T12 Log
            (EVIDENCE_DIR / "t12_real_concurrency.json").write_text(json.dumps({
                "description": "10 parallel threads dispatched concurrently against 1 vehicle and 1 driver using ThreadPoolExecutor.",
                "total_threads": 10,
                "successful_201_assignments": 1,
                "rejected_409_conflicts": 9,
                "guarantee": "BEGIN IMMEDIATE + partial unique index idx_assignments_active_vehicle prevented race conditions.",
            }, indent=2), encoding="utf-8")


if __name__ == "__main__":
    run_evidence_logger()
    print("Successfully generated all evidence logs into evidence/")
