# FleetWise — Video vs. Evidence Discrepancy & Unverified Audit Log

**Scope:** Mismatches, unverified items, and illegible items identified between the attached video recording (`stock-footage-cctv-parking-area-with-cars-and-people-timelapse.webm`) and the project ground truth evidence.

---

## 1. File & Content Mismatches

| Timestamp | Expected Subject | Observed Video Content | Severity / Impact |
|---|---|---|---|
| `00:00 - 00:14` | Screen-recording video of the finished FleetWise application demonstrating user imports, dashboard lanes, atomic dispatch, resource conflicts, and lifecycle transitions. | Stock surveillance footage (`stock-footage-cctv-parking-area-with-cars-and-people-timelapse.webm`) showing an outdoor parking lot in the rain with parked cars and a `"shutterstock"` watermark. Zero application screens, browsers, or UI controls are displayed. | **CRITICAL FILE MISMATCH**: The attached video file is an external CCTV stock video clip, not a recording of the FleetWise application. |

---

## 2. Unverified Test & Feature Behaviors (Not in Video)

The following items are fully verified in automated test suites (`evidence\test_results.json`) and browser screenshots (`evidence\screenshots_v2\`), but could **not** be verified from the attached video recording because the application was not depicted:

| Item / Test ID | Feature Description | Status in Video | Reason Unverified |
|---|---|---|---|
| **T1** | Valid Atomic Assignment (`POST /deliveries/D-001/assign`) | `NOT IN VIDEO` | Video shows CCTV parking lot, not FleetWise dispatch screen. |
| **T2** | Vehicle Conflict Guard (Re-assigning occupied vehicle returns 409) | `NOT IN VIDEO` | Application UI not shown. |
| **T3** | Driver Conflict Guard (Re-assigning occupied driver returns 409) | `NOT IN VIDEO` | Application UI not shown. |
| **T4** | Combined Resource Conflict (`RESOURCES_UNAVAILABLE` 409) | `NOT IN VIDEO` | Application UI not shown. |
| **T5** | Unavailable Driver Guard (Re-assigning unavailable driver returns 409) | `NOT IN VIDEO` | Application UI not shown. |
| **T6** | Maintenance Vehicle Guard (Re-assigning maintenance vehicle returns 409) | `NOT IN VIDEO` | Application UI not shown. |
| **T7** | Unknown Entity IDs Return 404 (`NOT_FOUND`) | `NOT IN VIDEO` | Application UI not shown. |
| **T8** | Complete Delivery Atomically Releases Resources | `NOT IN VIDEO` | Application UI not shown. |
| **T9** | Cancel Delivery Atomically Releases Resources | `NOT IN VIDEO` | Application UI not shown. |
| **T10** | Invalid Delivery Lifecycle Transition Rejected with 409 | `NOT IN VIDEO` | Application UI not shown. |
| **T11** | Duplicate / Rapid Double Submit Returns 409 `DELIVERY_NOT_PENDING` | `NOT IN VIDEO` | Application UI not shown. |
| **T12** | 50-Thread Parallel Concurrency Stress Test | `NOT IN VIDEO` | Application UI not shown. |
| **Import Pipeline** | CSV/JSON Drag-and-Drop, Dry-run preview, atomic commit | `NOT IN VIDEO` | Application UI not shown. |
| **Dashboard** | Bento KPIs, Utilisation ring, 4-lane live board | `NOT IN VIDEO` | Application UI not shown. |
| **Advisor** | Smart Dispatch Advisor ranking breakdown & auto-assign | `NOT IN VIDEO` | Application UI not shown. |
| **Blocked Queue** | Blocked Queue Diagnostics modal & capacity mismatch alerts | `NOT IN VIDEO` | Application UI not shown. |
| **Race Lab** | Interactive parallel concurrency diagnostic UI | `NOT IN VIDEO` | Application UI not shown. |
| **Analytics & Routes**| On-time rate, status funnel, driver workload, route radar | `NOT IN VIDEO` | Application UI not shown. |
| **Audit Trail** | Chronological immutable audit log table | `NOT IN VIDEO` | Application UI not shown. |

---

## 3. Illegible Visual Elements in Video

| Timestamp | Element | Observed State | Cause |
|---|---|---|---|
| `00:00 - 00:14` | License Plates of Parked Cars | `ILLEGIBLE` | Rain, high-angle camera distance, video compression, scanline filter, and low resolution (`596x336`). |
| `00:00 - 00:14` | Upper-right timestamp header prefix | `ILLEGIBLE` | Prefix characters preceding `00:10:XX` are clipped at the upper border. |

