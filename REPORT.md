# FleetWise — Engineering & Verification Report
**IT HAPPENS @ RAALE #13 — Logistics**  
**System:** Vehicle & Delivery Assignment Control Room  
**Date:** 2026-10-29  

---

## 1. What We Built
FleetWise is a production-grade, conflict-free fleet dispatch and delivery allocation system built for mission-critical logistics operations. It enforces the non-negotiable invariant that **no occupied vehicle or unavailable/occupied driver can ever be assigned to more than one active delivery**, while simultaneously supporting high-concurrency dispatch requests without race conditions or partial updates.

### Key Highlights
- **Zero Pre-Seeded / Demo Data:** Starts with an empty database. All data enters via drag-and-drop CSV/JSON user file import with server dry-run validation and atomic all-or-nothing commit, or manual create forms.
- **Strict Concurrency Protection:** Powered by SQLite in Write-Ahead Logging (`WAL`) mode with explicit `BEGIN IMMEDIATE` transaction serialization and partial unique indexes (`WHERE released_at IS NULL`).
- **Dark Control Room Interface:** Designed according to `design-system/fleetwise/MASTER.md` (HUD / Sci-Fi FUI, 8/10 density, 3/10 subtle motion). Includes bento KPI telemetry, 4-lane live operations board (`Pending`, `Assigned`, `In Transit`, `Delivered`), resource eligibility inspector, `Ctrl+K` command palette, and local Lucide SVG icons (zero external CDN dependencies).
- **Comprehensive Verification:** 15 automated pytest tests including T1–T12 with database snapshot comparison, multi-threaded concurrency stress testing (`ThreadPoolExecutor`), and full-stack Playwright browser screenshots.

---

## 2. Data Model
The database uses SQLite 3 with `PRAGMA foreign_keys = ON` and `PRAGMA journal_mode = WAL`.

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
+-------------------+
```

### Table Definitions & Constraints
1. **`vehicles`**:
   - `vehicle_id TEXT PRIMARY KEY` (auto-formatted `V-###` if omitted)
   - `registration_no TEXT UNIQUE NOT NULL`
   - `type TEXT NOT NULL`
   - `capacity REAL NOT NULL CHECK (capacity > 0)`
   - `status TEXT NOT NULL DEFAULT 'available' CHECK (status IN ('available', 'assigned', 'maintenance', 'inactive'))`

2. **`drivers`**:
   - `driver_id TEXT PRIMARY KEY` (auto-formatted `DR-###` if omitted)
   - `name TEXT NOT NULL`
   - `phone TEXT NOT NULL`
   - `availability_status TEXT NOT NULL DEFAULT 'available' CHECK (availability_status IN ('available', 'assigned', 'unavailable'))`

3. **`deliveries`**:
   - `delivery_id TEXT PRIMARY KEY` (auto-formatted `D-###` if omitted)
   - `pickup TEXT NOT NULL`, `dropoff TEXT NOT NULL`
   - `scheduled_time TEXT NOT NULL` (ISO 8601 string)
   - `priority TEXT NOT NULL CHECK (priority IN ('low', 'normal', 'high', 'urgent'))`
   - `required_capacity REAL NULL CHECK (required_capacity IS NULL OR required_capacity > 0)`
   - `status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'assigned', 'in_transit', 'delivered', 'cancelled'))`
   - `created_at TEXT NOT NULL`

4. **`assignments`**:
   - `assignment_id TEXT PRIMARY KEY`
   - `delivery_id TEXT NOT NULL REFERENCES deliveries(delivery_id)`
   - `vehicle_id TEXT NOT NULL REFERENCES vehicles(vehicle_id)`
   - `driver_id TEXT NOT NULL REFERENCES drivers(driver_id)`
   - `assigned_at TEXT NOT NULL`
   - `released_at TEXT NULL`
   - `release_reason TEXT NULL`

5. **`audit_log`**:
   - `id INTEGER PRIMARY KEY AUTOINCREMENT`
   - `ts TEXT NOT NULL`, `actor TEXT NOT NULL`, `action TEXT NOT NULL`
   - `entity TEXT NOT NULL`, `entity_id TEXT NOT NULL`
   - `before_json TEXT NULL`, `after_json TEXT NULL`

6. **`tracking_sessions`**:
   - `session_id INTEGER PRIMARY KEY AUTOINCREMENT`
   - `driver_id TEXT NOT NULL REFERENCES drivers(driver_id)`
   - `vehicle_id TEXT NULL REFERENCES vehicles(vehicle_id)`
   - `delivery_id TEXT NULL REFERENCES deliveries(delivery_id)`
   - `device_info TEXT NULL`
   - `started_at TEXT NOT NULL`, `stopped_at TEXT NULL`
   - `status TEXT NOT NULL CHECK(status IN ('active', 'stopped', 'expired'))`

7. **`gps_locations`**:
   - `location_id INTEGER PRIMARY KEY AUTOINCREMENT`
   - `session_id INTEGER NOT NULL REFERENCES tracking_sessions(session_id)`
   - `driver_id TEXT NOT NULL REFERENCES drivers(driver_id)`
   - `vehicle_id TEXT NULL REFERENCES vehicles(vehicle_id)`
   - `delivery_id TEXT NULL REFERENCES deliveries(delivery_id)`
   - `latitude REAL NOT NULL CHECK(latitude BETWEEN -90.0 AND 90.0)`
   - `longitude REAL NOT NULL CHECK(longitude BETWEEN -180.0 AND 180.0)`
   - `accuracy REAL NOT NULL CHECK(accuracy >= 0.0)`
   - `speed REAL NULL CHECK(speed IS NULL OR speed >= 0.0)`
   - `heading REAL NULL CHECK(heading IS NULL OR (heading >= 0.0 AND heading <= 360.0))`
   - `device_timestamp TEXT NOT NULL`, `server_timestamp TEXT NOT NULL`
   - `is_valid INTEGER NOT NULL DEFAULT 1`
   - *Indexes:* `idx_gps_driver_ts`, `idx_gps_vehicle_ts`, `idx_gps_delivery_ts`, `idx_gps_session_ts`

### Database Engine Partial Unique Indexes
To prevent race conditions at the storage engine level, partial unique indexes guarantee that no resource can have more than one unreleased assignment:
```sql
CREATE UNIQUE INDEX idx_assignments_active_vehicle ON assignments(vehicle_id) WHERE released_at IS NULL;
CREATE UNIQUE INDEX idx_assignments_active_driver  ON assignments(driver_id)  WHERE released_at IS NULL;
CREATE UNIQUE INDEX idx_assignments_active_delivery ON assignments(delivery_id) WHERE released_at IS NULL;
```

---

## 3. Assignment Rule & Concurrency Handling
The core invariant of FleetWise is that an assignment must never create a double-booking or violate operational constraints.

### Execution Lifecycle (`POST /deliveries/{id}/assign`)
1. **Transaction Initialization**: The transaction begins with `BEGIN IMMEDIATE`. This immediately acquires a reserved write lock on SQLite, serializing concurrent writes and blocking competing assign requests from reading stale state.
2. **Re-Read & Re-Validation Inside Lock**:
   - **Delivery Validation**: Fetches target delivery. Returns `404 NOT_FOUND` if missing; returns `409 DELIVERY_NOT_PENDING` if status is not `pending` or if an active unreleased assignment already exists.
   - **Resource Existence**: Fetches vehicle and driver. Returns `404 NOT_FOUND` if either is missing.
   - **Resource Availability**: Evaluates vehicle (`status == 'available'` and no unreleased assignment) and driver (`availability_status == 'available'` and no unreleased assignment).
   - **Combined Resource Conflict**: If **both** vehicle and driver are unavailable/occupied, returns `409 RESOURCES_UNAVAILABLE` with a message explicitly detailing both reasons.
   - **Single Resource Conflict**: If only the vehicle is unavailable/occupied, returns `409 VEHICLE_UNAVAILABLE`. If only the driver is unavailable/occupied, returns `409 DRIVER_UNAVAILABLE`.
   - **Capacity Check**: If `delivery.required_capacity` is specified, asserts `vehicle.capacity >= delivery.required_capacity`. If violated, returns `409 CAPACITY_MISMATCH`.
3. **Atomic Commit & Audit**:
   - Inserts record into `assignments`.
   - Updates `vehicles.status = 'assigned'`.
   - Updates `drivers.availability_status = 'assigned'`.
   - Updates `deliveries.status = 'assigned'`.
   - Writes structured JSON snapshot entry to `audit_log`.
   - Commits transaction atomically. On any error or exception, the transaction rolls back completely with zero partial mutations.

### Status Transition Lifecycle (`PATCH /deliveries/{id}/status`)
- Allowed transitions:
  - `assigned -> in_transit`
  - `in_transit -> delivered`
  - `pending -> cancelled`
  - `assigned -> cancelled`
- All other transitions (including `pending -> delivered` or `in_transit -> cancelled`) are rejected with `409 INVALID_TRANSITION`.
- On transition to `delivered` or `cancelled`, the active assignment is marked with `released_at = utc_now_iso()`, `release_reason = new_status`, and the linked vehicle and driver are atomically restored to `available`.

### Manual Status Guards
- `PATCH /vehicles/{id}/status`: Requests to change vehicle status to `maintenance` or `inactive` are rejected with `409 VEHICLE_UNAVAILABLE` if the vehicle has an active assignment (`released_at IS NULL`).
- `PATCH /drivers/{id}/status`: Requests to change driver availability to `unavailable` are rejected with `409 DRIVER_UNAVAILABLE` if the driver has an active assignment (`released_at IS NULL`).

---

## 4. Methods and Decisions

| Decision Area | Chosen Approach | Alternatives Considered | Rationale |
|---|---|---|---|
| **Backend Framework** | FastAPI (Python 3.12) | Flask, Django, Node/Express | Automatic OpenAPI contracts, native Pydantic v2 validation, high throughput with ASGI/Uvicorn, zero compilation. |
| **Database Engine** | SQLite (WAL mode, Foreign Keys ON) | PostgreSQL, MySQL, In-memory Dict | Single-file zero-setup persistence, ACID guarantees with `BEGIN IMMEDIATE`, WAL mode allows concurrent readers during writes. |
| **Concurrency Guard** | DB `BEGIN IMMEDIATE` + Partial Unique Indexes | In-memory Mutex / Redis Lock | In-memory locks fail across processes/restarts. SQLite partial unique indexes enforce single-active invariants at the database storage engine level. |
| **Frontend Stack** | Static HTML5 + Hand-written CSS + Vanilla ES Modules | React / Next.js / Tailwind build pipeline | Zero build step (`npm run build` not required at demo time), zero CDN dependence, instant startup, vendored local Lucide SVG icons. |
| **Design System** | `ui-ux-pro-max` (HUD / Control Room, Density 8, Motion 3) | Generic Bootstrap / Tailwind presets | Built specifically for command-center logistics telemetry. High contrast (≥4.5:1), tabular numerals, no emoji icons. |
| **Import Strategy** | 2-Phase: Dry-run preview table -> All-or-Nothing Atomic Commit | Direct upload with partial row skipping | Partial imports leave database in unpredictable states; dry-run preview with per-row badges allows operators to fix errors before committing. |

---

## 5. Results & Test Evidence
All test results below are executed and directly sourced from `evidence/test_results.json` (**30 / 30 tests passing, 100% pass rate**).

> **Historical Test Count Reconciliation:**
> - *Initial Sprint Baseline:* 25 tests (T1–T12, AUDIT-1, 3, 4, 5, 6, 7, 8, 9, PHASE-B1, B2, B4, B5, B6).
> - *Sprint Hardening:* Added `AUDIT-10` (Idempotency-Key replay caching and `If-Match` stale-state protection), bringing total to 26 tests.
> - *Comprehensive Security & Route Audit:* Added `AUDIT-11` (Unified HTTP error envelopes across Starlette 404, 405, and 400 validation, plus strict route vs resource 404 separation), bringing total to 27 tests.
> - *Physical GPS & Telematics Sprint:* Added `TRK-1` (Driver Phone Validation & Modification), `TRK-2` (Session Lifecycle & Real GPS Ingestion with Assignment Linking), and `TRK-3` (Coordinate Boundaries & Offline Telemetry States), bringing total to **30 distinct tests executed and passing**.

| Test ID | Test Name | Input | Expected | Observed | Status | Evidence Path |
|---|---|---|---|---|---|---|
| **T1** | Valid Assignment | Delivery `D-001`, Vehicle `V-001`, Driver `DR-001` | Status `201`, Vehicle/Driver/Delivery set to `assigned` | Status `201`, Vehicle/Driver/Delivery set to `assigned` | **PASS** | `evidence/t1_valid_assignment.json` |
| **T2** | Vehicle Conflict (Occupied) | Delivery `D-002`, Vehicle `V-001` (active on `D-001`), Driver `DR-002` | Status `409`, `VEHICLE_UNAVAILABLE`, DB unchanged | Status `409`, `VEHICLE_UNAVAILABLE`, DB unchanged (`true`) | **PASS** | `evidence/t2_vehicle_conflict.json` |
| **T3** | Driver Conflict (Occupied) | Delivery `D-002`, Vehicle `V-002`, Driver `DR-001` (active on `D-001`) | Status `409`, `DRIVER_UNAVAILABLE`, DB unchanged | Status `409`, `DRIVER_UNAVAILABLE`, DB unchanged (`true`) | **PASS** | `evidence/t3_driver_conflict.json` |
| **T4** | Both Resources Occupied | Delivery `D-002`, Vehicle `V-001`, Driver `DR-001` | Status `409`, `RESOURCES_UNAVAILABLE`, DB unchanged | Status `409`, `RESOURCES_UNAVAILABLE`, DB unchanged (`true`) | **PASS** | `evidence/t4_both_occupied.json` |
| **T5** | Unavailable Driver | Delivery `D-001`, Driver status `unavailable` | Status `409`, `DRIVER_UNAVAILABLE`, DB unchanged | Status `409`, `DRIVER_UNAVAILABLE`, DB unchanged (`true`) | **PASS** | `evidence/t5_unavailable_driver.json` |
| **T6** | Maintenance Vehicle | Delivery `D-001`, Vehicle status `maintenance` | Status `409`, `VEHICLE_UNAVAILABLE`, DB unchanged | Status `409`, `VEHICLE_UNAVAILABLE`, DB unchanged (`true`) | **PASS** | `evidence/t6_maintenance_vehicle.json` |
| **T7** | Unknown IDs Validation | Delivery `D-999`, Vehicle `V-999`, Driver `DR-999` | Status `404`, `NOT_FOUND`, DB unchanged | Status `404` for all, `NOT_FOUND`, DB unchanged (`true`) | **PASS** | `evidence/t7_unknown_ids.json` |
| **T8** | Complete Delivery Releases Resources | Delivery `D-001` transitioned `assigned -> in_transit -> delivered` | Status `200`, Resources `available`, immediate re-assignment returns `201` | Status `200`, Resources `available`, re-assignment returned `201` | **PASS** | `evidence/t8_complete_delivery_releases.json` |
| **T9** | Cancel Releases Resources | Delivery `D-001` transitioned `assigned -> cancelled` | Status `200`, Resources restored to `available` | Status `200`, Vehicle & Driver restored to `available` | **PASS** | `evidence/t9_cancel_releases.json` |
| **T10** | Invalid Transition | Delivery `D-001` illegal transition `pending -> delivered` | Status `409`, `INVALID_TRANSITION`, DB unchanged | Status `409`, `INVALID_TRANSITION`, DB unchanged (`true`) | **PASS** | `evidence/t10_invalid_transition.json` |
| **T11** | Duplicate / Rapid Double Submit | 2 consecutive identical `/assign` calls on `D-001` | 1st call `201`, 2nd call `409 DELIVERY_NOT_PENDING`, active assignments = 1 | 1st call `201`, 2nd call `409 DELIVERY_NOT_PENDING`, active assignments = 1 | **PASS** | `evidence/t11_duplicate_submit.json` |
| **T12** | Real Concurrency Stress (50 Threads) | 50 parallel threads competing for 1 vehicle & 1 driver via `ThreadPoolExecutor` | Exactly 1 `201`, 49 `409`, zero `5xx` / db locks, active assignments = 1 | Exactly 1 `201`, 49 `409`, zero `5xx` / db locks, active assignments = 1 | **PASS** | `evidence/t12_real_concurrency.json` |
| **AUDIT-1** | Clean Start & Health | `/health` check with empty DB | Status `200`, `journal_mode=wal`, `foreign_keys=true`, counts=0 | Status `200`, WAL mode, foreign keys active, 0 counts | **PASS** | `evidence/audit_1_clean_start.json` |
| **AUDIT-3** | State Bypass Rejected | Direct patch of vehicle/driver/delivery to `assigned`/`in_transit` | Status `400`/`409`, state bypass rejected | Status `400`/`409`, all bypass attempts blocked | **PASS** | `evidence/audit_3_state_bypass.json` |
| **AUDIT-4** | Exhaustive 5x5 Transition Matrix | All 25 source/target delivery status pairs tested | Exactly 5 allowed transitions pass; 20 invalid pairs return `409 INVALID_TRANSITION` | 5 passed, 20 rejected with 409, DB untouched | **PASS** | `evidence/audit_4_matrix.json` |
| **AUDIT-5** | Validation & Normalization | Pydantic validation mapping to 400 `VALIDATION_ERROR`, registration normalization | 422 mapped to 400, registration uppercase trimmed, phone validated | 422 mapped to 400 `VALIDATION_ERROR`, reg normalized | **PASS** | `evidence/audit_5_validation.json` |
| **AUDIT-6** | Frontend XSS Inert Sanitization | Imported row with `<script>` and `<img onerror>` payload | Stored verbatim in DB, rendered inert via `escapeHtml` / `textContent` | Rendered inert with zero script execution | **PASS** | `evidence/audit_6_xss_inert.json` |
| **AUDIT-7** | Export CSV Formula Safety | Export cells starting with `=`, `+`, `-`, `@`, `\t`, `\r` | Prefixed with single quote `'` to neutralize spreadsheet formulas | All formula characters safely escaped with `'` | **PASS** | `evidence/audit_7_export_safety.json` |
| **AUDIT-8** | Upload Limits & Malformed Files | 5 MB upload limit, 5000 rows limit, binary null-byte sniffing | Rejected with 400 `VALIDATION_ERROR`, clear human-readable message | 400 `VALIDATION_ERROR`, oversized/binary files blocked | **PASS** | `evidence/audit_8_upload_limits.json` |
| **AUDIT-9** | Security Hardening Headers | `GET /` response headers inspection | `Content-Security-Policy`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy` | All 4 security headers present on every response | **PASS** | `evidence/audit_9_security_headers.json` |
| **AUDIT-10**| Idempotency & Version Stale State | Replay with same `Idempotency-Key`; `If-Match` version conflict | Same key returns cached response without 2nd insert; version mismatch returns `409 STALE_STATE` | Zero duplicate assignments, `409 STALE_STATE` verified | **PASS** | `evidence/audit_10_idempotency.json` |
| **AUDIT-11**| HTTP Error Envelopes & Route Separation | Unknown route (404), Method not allowed (405), Nonexistent entity (404) | All return unified `{"error", "message"}` envelope; API 404 does not return SPA HTML 200 | Strict `{"error", "message"}` envelope observed on all non-2xx responses | **PASS** | `evidence/audit_11_http_errors.json` |
| **PHASE-B1**| Smart Advisor & Auto-Assign | Recommendations endpoint & auto-assign planner | Top capacity fit vehicle & fair driver scored highest; auto-assign creates valid plan | Smallest sufficient capacity chosen, batch committed | **PASS** | `evidence/phase_b_advisor.json` |
| **PHASE-B2**| Blocked Queue Radar | Pending delivery with `required_capacity` exceeding fleet max | Listed in `/deliveries/blocked` with specific cause ("Insufficient capacity") | Correctly diagnosed with clear blockage reason | **PASS** | `evidence/phase_b_blocked.json` |
| **PHASE-B4**| Parallel Allocation Race Lab | Diagnostic concurrency proof endpoint with 25 parallel threads | Exactly 1 winner (`201`), 24 blocked (`409`), 0 errors (`5xx`), invariant preserved | 1 winner, 24 conflicts, 0 errors, invariant verified | **PASS** | `evidence/phase_b_racelab.json` |
| **PHASE-B5**| Role-Based Access Control | Cookie-based session auth with scrypt hashing | Dispatcher, fleet manager, and ops lead permissions enforced | Valid authentication, role permissions verified | **PASS** | `evidence/phase_b_auth.json` |
| **PHASE-B6**| Analytics & Route Radar | Summary metrics & route coordinate vectors | On-time rate, status funnel, driver workload, active routes | SVG charts and route vectors computed cleanly | **PASS** | `evidence/phase_b_analytics.json` |
| **TRK-1** | Driver Phone Update & Validation | Phone PATCH endpoint with international regex check | Valid formats update phone + audit log; invalid formats return 400 | Phone format validated, audit snapshot recorded | **PASS** | `evidence/trk_1_phone_update.json` |
| **TRK-2** | Tracking Session Lifecycle & GPS Stream | Start session, ingest coordinates, query vehicle/delivery latest, stop session | Ingestion succeeds, latest coordinates linked across vehicle/delivery/driver, Street View generated | Complete lifecycle & link verified, Street View active | **PASS** | `evidence/trk_2_lifecycle.json` |
| **TRK-3** | GPS Boundaries & Empty States | Out-of-bounds lat/lng/accuracy, offline vehicle state | Bad coordinates return 400 `VALIDATION_ERROR`; unassigned vehicle returns offline | Boundary guards verified, offline state verified | **PASS** | `evidence/trk_3_boundaries.json` |

---

## 6. Team Work

### Engineering Team & Role Ownership
| Member | Role | Key Contributions |
|---|---|---|
| **Sheshman Ahir** | **Team Leader** — Backend Development & Assignment Logic | Designed atomic assignment transaction flow using SQLite `BEGIN IMMEDIATE`; implemented partial unique indexes (`idx_assignments_active_vehicle`, `idx_assignments_active_driver`, `idx_assignments_active_delivery`) guaranteeing DB-level mutual exclusion; engineered status transition state machine, idempotency caching, and smart advisor allocation algorithm. |
| **Sandip Sah** | Frontend Development & UI/UX Design | Engineered dark HUD / Control Room UI adhering to `ui-ux-pro-max` design system with CSS custom properties (`tokens.css`); created 4-lane Kanban dispatch board, assignment modal, telemetry status badges, Race Lab diagnostic console, and analytics route radar; vendored Lucide SVG icons locally (zero CDN dependencies); ensured 375px–1440px responsiveness. |
| **Rabi Kumar Gupta** | Cybersecurity, Import Validation, Testing & Evidence | Engineered 2-phase CSV/JSON import pipeline with dry-run schema validation; implemented CSV formula injection protection (`'`, `=`, `+`, `-`, `@`); added HTTP security headers (CSP, X-Content-Type-Options, X-Frame-Options, Referrer-Policy); built and executed the 26-test Pytest test suite, 50-thread concurrency race stress tests, and automated browser evidence capture. |

- **Planned vs. Actual Timeline**:
  - *Planned:* 2h 30m core implementation + 30m evaluation reporting.
  - *Actual:* Completed in 2h 25m with 100% test pass rate (26/26) and 22 forensic screenshots captured.
- **Dead Ends Encountered**:
  - *In-memory synchronization / application locks*: Explored in-memory mutexes for race prevention, but rejected in favor of SQLite WAL mode + `BEGIN IMMEDIATE` transaction serialization combined with partial unique indexes. In-memory locks fail across multiple Uvicorn workers and process restarts, whereas database-level unique constraints provide unbreachable conflict-free guarantees.

---

## 7. Limitations and Next Steps
1. **Multi-Stop Route Optimization**: Current assignment model handles point-to-point pickups and dropoffs. Future iterations could integrate TSP routing algorithms for multi-stop delivery batches.
2. **Geo-Fencing & GPS Telemetry**: Real-time vehicle positions could be streamed via WebSockets or Server-Sent Events (SSE) to render live map markers.
3. **Driver Shift Hours Tracking**: Adding HOS (Hours of Service) limits to prevent dispatching drivers approaching statutory driving duration caps.

---

## 8. How to Run

### 1. Start Server
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
Visit `http://127.0.0.1:8000`.

### 2. Run Test Suite
```bash
pytest -v
```

### 3. Re-run Browser UI Judge Flow & Screenshot Capture
```bash
python scripts/run_browser_judge_flow.py
```
Outputs screenshots into `evidence/screenshots/`.

