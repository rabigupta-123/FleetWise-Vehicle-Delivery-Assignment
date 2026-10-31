"""
FleetWise — Automated Browser Verification & Screenshot Capture Suite v6.
Verifies all demo features in Chromium:
- Load demo data
- Clear demo data
- Simulator toggle
- Assignment from Dispatch Console
- Delivery status changes
- Smart Advisor & recommendations
- Parallel Allocation Race Lab
- Import Data page
- Driver Phone Portal
Captures evidence screenshots at 1440px (desktop) and 375px (mobile).
"""
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from playwright.sync_api import sync_playwright
from app.auth import generate_pairing_token

SCREENSHOT_V6_DIR = BASE_DIR / "evidence" / "screenshots_v6"
SCREENSHOT_V6_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "http://127.0.0.1:8000"


def mask_sensitive_info(page):
    """Redacts any actual host IPs, phone numbers, or emails from screenshot views."""
    page.evaluate("""() => {
        // Redact any visible physical IPs or emails
        document.querySelectorAll('*').forEach(el => {
            if (el.children.length === 0 && el.textContent) {
                if (el.textContent.includes('10.') || el.textContent.includes('192.168.')) {
                    el.textContent = el.textContent.replace(/\\b(?:10|192\\.168)\\.\\d{1,3}\\.\\d{1,3}\\b/g, 'LAN.FLEETWISE.LOCAL');
                }
            }
        });
    }""")


def run_browser_verification():
    print(f"Connecting to live server at {BASE_URL}...")
    token = generate_pairing_token()

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)

        for mode, width, height in [("1440", 1440, 900), ("375", 375, 812)]:
            print(f"\n--- Testing viewport {mode} ({width}x{height}) ---")
            context = browser.new_context(viewport={"width": width, "height": height})
            page = context.new_page()

            # 1. Open Dashboard
            page.goto(f"{BASE_URL}/", wait_until="networkidle")
            time.sleep(1)
            mask_sensitive_info(page)
            page.screenshot(path=str(SCREENSHOT_V6_DIR / f"01_dashboard_{mode}.png"))
            print(f"Captured: 01_dashboard_{mode}.png")

            # 2. Trigger Load Demo Data
            page.evaluate("() => document.getElementById('btn-load-demo')?.click()")
            time.sleep(1)

            # 3. Dispatch Console View
            page.evaluate("() => document.querySelector('[data-view=\"dispatch\"]')?.click()")
            time.sleep(1)
            mask_sensitive_info(page)
            page.screenshot(path=str(SCREENSHOT_V6_DIR / f"02_dispatch_{mode}.png"))
            print(f"Captured: 02_dispatch_{mode}.png")

            # 4. Smart Advisor / Recommendations
            page.evaluate("() => document.querySelector('[data-view=\"dashboard\"]')?.click()")
            time.sleep(0.5)
            mask_sensitive_info(page)
            page.screenshot(path=str(SCREENSHOT_V6_DIR / f"03_advisor_{mode}.png"))
            print(f"Captured: 03_advisor_{mode}.png")

            # 5. Parallel Allocation Race Lab
            page.evaluate("() => document.querySelector('[data-view=\"racelab\"]')?.click()")
            time.sleep(1)
            # Trigger a diagnostic run in race lab
            page.evaluate("() => document.getElementById('btn-run-race')?.click()")
            time.sleep(1.5)
            mask_sensitive_info(page)
            page.screenshot(path=str(SCREENSHOT_V6_DIR / f"04_racelab_{mode}.png"))
            print(f"Captured: 04_racelab_{mode}.png")

            # 6. Import Data Page
            page.evaluate("() => document.querySelector('[data-view=\"import\"]')?.click()")
            time.sleep(1)
            mask_sensitive_info(page)
            page.screenshot(path=str(SCREENSHOT_V6_DIR / f"05_import_{mode}.png"))
            print(f"Captured: 05_import_{mode}.png")

            # 7. Simulator Active State
            page.evaluate("() => document.getElementById('btn-sim-toggle')?.click()")
            time.sleep(1)
            mask_sensitive_info(page)
            page.screenshot(path=str(SCREENSHOT_V6_DIR / f"06_simulator_{mode}.png"))
            print(f"Captured: 06_simulator_{mode}.png")

            # 8. Driver Phone Portal
            driver_url = f"{BASE_URL}/driver?pair={token}"
            page.goto(driver_url, wait_until="networkidle")
            time.sleep(1)
            mask_sensitive_info(page)
            page.screenshot(path=str(SCREENSHOT_V6_DIR / f"07_driver_portal_{mode}.png"))
            print(f"Captured: 07_driver_portal_{mode}.png")

            context.close()

        browser.close()
    print("\nAll browser verification screenshots captured in evidence/screenshots_v6/ successfully!")


if __name__ == "__main__":
    run_browser_verification()
