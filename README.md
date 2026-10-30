# FleetWise — Conflict-Free Fleet & Delivery Assignment Engine

[![FleetWise CI](https://github.com/rabigupta-123/FleetWise-Vehicle-Delivery-Assignment/actions/workflows/ci.yml/badge.svg)](https://github.com/rabigupta-123/FleetWise-Vehicle-Delivery-Assignment/actions/workflows/ci.yml)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.136.3-green.svg)](https://fastapi.tiangolo.com/)
[![SQLite WAL](https://img.shields.io/badge/SQLite-WAL%20Mode-orange.svg)](https://www.sqlite.org/wal.html)
[![Tests Passing](https://img.shields.io/badge/Tests-58%20Passed%20(100%25)-brightgreen.svg)]()
[![Security: Hardened](https://img.shields.io/badge/Security-Hardened%20RBAC%20%2B%20WAL-purple.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

> **IT HAPPENS @ RAALE #13 (Logistics)**  
> Production-grade, conflict-free fleet dispatch, delivery allocation engine, deep telemetry analytics, and physical smartphone GPS tracking system. Built with zero external CDN dependencies (locally vendored Leaflet & Lucide SVGs), strict SQLite `BEGIN IMMEDIATE` + WAL concurrency protection, dark HUD control-room UI inspired by Layers AI, automated Smart Dispatch Advisory, and live Google Maps Street View navigation.

---

## 👥 Engineering Team & Role Ownership

| Member | Role | Primary Responsibilities |
|---|---|---|
| **Sheshman Ahir** | **Team Leader** & Backend Development | Assignment logic, SQLite WAL transaction serialization (`BEGIN IMMEDIATE`), partial unique indexes, status transition matrix, smart advisor ranking |
| **Sandip Sah** | Frontend Development & UI/UX Design | HUD / Control-room design system (`tokens.css`), 4-lane Kanban dispatch board, assignment modal, telemetry badges, Race Lab console, vendored SVG icons |
| **Rabi Kumar Gupta** | Cybersecurity, Validation & QA | 2-phase CSV/JSON import pipeline, CSV injection escaping (`=,+,-,@`), XSS inert DOM sanitization, 58-test automated test suite, 50-thread race stress tests, forensic evidence collection |

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

# 3. Launch Dual Server (Serves HTTP on :8000 and HTTPS on :8443 concurrently)
python scripts/run_dual_server.py
```
- Open Desktop Dashboard: **[http://127.0.0.1:8000](http://127.0.0.1:8000)**
- Open Mobile GPS Portal on Phone: **`https://<your-lan-ip>:8443`** (Enables Secure Context for real physical GPS)

---

## 2. Core Non-Negotiables & Guarantees

### Zero Pre-Seeded / Demo Data
The application starts with an **empty database**. All records enter through:
1. **First-class user file import** (drag-and-drop CSV or JSON array with server-side validation dry-run).
2. **Sample Datasets** included in [`data/`](data/) (`sample_deliveries.csv`, `sample_drivers.csv`, `sample_deliveries.json`, `sample_drivers.json`).
3. **Manual interactive creation modals** (Delivery, Vehicle, Driver).

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

## 3. Mathematical Foundations & Analytics Formulations

FleetWise implements transparent, reproducible mathematics with zero hardcoded or fabricated scores.

### A. Geolocation & Telematics Physics (`app/telematics.py`)

1. **Haversine Great-Circle Surface Distance:**
   $$a = \sin^2\left(\frac{\Delta \phi}{2}\right) + \cos(\phi_1) \cdot \cos(\phi_2) \cdot \sin^2\left(\frac{\Delta \lambda}{2}\right)$$
   $$c = 2 \cdot \text{atan2}\left(\sqrt{a}, \sqrt{1 - a}\right), \quad d = R \cdot c \quad (R = 6,371,000\text{ m})$$
   *Clamped to $[0, 1]$ against floating-point boundary imprecision.*

2. **Derived Kinematic Velocity:**
   $$v = \frac{\Delta d}{\Delta t}$$
   Calculates actual movement velocity from sequential device timestamps. If sensor velocity is missing, derived velocity is enforced.

3. **Telemetry Freshness Categorization:**
   $$\text{Status} = \begin{cases} \text{LIVE} & \Delta t \le 90\text{ s} \\ \text{STALE} & 90 < \Delta t \le 300\text{ s} \\ \text{OFFLINE} & \Delta t > 300\text{ s} \end{cases}$$

4. **Kinematic Jump Anomaly Detection:**
   Flags implausible GPS teleports if:
   $$v > 50\text{ m/s } (180\text{ km/h}) \quad \lor \quad (\Delta d > 300\text{ m} \text{ within } \Delta t < 2\text{ s})$$

---

### B. Mathematical Accuracy Engine (`app/analytics/accuracy_engine.py`)

1. **GPS Precision Quality Score ($0 - 100$):**
   $$Q_{\text{GPS}} = 100 \cdot \exp\left(-\frac{\text{accuracy (meters)}}{50}\right)$$
   - $\text{accuracy} = 5\text{m} \implies Q_{\text{GPS}} \approx 90.5$
   - $\text{accuracy} = 10\text{m} \implies Q_{\text{GPS}} \approx 81.9$
   - $\text{accuracy} = 25\text{m} \implies Q_{\text{GPS}} \approx 60.7$
   - $\text{accuracy} = 50\text{m} \implies Q_{\text{GPS}} \approx 36.8$

2. **Fix Freshness Quality Score ($0 - 100$):**
   $$Q_{\text{freshness}} = 100 \cdot \exp\left(-\frac{\text{age (seconds)}}{120}\right)$$
   - $\text{age} = 0\text{s} \implies 100.0$
   - $\text{age} = 60\text{s} \implies 60.7$
   - $\text{age} = 120\text{s} \implies 36.8$
   - Future timestamps ($\Delta t < 0$) are penalized with `clock_drift_future_timestamp`.

3. **Composite Telemetry Quality Score:**
   $$Q_{\text{telemetry}} = 0.40 \cdot Q_{\text{GPS}} + 0.30 \cdot Q_{\text{freshness}} + 0.20 \cdot Q_{\text{movement}} + 0.10 \cdot Q_{\text{completeness}}$$
   *(Renormalized across available component weights if optional metrics are absent).*

---

### C. Multi-Factor Confidence Engine (`app/analytics/confidence_engine.py`)

1. **Hard Constraint Gate (Defensive Validation):**
   Before computing any heuristic score, mandatory operational invariants are verified:
   - Vehicle must exist and have `status == 'available'`.
   - Driver must exist and have `availability_status == 'available'`.
   - Vehicle capacity must satisfy `capacity >= required_capacity`.
   - Device must not be revoked (`is_revoked == 0`).
   - Neither vehicle nor driver may have active unreleased assignments.
   $$\text{If ANY hard constraint fails} \implies \text{Confidence Score} = 0.0 \text{ (LOW, Rejected)}$$

2. **Capacity Suitability Formula:**
   $$\text{Score}_{\text{capacity}} = 100 - \left(\frac{\text{Capacity} - \text{Weight}}{\text{Capacity}}\right) \times 20$$
   Rewards optimal capacity sizing while penalizing massive vehicle over-allocation for lightweight packages.

---

### D. Deep Analytics Performance Metrics (`app/analytics/deep_analysis.py`)

1. **Fleet Utilization Rate:**
   $$U_{\text{fleet}} = \frac{V_{\text{active}}}{V_{\text{total}} - V_{\text{inactive}}} \times 100\%$$
   *(Excludes decommissioned/inactive vehicles from active capacity).*

2. **Driver Utilization Rate:**
   $$U_{\text{driver}} = \frac{D_{\text{active}}}{D_{\text{total}} - D_{\text{unavailable}}} \times 100\%$$

3. **Delivery Completion Rate:**
   $$R_{\text{completion}} = \frac{N_{\text{delivered}}}{N_{\text{total}} - N_{\text{cancelled}}} \times 100\%$$

4. **On-Time Delivery Rate:**
   $$R_{\text{on-time}} = \frac{N_{\text{delivered, on-time}}}{N_{\text{delivered with deadline}}} \times 100\%$$

---

## 4. API Endpoints & Status Code Guide

> ### ℹ️ Understanding REST Status Codes in FleetWise
> The status codes documented below represent standard HTTP specifications returned by our defensive validation and security layers:
> - **`200 OK` / `201 Created`**: Successful state query or atomic resource creation.
> - **`400 Bad Request`**: Validation rejection (e.g. invalid phone format, negative capacity, or malformed JSON).
> - **`401 Unauthorized`**: Authentication required (enforced for write operations over public internet tunnels).
> - **`403 Forbidden`**: Authorization denied (e.g. attempting to ingest GPS fixes from a revoked device token).
> - **`404 Not Found`**: Target ID does not exist in the database.
> - **`409 Conflict`**: Atomic concurrency protection (e.g. duplicate assignment prevention, occupied vehicle collision).
> - **`429 Rate Limited`**: Telematics throttle (enforces $\ge 0.5\text{s}$ interval to prevent sensor spam).

| Method | Route | Description | Expected Status Codes |
|---|---|---|---|
| `GET` | `/` | Serves static SPA frontend control room | `200` |
| `GET` | `/health` | Health check (verifies SQLite WAL mode, foreign keys, table counts) | `200` |
| `GET` | `/metrics` | Fleet telemetry (available fleet, active deliveries, delivered, utilisation %) | `200` |
| `GET` | `/audit` | Chronological immutable transaction audit trail | `200` |
| `GET` | `/api/system/power-status` | **Physical Win32 Kernel Power Status** (bypasses browser dummy stubs) | `200` |
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
| `POST` | `/deliveries/auto-assign` | Auto-assign pending deliveries using Smart Advisor scoring | `200`, `400` |
| `GET` | `/events` | Real-time Server-Sent Events (SSE) telemetry stream | `200` |
| `POST` | `/diagnostics/concurrency-test` | Race Lab: parallel allocation stress test against isolated temporary DB | `200` |
| `GET` | `/analytics/overview` | Executive KPI dashboard with telemetry & completion analytics | `200` |
| `GET` | `/analytics/fleet` | Fleet utilization, status distribution, and maintenance ratios | `200` |
| `GET` | `/analytics/drivers` | Driver active hours, completed runs, and on-time percentages | `200` |
| `GET` | `/analytics/deliveries` | Delivery funnel, transit durations, and deadline compliance | `200` |
| `GET` | `/analytics/accuracy` | Quality scores for GPS precision, freshness, and kinematic continuity | `200` |
| `GET` | `/analytics/confidence` | Identity, location, and assignment multi-factor confidence ratings | `200` |
| `GET` | `/analytics/anomalies` | Detected kinematic jumps, out-of-order fixes, and device revocations | `200` |
| `GET` | `/export/{entity}.csv` | Formula-injection safe CSV export (`vehicles`, `drivers`, `deliveries`, `audit`) | `200`, `404` |
| `POST` | `/auth/login` | Session login with scrypt password hashing & signed HTTP-only cookies | `200`, `400`, `401` |
| `GET` | `/auth/me` | Current authenticated user & RBAC role | `200` |
| `POST` | `/auth/logout` | Terminate session & clear cookies | `200` |
| `GET` | `/import/templates/{entity}.csv` | Download header-only CSV template (`vehicles`, `drivers`, `deliveries`) | `200`, `404` |
| `POST` | `/import/{entity}?dry_run=true\|false` | Validate & import CSV or JSON array (all-or-nothing atomic transaction) | `200`, `400` |
| `POST` | `/devices/register` | Register test smartphone / browser device session & capabilities | `201`, `400` |
| `GET` | `/devices` | List registered devices with driver association and revocation status | `200` |
| `GET` | `/devices/{device_id}` | Detailed device profile, active tracking session, and latest location | `200`, `404` |
| `POST` | `/devices/{device_id}/revoke` | Revoke device authorization (instantly halts GPS fix ingestion) | `200`, `403`, `404` |
| `POST` | `/tracking/sessions/start` | Start tracking session for a driver (links active vehicle & delivery assignment) | `201`, `400`, `404` |
| `POST` | `/tracking/sessions/stop` | Stop active tracking session | `200`, `400`, `404` |
| `POST` | `/tracking/location` | Ingest real device GPS fix (rate limited, jump detection, bounds check) | `201`, `400`, `403`, `429` |
| `GET` | `/tracking/drivers/{id}/latest` | Fetch latest GPS fix, staleness flag, and Google Street View link | `200`, `404` |
| `GET` | `/tracking/vehicles/{id}/latest` | Fetch vehicle live location, assigned driver, active delivery, and Street View | `200`, `404` |
| `GET` | `/tracking/deliveries/{id}/latest` | Fetch delivery location, transit trail, driver position, and corridor Street View | `200`, `404` |
| `GET` | `/tracking/history` | Query location history trail (`?vehicle_id=`, `?delivery_id=`, `?session_id=`) | `200` |
| `GET` | `/tracking/telemetry-graph` | Time-series telemetry points (speed km/h, accuracy m, cumulative distance km) | `200` |

---

## 5. Real Physical Smartphone GPS Tracking & Dual Server

FleetWise streams **genuine physical device GPS fixes** using your smartphone without mock generators:

1. **Physical Geolocation API:** Fixes are captured exclusively via browser `navigator.geolocation.watchPosition()` on the phone with explicit driver consent.
2. **Dual-Server Protocol Architecture:**
   - Launch `python scripts/run_dual_server.py`.
   - Runs `http://0.0.0.0:8000` (Fast standard access for desktop).
   - Runs `https://0.0.0.0:8443` (TLS with local IP Subject Alternative Names).
   - **Why HTTPS is Required for Phones:** Modern mobile browsers (iOS Safari and Android Chrome) enforce W3C Secure Context rules; they permanently disable `navigator.geolocation` on non-localhost HTTP. Accessing via `https://<your-lan-ip>:8443` enables location permission prompts immediately.
3. **Google Maps Street View Links:**
   Inspect vehicles and drivers directly in Street View at physical GPS fixes:
   ```
   https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={latitude},{longitude}
   ```
4. **Physical Power Telemetry:**
   When running locally, FleetWise directly queries Windows Kernel power drivers via `GetSystemPowerStatus`, avoiding Chromium's hardcoded 100% battery privacy stub and reflecting real battery percentages and charging states.

---

## 6. Verification & Automated Test Suite

FleetWise includes an exhaustive 58-test verification suite covering unit models, concurrency stress tests, transaction race conditions, math accuracy, and security guards:

```bash
# Execute entire test suite
pytest -v
```

### Test Suite Execution Summary:
```
======================= 58 passed, 1 warning in 38.48s =======================
```

| Test Module | Tests | Focus Area |
|---|---|---|
| `tests/test_fleetwise.py` | 27 | Transaction isolation (`BEGIN IMMEDIATE`), partial unique index guards, 50-thread race stress tests, 5x5 state matrix, XSS sanitization |
| `tests/test_master_analytics_and_confidence.py` | 8 | Mathematical Accuracy Engine, Freshness Decay, Kinematic Jumps, Confidence Constraints, Deep Analytics endpoints |
| `tests/test_device_intelligence_and_security.py` | 10 | Device hardware fingerprinting, token separation, device revocation guards, concurrent GPS rate limits, tunnel RBAC |
| `tests/test_telemetry_formulas.py` | 4 | Haversine precision ($R=6,371,000\text{m}$), velocity derivation, freshness status thresholds, GPS rate limiting |
| `tests/test_devices.py` | 3 | Device registration, listing, revocation, and negative authorization cases |
| `tests/test_tracking.py` | 3 | Tracking session lifecycle, GPS boundary validation, and driver phone mapping |
| `tests/test_phone_verification.py` | 2 | E.164 phone normalization, SHA-256 OTP challenge generation, and rate limits |
| `tests/test_all_endpoints.py` | 1 | Comprehensive audit of all 46 API endpoints and HTTP status code contracts |

---

## 7. License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
