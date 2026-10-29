import os
import sys
import time
import subprocess
import tempfile
from pathlib import Path
import httpx

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from playwright.sync_api import sync_playwright

SCREENSHOT_DIR = BASE_DIR / "evidence" / "screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
SCREENSHOT_V2_DIR = BASE_DIR / "evidence" / "screenshots_v2"
SCREENSHOT_V2_DIR.mkdir(parents=True, exist_ok=True)


def save_screen(page, name: str):
    p1 = SCREENSHOT_DIR / name
    p2 = SCREENSHOT_V2_DIR / name
    page.screenshot(path=str(p1))
    page.screenshot(path=str(p2))
    print(f"Captured {name} -> {p1.name} & {p2.name}")


def run_flow():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_file = os.path.join(tmp_dir, "judge_flow.db")
        env = os.environ.copy()
        env["DATABASE_PATH"] = db_file

        port = 8769
        base_url = f"http://127.0.0.1:{port}"

        proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        try:
            # Wait for server ready
            ready = False
            for _ in range(30):
                try:
                    r = httpx.get(f"{base_url}/health", timeout=1.0)
                    if r.status_code == 200:
                        ready = True
                        break
                except Exception:
                    time.sleep(0.3)

            if not ready:
                raise RuntimeError("Uvicorn server failed to start within timeout.")

            with sync_playwright() as p:
                browser = p.chromium.launch(channel="msedge", headless=True)
                context = browser.new_context(viewport={"width": 1440, "height": 900})
                page = context.new_page()

                # 1. Empty state
                page.goto(base_url)
                page.wait_for_selector("#dashboard-empty-state:not(.hidden)", timeout=5000)
                save_screen(page, "01_empty_state.png")

                # Seed sample data
                with httpx.Client(base_url=base_url) as client:
                    client.post("/vehicles", json={"vehicle_id": "V-001", "registration_no": "KA-01-A-1001", "type": "Van", "capacity": 1500, "status": "available"})
                    client.post("/vehicles", json={"vehicle_id": "V-002", "registration_no": "KA-01-A-1002", "type": "Heavy Truck", "capacity": 5000, "status": "available"})
                    client.post("/drivers", json={"driver_id": "DR-001", "name": "Aarav Sharma", "phone": "9876543210", "availability_status": "available"})
                    client.post("/drivers", json={"driver_id": "DR-002", "name": "Priya Nair", "phone": "9876543211", "availability_status": "available"})
                    client.post("/deliveries", json={"delivery_id": "D-001", "pickup": "Central Hub", "dropoff": "Terminal B", "scheduled_time": "2026-10-30T10:00:00Z", "priority": "urgent", "required_capacity": 1000})
                    client.post("/deliveries", json={"delivery_id": "D-002", "pickup": "Warehouse 4", "dropoff": "Dock 9", "scheduled_time": "2026-10-30T12:00:00Z", "priority": "high", "required_capacity": 800})
                    # Oversized delivery for blocked queue demonstration
                    client.post("/deliveries", json={"delivery_id": "D-OVERSIZED", "pickup": "Cargo Depot", "dropoff": "Port Gate 3", "scheduled_time": "2026-10-30T14:00:00Z", "priority": "urgent", "required_capacity": 15000})

                # 2. View Import page
                page.click("button[data-view='import']")
                page.wait_for_selector("#view-import.active")
                save_screen(page, "02_import_page.png")

                # 3. View Dashboard populated
                page.click("button[data-view='dashboard']")
                page.wait_for_selector("#view-dashboard.active")
                page.click("#btn-refresh-now")
                time.sleep(0.5)
                save_screen(page, "03_dashboard_populated.png")

                # 4. Dispatch Console: Assign D-001 to V-001 & DR-001
                page.click("button[data-view='dispatch']")
                page.wait_for_selector("#view-dispatch.active")
                time.sleep(0.5)
                page.click("button[data-select-dispatch-delivery='D-001']")
                page.click("button[data-select-dispatch-vehicle='V-001']")
                page.click("button[data-select-dispatch-driver='DR-001']")
                page.click("#btn-submit-assign")
                time.sleep(0.8)
                save_screen(page, "04_successful_assignment.png")

                # 5. Attempt to reuse occupied vehicle V-001 on D-002 (Rejected 409)
                page.click("button[data-select-dispatch-delivery='D-002']")
                time.sleep(0.3)
                page.check("#toggle-server-guard-test")
                page.click("button[data-select-dispatch-vehicle='V-001']")
                page.click("button[data-select-dispatch-driver='DR-002']")
                page.click("#btn-submit-assign")
                time.sleep(0.8)
                save_screen(page, "05_reuse_vehicle_rejected.png")

                # 6. Attempt to reuse occupied driver DR-001 on D-002 (Rejected 409)
                page.click("button[data-select-dispatch-vehicle='V-002']")
                page.click("button[data-select-dispatch-driver='DR-001']")
                page.click("#btn-submit-assign")
                time.sleep(0.8)
                save_screen(page, "06_reuse_driver_rejected.png")

                # 7. Complete D-001: Transition assigned -> in_transit -> delivered via Dashboard lane buttons
                page.click("button[data-view='dashboard']")
                page.wait_for_selector("#view-dashboard.active")
                time.sleep(0.5)
                # Click In Transit in assigned lane card
                page.click("#lane-body-assigned button[data-transition-delivery='D-001'][data-target-status='in_transit']")
                time.sleep(0.8)
                # Click Complete Delivery in in_transit lane card
                page.click("#lane-body-in_transit button[data-transition-delivery='D-001'][data-target-status='delivered']")
                time.sleep(0.8)
                save_screen(page, "07_complete_delivery.png")

                # 8. Dispatch Console: Verify resources V-001 & DR-001 are now available again!
                page.click("button[data-view='dispatch']")
                page.wait_for_selector("#view-dispatch.active")
                time.sleep(0.5)
                page.uncheck("#toggle-server-guard-test")
                time.sleep(0.3)
                save_screen(page, "08_resources_available_again.png")

                # 9. Smart Dispatch Advisor & Blocked Queue
                page.click("button[data-select-dispatch-delivery='D-002']")
                time.sleep(0.5)
                # Open Blocked Queue dialog to show capacity diagnosis
                page.click("#btn-view-blocked-queue")
                page.wait_for_selector("#modal-blocked-queue:not(.hidden)")
                time.sleep(0.5)
                save_screen(page, "09_smart_advisor_and_blocked_queue.png")
                page.click("#modal-blocked-queue button[data-close-modal='modal-blocked-queue']")
                time.sleep(0.3)

                # 10. Race Lab Diagnostic Proof
                page.click("button[data-view='racelab']")
                page.wait_for_selector("#view-racelab.active")
                time.sleep(0.3)
                page.click("#btn-launch-racelab")
                page.wait_for_selector("#racelab-results-panel:not(.hidden)", timeout=10000)
                time.sleep(0.8)
                save_screen(page, "10_race_lab_diagnostic_proof.png")

                # 11. Analytics & Route Radar
                page.click("button[data-view='analytics']")
                page.wait_for_selector("#view-analytics.active")
                time.sleep(0.8)
                save_screen(page, "11_analytics_and_routes.png")

                browser.close()
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except Exception:
                proc.kill()


if __name__ == "__main__":
    run_flow()
    print("Browser judge flow finished successfully!")
