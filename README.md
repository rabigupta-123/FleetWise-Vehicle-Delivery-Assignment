# FleetWise — Conflict-Free Fleet & Delivery Assignment Engine

[![FleetWise CI](https://github.com/rabigupta-123/FleetWise-Vehicle-Delivery-Assignment/actions/workflows/ci.yml/badge.svg)](https://github.com/rabigupta-123/FleetWise-Vehicle-Delivery-Assignment/actions/workflows/ci.yml)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.136.3-green.svg)](https://fastapi.tiangolo.com/)
[![SQLite WAL](https://img.shields.io/badge/SQLite-WAL%20Mode-orange.svg)](https://www.sqlite.org/wal.html)
[![Tests Passing](https://img.shields.io/badge/Tests-40%20Passed%20(100%25)-brightgreen.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-purple.svg)](LICENSE)

> **IT HAPPENS @ RAALE #13 (Logistics)**  
> Production-grade, conflict-free fleet dispatch, delivery allocation engine, and real smartphone GPS tracking system. Built with zero CDN dependencies (locally vendored Leaflet & Lucide SVGs), strict SQLite `BEGIN IMMEDIATE` + WAL concurrency protection, dark HUD control-room UI, automated Smart Dispatch Advisory, and live Street View navigation.

---

## 👥 Engineering Team & Role Ownership

| Member | Role | Primary Responsibilities |
|---|---|---|
| **Sheshman Ahir** | **Team Leader** & Backend Development | Assignment logic, SQLite WAL transaction serialization (`BEGIN IMMEDIATE`), partial unique indexes, status transition matrix, smart advisor ranking |
| **Sandip Sah** | Frontend Development & UI/UX Design | HUD / Control-room design system (`tokens.css`), 4-lane Kanban dispatch board, assignment modal, telemetry badges, Race Lab console, vendored SVG icons |
| **Rabi Kumar Gupta** | Cybersecurity, Validation & QA | 2-phase CSV/JSON import pipeline, CSV injection escaping (`=,+,-,@`), XSS inert DOM sanitization, 27-test automated test suite, 50-thread race stress tests, forensic evidence collection |

---

## Visual Tour

| Command Center (Telemetry & 4-Lane Board) | Dispatch Console (Atomic Assignment) |
|---|---|
| ![Command Center Dashboard](evidence/screenshots_v2/03_dashboard_populated.png) | ![Dispatch Console](evidence/screenshots_v2/04_successful_assignment.png) |

| Smart Dispatch Advisor & Blocked Queue | Parallel Allocation Race Lab (50 Workers) |
|---|---|
| ![Smart Advisor & Blocked Queue](evidence/screenshots_v2/09_smart_advisor_and_blocked_queue.png) | ![Race Lab Diagnostic](evidence/screenshots_v2/10_race_lab_diagnostic_proof.png) |

| Analytics Radar & Route Canvas | 2-Phase Import Pipeline (Dry-Run & Commit) |
|---|---|
| ![Analytics & Route Radar](evidence/screenshots_v2/11_analytics_and_routes.png) | ![Import Pipeline](evidence/screenshots_v2/02_import_page.png) |

---

## 1. Quick Start

### Prerequisites
- Python 3.11+
- Git

### Installation & Launch
```bash
# 1. Clone repository & enter workspace
git clone https://github.com/rabigupta-123/FleetWise-Vehicle-Delivery-Assignment.git
cd FleetWise-Vehicle-Delivery-Assignment

# 2. Install dependencies (standard library + FastAPI, Uvicorn, Pydantic v2, Pytest, HTTPX)
pip install -r requirements.txt

# 3. Start the application server
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
Open your browser to: **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

---

## 2. Core Non-Negotiables & Guarantees

### Zero Pre-Seeded / Demo Data
The application starts with an **empty database**. All records enter through:
1. **First-class user file import** (drag-and-drop CSV or JSON array with server-side validation dry-run).
2. **Manual interactive creation modals** (Delivery, Vehicle, Driver).

### Non-Negotiable Core Rule
> **Never assign an occupied vehicle or an unavailable/occupied driver.**
- **Database Engine Partial Unique Indexes:**
  ```sql
  CREATE UNIQUE INDEX idx_assignments_active_vehicle ON assignments(vehicle_id) WHERE released_at IS NULL;
  CREATE UNIQUE INDEX idx_assignments_active_driver  ON assignments(driver_id)  WHERE released_at IS NULL;
  CREATE UNIQUE INDEX idx_assignments_active_delivery ON assignments(delivery_id) WHERE released_at IS NULL;
  ```
- **Transaction Serialization:** Opened with `BEGIN IMMEDIATE`. Re-reads and re-validates all resources inside the transaction boundary before mutating states.
- **Active Lifecycle:** Active deliveries are defined as `status IN ('assigned', 'in_transit')`. Transitioning to `delivered` or `cancelled` atomically sets `assignment.released_at` and restores vehicle and driver to `available`.

---

## 3. Architecture & Data Model

```
                  +-------------------------+
                  |        vehicles         |
                  +-------------------------+
                  | vehicle_id (PK)         |
                  | registration_no (UNIQUE)|
                  | type                    |
                  | capacity                |
                  | status                  |
                  +------------+------------+
                               | 1
                               |
                               | *
+-------------------+     +----+--------------------+     +------------------------+
|    deliveries     |     |      assignments        |     |        drivers         |
+-------------------+     +-------------------------+     +------------------------+
| delivery_id (PK)  |1   *| assignment_id (PK)      |*   1| driver_id (PK)         |
| pickup            +-----+ delivery_id (FK)        +-----+ name                   |
| dropoff           |     | vehicle_id (FK)         |     | phone                  |
| scheduled_time    |     | driver_id (FK)          |     | availability_status    |
| priority          |     | assigned_at             |     +------------------------+
| required_capacity |     | released_at (NULLABLE)  |
| status            |     | release_reason          |
| created_at        |     +-------------------------+
| version           |
+-------------------+
```

---

## 4. API Endpoints

| Method | Route | Description | Status Codes |
|---|---|---|---|
| `GET` | `/` | Serves static SPA frontend control room | `200` |
| `GET` | `/health` | Health check (verifies SQLite WAL mode, foreign keys, table counts) | `200` |
| `GET` | `/metrics` | Fleet telemetry (available fleet, active deliveries, delivered, utilisation %) | `200` |
| `GET` | `/audit` | Chronological immutable transaction audit trail | `200` |
| `GET` | `/vehicles` | List all vehicles with active delivery assignments | `200` |
| `POST` | `/vehicles` | Register vehicle (auto-assigns `V-###` if omitted) | `201`, `400`, `409` |
| `PATCH` | `/vehicles/{id}/status` | Manual status change (`available`, `maintenance`, `inactive`). Guarded while occupied. | `200`, `404`, `409` |
| `GET` | `/drivers` | List all drivers with active delivery assignments | `200` |
| `POST` | `/drivers` | Register driver (auto-assigns `DR-###` if omitted) | `201`, `400`, `409` |
| `PATCH` | `/drivers/{id}/status` | Manual availability change (`available`, `unavailable`). Guarded while occupied. | `200`, `404`, `409` |
| `GET` | `/deliveries` | List deliveries (`?status=&q=`) | `200` |
| `POST` | `/deliveries` | Create pending delivery (auto-assigns `D-###` if omitted) | `201`, `400`, `409` |
| `POST` | `/deliveries/{id}/assign` | **Atomic assignment** under `BEGIN IMMEDIATE` + partial unique index guard | `201`, `400`, `404`, `409` |
| `PATCH` | `/deliveries/{id}/status` | Lifecycle transition (`assigned -> in_transit`, `in_transit -> delivered`, etc.) | `200`, `404`, `409` |
| `GET` | `/deliveries/{id}/recommendations` | Smart Advisor: ranked eligible (vehicle, driver) pairs with score breakdown | `200`, `404` |
| `GET` | `/deliveries/dispatch-next` | Dispatch Next: selects highest-priority pending delivery | `200` |
| `GET` | `/deliveries/blocked` | Blocked Queue: lists pending deliveries that lack eligible resources with exact reasons | `200` |
| `POST` | `/deliveries/auto-assign?dry_run=true\|false` | Auto-assign pending deliveries using Smart Advisor scoring | `200`, `400` |
| `GET` | `/events` | Real-time Server-Sent Events (SSE) telemetry stream | `200` |
| `POST` | `/diagnostics/concurrency-test?workers=N` | Race Lab: parallel allocation stress test against isolated temporary DB | `200` |
| `GET` | `/analytics/summary` | Analytics: on-time rate, status funnel, driver trip distribution | `200` |
| `GET` | `/deliveries/routes` | Route Radar: active pickup/dropoff corridors and telemetry coordinates | `200` |
| `GET` | `/export/{entity}.csv` | Formula-injection safe CSV export (`vehicles`, `drivers`, `deliveries`, `audit`) | `200`, `404` |
| `POST` | `/auth/login` | Session login with scrypt password hashing & signed HTTP-only cookies | `200`, `400`, `401` |
| `GET` | `/auth/me` | Current authenticated user & RBAC role | `200` |
| `POST` | `/auth/logout` | Terminate session & clear cookies | `200` |
| `GET` | `/import/templates/{entity}.csv` | Download header-only CSV template (`vehicles`, `drivers`, `deliveries`) | `200`, `404` |
| `POST` | `/import/{entity}?dry_run=true\|false` | Validate & import CSV or JSON array (all-or-nothing atomic transaction) | `200`, `400` |
| `PATCH` | `/drivers/{id}/phone` | Update driver phone number (E.164 normalization & carrier/country parsing) | `200`, `400`, `404` |
| `POST` | `/drivers/{id}/phone/request-verification` | Request 6-digit OTP challenge for driver phone (SHA-256 hashed, rate limited) | `200`, `400`, `429` |
| `POST` | `/drivers/{id}/phone/verify` | Submit OTP verification code to confirm authenticated ownership | `200`, `400` |
| `POST` | `/devices/register` | Register test smartphone / browser device session & capabilities | `201`, `400` |
| `GET` | `/devices` | List registered devices with driver association and revocation status | `200` |
| `GET` | `/devices/{device_id}` | Detailed device profile, active tracking session, and latest location | `200`, `404` |
| `POST` | `/devices/{device_id}/revoke` | Revoke device authorization (blocks subsequent GPS fix ingestion) | `200`, `404` |
| `GET` | `/devices/{device_id}/telemetry` | Time-series telemetry points for a specific authenticated device | `200`, `404` |
| `POST` | `/tracking/sessions/start` | Start tracking session for a driver (links active vehicle & delivery assignment) | `201`, `400`, `404` |
| `POST` | `/tracking/sessions/stop` | Stop active tracking session | `200`, `400`, `404` |
| `POST` | `/tracking/location` | Ingest real device GPS fix (validates lat/lng, speed, accuracy, ISO timestamp) | `201`, `400` |
| `GET` | `/tracking/drivers/{id}/latest` | Fetch latest GPS fix, staleness flag, and Google Street View link | `200`, `404` |
| `GET` | `/tracking/vehicles/{id}/latest` | Fetch vehicle live location, assigned driver, active delivery, and Street View | `200`, `404` |
| `GET` | `/tracking/deliveries/{id}/latest` | Fetch delivery location, transit trail, driver position, and corridor Street View | `200`, `404` |
| `GET` | `/tracking/history` | Query location history trail (`?vehicle_id=`, `?delivery_id=`, `?session_id=`) | `200` |
| `GET` | `/tracking/telemetry-graph` | Time-series telemetry points (speed km/h, accuracy m, cumulative distance km) | `200` |

---


---

## 5. Device Intelligence, Telematics Physics & Extensible Providers

FleetWise implements transparent, verified telematics mathematics and strict device lifecycle authorization:

### Mathematical Telematics Formulas (`app/telematics.py`)
1. **Haversine Great-Circle Surface Distance:**
   $$a = \sin^2\left(\frac{\Delta \phi}{2}\right) + \cos(\phi_1) \cdot \cos(\phi_2) \cdot \sin^2\left(\frac{\Delta \lambda}{2}\right)$$
   $$c = 2 \cdot \text{atan2}(\sqrt{a}, \sqrt{1 - a}), \quad d = R \cdot c \quad (R = 6,371,000\text{ m})$$
   *Clamped to $[0, 1]$ against floating-point boundary imprecision.*

2. **Derived Speed Kinematics:**
   $$v_{\text{derived}} = \frac{\Delta d}{\Delta t}$$
   Calculates actual movement velocity from sequential device timestamps. If reported GPS sensor velocity is absent, derived velocity takes precedence.

3. **Telemetry Freshness Thresholds:**
   $$\text{Status} = \begin{cases} \text{LIVE} & \Delta t \le 90\text{ seconds} \\ \text{STALE} & 90 < \Delta t \le 300\text{ seconds} \\ \text{OFFLINE} & \Delta t > 300\text{ seconds} \end{cases}$$

4. **Implausible Jump Outlier Detection:**
   Flags impossible GPS jumps if $v > 50\text{ m/s}$ ($180\text{ km/h}$) or if $\Delta d > 300\text{ m}$ within $\Delta t < 2\text{ s}$, preventing sensor glitches from distorting fleet metrics.

5. **Anti-Flooding Rate Limiting:**
   Enforces a minimum interval of 0.8s between consecutive device fixes per tracking session (`429 RATE_LIMITED`).

### Device Lifecycle & Security
- **Device Registration (`/devices/register`):** Client-side platform capability detection without invasive tracking.
- **Revocation Protection:** Revoking a device instantly halts active tracking sessions and blocks further GPS fix ingestion with `403 DEVICE_REVOKED`.
- **E.164 Normalization & Phone Verification:** International number parsing (`phonenumbers` library), carrier detection, and rate-limited 6-digit challenge verification with SHA-256 hashed storage.
- **Privacy Boundaries:** A phone number is an identifier, not a sensor. Real GPS coordinates are ingested exclusively from browser HTML5 Geolocation with explicit driver consent. Zero simulated or fabricated coordinates in production databases.

### Extensible Provider Architecture (`app/providers.py`)
FleetWise abstracts external integrations via clean interfaces:
- `BaseTelematicsProvider`: Direct hardware GPS / OBD-II dongle streaming.
- `BaseIPGeolocationProvider`: IP-to-city lookup for network context (explicitly disclosed as approximate, NOT GPS).
- `BaseSMSGatewayProvider`: Multi-tenant SMS delivery for OTP challenges.

## 6. Real Smartphone GPS Tracking, Vehicle Tracking & Street View

FleetWise supports **genuine physical device GPS tracking** using your smartphone:

### How It Works:
1. **Explicit Privacy Consent & Real Geolocation:** Coordinates are captured via the standard browser `navigator.geolocation.watchPosition()` API directly on your mobile device. The system **never** simulates or fabricates GPS fixes and never derives coordinates from phone numbers.
2. **Driver Phone Number Authorization:** Assign or update any driver's phone number to your own mobile number using the **Change Phone #** modal.
3. **Driver Phone GPS Portal (`View 8`):** Open `http://<your-lan-ip>:8000` on your smartphone browser, select your driver profile, and tap **Start GPS Tracking**. Your phone streams high-precision fixes (latitude, longitude, accuracy, velocity, heading) into FleetWise.
4. **Vehicle Live GPS Radar (`View 6`):** Inspect any vehicle on an interactive Leaflet map (dark HUD styling, 100% locally vendored, zero CDN). View breadcrumb trails, real-time speed/accuracy telemetry curves, and launch **Google Maps Street View** directly at the vehicle's exact physical coordinates:
   ```
   https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={lat},{lng}
   ```
5. **Delivery Transit Tracking (`View 7`):** Track the driver's progress along active delivery corridors, view pickup/dropoff points, and verify transit velocity profiles.
6. **Zero-CDN Architecture:** Leaflet CSS/JS assets are vendored locally in `static/vendor/leaflet/` to ensure full functionality in air-gapped or restricted network environments.

> **Mobile Network Note:** For security reasons, modern smartphone browsers require `localhost` or `https://` to permit `navigator.geolocation`. When testing over a local Wi-Fi network, use local port forwarding (`adb forward` or Chrome remote debugging) or access over a local development HTTPS certificate. Also keep the browser tab open, as mobile operating systems may throttle background tabs when the screen is locked.

---

## 6. User Data Import Formats

FleetWise accepts CSV or JSON arrays for import:

### Vehicles (`vehicles.csv`)
```csv
vehicle_id,registration_no,type,capacity,status
V-001,KA-01-AB-1001,Refrigerated Van,1500,available
V-002,KA-01-AB-1002,Heavy Freight,5000,available
```

### Drivers (`drivers.csv`)
```csv
driver_id,name,phone,availability_status
DR-001,Aarav Sharma,+91-9876543210,available
DR-002,Priya Nair,+91-9876543211,available
```

### Deliveries (`deliveries.csv`)
```csv
delivery_id,pickup,dropoff,scheduled_time,priority,required_capacity
D-001,Central Hub Sector 4,Terminal B Cold Storage,2026-10-30T10:00:00Z,urgent,1000
D-002,Warehouse 12,Cargo Gate 3,2026-10-30T11:30:00Z,normal,500
```

---

## 7. Verification & Automated Test Suite

Execute the comprehensive automated test suite (verifying T1–T12, snapshot comparisons, 50-thread concurrency, 5x5 transition matrix, formula injection sanitization, real GPS ingestion boundaries, session lifecycles, and import validations against isolated temporary SQLite databases):

```bash
pytest -v
```

All **40 / 40 tests passed (100% pass rate)**. Test evidence is logged directly to [`evidence/test_results.json`](evidence/test_results.json).

To re-run the Playwright browser judge flow:
```bash
python scripts/run_browser_judge_flow.py
```
Outputs screenshots directly into [`evidence/screenshots_v2/`](evidence/screenshots_v2/).

> **Note on Example Rows:** The CSV/JSON rows shown above are purely illustrative templates. FleetWise starts with a completely empty database; zero pre-seeded records exist. All records enter strictly via user import or interactive creation modals.


