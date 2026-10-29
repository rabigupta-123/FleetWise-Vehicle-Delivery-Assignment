# FleetWise — Video Evidence Extraction & Forensic Audit Report

**Auditor:** Evidence Auditor (Independent Automated Inspection)  
**Workspace:** `C:\Users\rabig\Downloads\it raale @13`  
**Video File Analyzed:** `C:\Users\rabig\.gemini\antigravity\brain\433e0138-ba1f-460f-9be9-08d7598222ef\.user_uploaded\media_1793281762635_88d80d25.webm`  
**Original Upload Name:** `stock-footage-cctv-parking-area-with-cars-and-people-timelapse.webm`  
**Analysis Method:** Extracted 1 frame per second using Microsoft Edge Playwright browser automation into `evidence\video_frames\frame_000s.png` through `frame_015s.png`.  
**Duration:** `00:14.35` (14.35 seconds, 16 extracted frames)  
**Resolution:** `596 x 336` pixels  
**Video Content Summary:** The attached video file is a 14-second stock surveillance video clip (watermarked `"shutterstock"`) showing an outdoor parking lot in the rain with parked cars viewed from an elevated CCTV angle. **The FleetWise application interface, web pages, buttons, forms, tables, and workflows are completely absent from this video recording.**

---

## 1. Timeline of Actions & Visual Changes

| Timestamp (mm:ss) | Screen / Scene | Action Observed | Visual Details / On-Screen Text |
|---|---|---|---|
| `00:00` | CCTV Outdoor Parking Lot | Video playback start | Static CCTV camera view of parked cars in rain. Scanlines active. Translucent centered watermark: `shutterstock`. Upper-right timestamp overlay reads `00:10:00`. FleetWise app: **NOT SHOWN**. |
| `00:01` | CCTV Outdoor Parking Lot | Continuous stream | Static cars in wet parking stalls. Upper-right timestamp counter advances to `00:10:01`. FleetWise app: **NOT SHOWN**. |
| `00:02` | CCTV Outdoor Parking Lot | Continuous stream | Static cars in wet parking stalls. Upper-right timestamp counter advances to `00:10:02`. FleetWise app: **NOT SHOWN**. |
| `00:03` | CCTV Outdoor Parking Lot | Continuous stream | Static cars in wet parking stalls. Upper-right timestamp counter advances to `00:10:03`. FleetWise app: **NOT SHOWN**. |
| `00:04` | CCTV Outdoor Parking Lot | Continuous stream | Static cars in wet parking stalls. Upper-right timestamp counter advances to `00:10:04`. FleetWise app: **NOT SHOWN**. |
| `00:05` | CCTV Outdoor Parking Lot | Continuous stream | Static cars in wet parking stalls. Upper-right timestamp counter advances to `00:10:05`. FleetWise app: **NOT SHOWN**. |
| `00:06` | CCTV Outdoor Parking Lot | Continuous stream | Static cars in wet parking stalls. Upper-right timestamp counter advances to `00:10:06`. FleetWise app: **NOT SHOWN**. |
| `00:07` | CCTV Outdoor Parking Lot | Continuous stream | Static cars in wet parking stalls. Upper-right timestamp counter advances to `00:10:07`. FleetWise app: **NOT SHOWN**. |
| `00:08` | CCTV Outdoor Parking Lot | Continuous stream | Static cars in wet parking stalls. Upper-right timestamp counter advances to `00:10:08`. FleetWise app: **NOT SHOWN**. |
| `00:09` | CCTV Outdoor Parking Lot | Continuous stream | Static cars in wet parking stalls. Upper-right timestamp counter advances to `00:10:09`. FleetWise app: **NOT SHOWN**. |
| `00:10` | CCTV Outdoor Parking Lot | Continuous stream | Static cars in wet parking stalls. Upper-right timestamp counter advances to `00:10:10`. FleetWise app: **NOT SHOWN**. |
| `00:11` | CCTV Outdoor Parking Lot | Continuous stream | Static cars in wet parking stalls. Upper-right timestamp counter advances to `00:10:11`. FleetWise app: **NOT SHOWN**. |
| `00:12` | CCTV Outdoor Parking Lot | Continuous stream | Static cars in wet parking stalls. Upper-right timestamp counter advances to `00:10:12`. FleetWise app: **NOT SHOWN**. |
| `00:13` | CCTV Outdoor Parking Lot | Continuous stream | Static cars in wet parking stalls. Upper-right timestamp counter advances to `00:10:13`. FleetWise app: **NOT SHOWN**. |
| `00:14` | CCTV Outdoor Parking Lot | Stream reaches end | Static cars in wet parking stalls. Upper-right timestamp counter advances to `00:10:14`. Playback terminates at 14.35s. FleetWise app: **NOT SHOWN**. |

---

## 2. Extracted Data Points (Exact Values with Timestamps)

### A. Import Pipeline
- **File names**: `NOT SHOWN`
- **Entity**: `NOT SHOWN`
- **Dry-run preview rows**: `NOT SHOWN`
- **Per-row error badges**: `NOT SHOWN`
- **Commit summary counts**: `NOT SHOWN`

### B. Vehicles
- **vehicle_id, registration_no, type, capacity, status**: `NOT SHOWN`  
  *(Physical automobiles are visible in the parking lot footage, but no software entities, registration text, database records, or statuses appear).*

### C. Drivers
- **driver_id, name, phone, availability_status**: `NOT SHOWN`

### D. Deliveries
- **delivery_id, pickup, dropoff, scheduled_time, priority, required_capacity, status**: `NOT SHOWN`

### E. Judge Flow Steps
1. **Successful assignment**: `NOT SHOWN`
2. **Vehicle reuse attempt (409)**: `NOT SHOWN`
3. **Driver reuse attempt (409)**: `NOT SHOWN`
4. **Complete first delivery (lifecycle transition)**: `NOT SHOWN`
5. **Resources available again**: `NOT SHOWN`

### F. Dashboard Telemetry
- **Available fleet**: `NOT SHOWN`
- **Active deliveries**: `NOT SHOWN`
- **Delivered count**: `NOT SHOWN`
- **Utilisation %**: `NOT SHOWN`

### G. Advanced Screens
- **Smart Dispatch Advisor ranking**: `NOT SHOWN`
- **Blocked queue diagnostics**: `NOT SHOWN`
- **SLA countdown / risk flags**: `NOT SHOWN`
- **Race Lab parallel diagnostic**: `NOT SHOWN`
- **Analytics numbers / SVG charts**: `NOT SHOWN`
- **Audit log rows**: `NOT SHOWN`
- **Role / login screens**: `NOT SHOWN`
- **Connection-status indicator**: `NOT SHOWN`

### H. Visual Quality & Accessibility
- **Horizontal overflow**: `NOT SHOWN` (No web browser DOM rendered)
- **Focus rings during keyboard navigation**: `NOT SHOWN`
- **Clipped text**: `NOT SHOWN`
- **Verbatim visible video text**:
  - Center: `shutterstock`
  - Top-right corner: `00:10:00` (at `00:00`) through `00:10:14` (at `00:14`)

---

## 3. Cross-Check Against Ground Truth

Ground truth comparison sources:
1. `evidence\test_results.json` (Automated pytest test results)
2. `evidence\t*.json` (Individual test evidence logs)
3. `REPORT.md` (Engineering specification & results)

| Test / Item | Video Displayed Value | Ground Truth (API / DB / Test Log) | Recomputed Value (Formula Spec) | Crosscheck Result | Video Timestamp |
|---|---|---|---|---|---|
| **T1: Valid Assignment** | `NOT SHOWN` | Status `201`, `assignments` insert, vehicle `assigned`, driver `assigned` | Status `201`, active assignments = 1 | **NOT IN VIDEO** | N/A |
| **T2: Vehicle Conflict** | `NOT SHOWN` | Status `409`, `VEHICLE_UNAVAILABLE`, DB unchanged (`true`) | Status `409`, DB unchanged (`true`) | **NOT IN VIDEO** | N/A |
| **T3: Driver Conflict** | `NOT SHOWN` | Status `409`, `DRIVER_UNAVAILABLE`, DB unchanged (`true`) | Status `409`, DB unchanged (`true`) | **NOT IN VIDEO** | N/A |
| **T4: Both Resources Occupied** | `NOT SHOWN` | Status `409`, `RESOURCES_UNAVAILABLE`, DB unchanged (`true`) | Status `409`, DB unchanged (`true`) | **NOT IN VIDEO** | N/A |
| **T5: Unavailable Driver** | `NOT SHOWN` | Status `409`, `DRIVER_UNAVAILABLE`, DB unchanged (`true`) | Status `409`, DB unchanged (`true`) | **NOT IN VIDEO** | N/A |
| **T6: Maintenance Vehicle** | `NOT SHOWN` | Status `409`, `VEHICLE_UNAVAILABLE`, DB unchanged (`true`) | Status `409`, DB unchanged (`true`) | **NOT IN VIDEO** | N/A |
| **T7: Unknown IDs Validation** | `NOT SHOWN` | Status `404`, `NOT_FOUND` on unknown entity IDs, DB unchanged | Status `404`, DB unchanged (`true`) | **NOT IN VIDEO** | N/A |
| **T8: Complete Delivery Releases**| `NOT SHOWN` | Status `200`, assignment `released_at` set, vehicle/driver `available` | Status `200`, resources re-assignable (`201`) | **NOT IN VIDEO** | N/A |
| **T9: Cancel Releases Resources** | `NOT SHOWN` | Status `200`, assignment `released_at` set, vehicle/driver `available` | Status `200`, resources available | **NOT IN VIDEO** | N/A |
| **T10: Invalid Transition** | `NOT SHOWN` | Status `409`, `INVALID_TRANSITION`, DB unchanged (`true`) | Status `409`, DB unchanged (`true`) | **NOT IN VIDEO** | N/A |
| **T11: Duplicate Submit** | `NOT SHOWN` | Call 1: `201`, Call 2: `409 DELIVERY_NOT_PENDING`, active asgs = 1 | Exactly 1 active assignment created | **NOT IN VIDEO** | N/A |
| **T12: Real Concurrency (50 Th)** | `NOT SHOWN` | 50 threads: 1 `201`, 49 `409`, 0 `5xx`, active assignments = 1 | `success=1`, `conflicts=49`, `errors=0` | **NOT IN VIDEO** | N/A |
| **available_fleet** | `NOT SHOWN` | `COUNT(vehicles WHERE status='available')` | `COUNT(vehicles WHERE status='available')` | **NOT IN VIDEO** | N/A |
| **active_deliveries** | `NOT SHOWN` | `COUNT(deliveries WHERE status IN ('assigned','in_transit'))` | `COUNT(deliveries WHERE status IN ('assigned','in_transit'))` | **NOT IN VIDEO** | N/A |
| **delivered_count** | `NOT SHOWN` | `COUNT(deliveries WHERE status='delivered')` | `COUNT(deliveries WHERE status='delivered')` | **NOT IN VIDEO** | N/A |
| **pending_count** | `NOT SHOWN` | `COUNT(deliveries WHERE status='pending')` | `COUNT(deliveries WHERE status='pending')` | **NOT IN VIDEO** | N/A |
| **utilisation_pct** | `NOT SHOWN` | `100 * assigned_vehicles / operational_vehicles` | `100 * assigned_vehicles / operational_vehicles` | **NOT IN VIDEO** | N/A |

---

## 4. Illegible & Unverified Items

| Timestamp | Item Description | Cause / Nature of Illegibility |
|---|---|---|
| `00:00 - 00:14` | Vehicle license plates | The license plate numbers on the physical cars in the parking lot footage cannot be resolved due to camera elevation, rain, video compression, scanline simulation filter, and low resolution (`596x336`). |
| `00:00 - 00:14` | Timestamp prefix | Characters immediately preceding the `00:10:XX` timestamp in the top-right overlay are cropped and partially obscured by the upper frame boundary. |

