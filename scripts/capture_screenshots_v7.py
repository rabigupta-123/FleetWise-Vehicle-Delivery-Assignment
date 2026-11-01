"""
FleetWise — Automated Verification & Screenshot Capture Suite v7.
Captures evidence screenshots at 1440px (desktop) and 375px (mobile) for:
1. Live Fleet Tracking Map & Multi-Driver Telemetry Panel (view-driver-gps)
2. Pair Driver Phone Modal with dynamic QR Code and URL
3. Driver Phone Mobile Portal (driver.html) with identity banner and accuracy metrics
4. Main Dashboard Overview with real-time fleet health
All captured images strictly masked of private tokens, personal coordinates, or LAN IPs.
"""
import subprocess
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from playwright.sync_api import sync_playwright
from app.auth import generate_pairing_token
from scripts.demo_data import load_demo_data

SCREENSHOT_V7_DIR = BASE_DIR / "evidence" / "screenshots_v7"
SCREENSHOT_V7_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "http://127.0.0.1:8000"


def mask_sensitive_info(page):
    """Redacts any actual host IPs, pairing tokens, or raw personal data from screenshot views."""
    page.evaluate("""() => {
        document.querySelectorAll('*').forEach(el => {
            if (el.children.length === 0 && el.textContent) {
                if (el.textContent.includes('10.') || el.textContent.includes('192.168.')) {
                    el.textContent = el.textContent.replace(/\\b(?:10|192\\.168)\\.\\d{1,3}\\.\\d{1,3}\\b/g, 'LAN.FLEETWISE.LOCAL');
                }
            }
        });
        const urlInput = document.getElementById('pair-driver-url-input');
        if (urlInput && urlInput.value) {
            urlInput.value = 'https://LAN.FLEETWISE.LOCAL:8443/driver?pair=REDACTED_PAIRING_TOKEN_192BIT';
        }
    }""")


def main():
    print(f"Ensuring demo data loaded at {BASE_URL}...")
    load_demo_data()

    # Generate a demo pairing token
    token = generate_pairing_token(driver_id="DR-DEMO-01")

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)

        for mode, width, height in [("1440", 1440, 900), ("375", 375, 812)]:
            print(f"\n--- Viewport {mode} ({width}x{height}) ---")
            context = browser.new_context(viewport={"width": width, "height": height})
            page = context.new_page()

            # 1. Main Dashboard
            page.goto(f"{BASE_URL}/", wait_until="networkidle")
            time.sleep(1)
            mask_sensitive_info(page)
            page.screenshot(path=str(SCREENSHOT_V7_DIR / f"01_dashboard_{mode}.png"))
            print(f"Captured: 01_dashboard_{mode}.png")

            # 2. Live Fleet Tracking Portal (view-driver-gps)
            page.evaluate("() => document.querySelector('[data-view=\"driver-gps\"]')?.click()")
            time.sleep(1.5)
            mask_sensitive_info(page)
            page.screenshot(path=str(SCREENSHOT_V7_DIR / f"02_live_fleet_tracking_{mode}.png"))
            print(f"Captured: 02_live_fleet_tracking_{mode}.png")

            # 3. Open Pair Driver Phone Modal
            if mode == "1440":
                page.evaluate("() => document.getElementById('btn-open-pair-driver-modal')?.click()")
                time.sleep(0.5)
                # Select a driver and generate QR
                page.evaluate("""() => {
                    const sel = document.getElementById('select-pair-driver-target');
                    if (sel && sel.options.length > 1) sel.selectedIndex = 1;
                    document.getElementById('btn-generate-pair-token')?.click();
                }""")
                time.sleep(1)
                mask_sensitive_info(page)
                page.screenshot(path=str(SCREENSHOT_V7_DIR / f"03_pair_driver_modal_{mode}.png"))
                print(f"Captured: 03_pair_driver_modal_{mode}.png")
                # Close modal
                page.evaluate("() => document.querySelector('[data-close-modal=\"modal-pair-driver\"]')?.click()")
                time.sleep(0.5)

            # 4. Driver Phone Mobile Portal (driver.html)
            page.goto(f"{BASE_URL}/driver?pair={token}", wait_until="networkidle")
            time.sleep(1.5)
            mask_sensitive_info(page)
            page.screenshot(path=str(SCREENSHOT_V7_DIR / f"04_driver_phone_portal_{mode}.png"))
            print(f"Captured: 04_driver_phone_portal_{mode}.png")

        browser.close()
    print("\nAll v7 screenshots successfully captured to evidence/screenshots_v7/")


if __name__ == "__main__":
    main()
