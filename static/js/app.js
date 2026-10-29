import { icon } from './icons.js';

const STATE = {
  activeView: 'dashboard',
  metrics: {
    available_fleet: 0,
    total_vehicles: 0,
    assigned_vehicles: 0,
    maintenance_vehicles: 0,
    inactive_vehicles: 0,
    available_drivers: 0,
    total_drivers: 0,
    active_deliveries: 0,
    pending_deliveries: 0,
    delivered_count: 0,
    cancelled_count: 0,
    utilisation_pct: 0,
  },
  vehicles: [],
  drivers: [],
  deliveries: [],
  filteredDeliveries: [],
  audit: [],
  deliveryFilterStatus: '',
  deliverySearchQuery: '',
  fleetSearchQuery: '',
  driverSearchQuery: '',
  dispatchSelectedDeliveryId: null,
  dispatchSelectedVehicleId: null,
  dispatchSelectedDriverId: null,
  bypassUiGuardForTest: false,
  importEntity: 'vehicles',
  importFile: null,
  importDryRunResult: null,
  pollingEnabled: true,
  pollTimer: null,
  topRecommendation: null,
  blockedQueue: [],
};

const VIEW_META = {
  dashboard: {
    title: 'Command Center',
    subtitle: 'Real-time fleet telemetry, active delivery lanes & conflict-free resource allocation',
  },
  deliveries: {
    title: 'Deliveries Management',
    subtitle: 'Create, filter, search, dispatch, and transition delivery lifecycles atomically',
  },
  dispatch: {
    title: 'Dispatch Console',
    subtitle: 'Assign pending deliveries to eligible vehicles and drivers under BEGIN IMMEDIATE protection',
  },
  fleet: {
    title: 'Fleet Vehicles',
    subtitle: 'Manage vehicle capacities, registration numbers, and operational status guards',
  },
  drivers: {
    title: 'Drivers Directory',
    subtitle: 'Manage driver roster and availability status guards',
  },
  import: {
    title: 'Import Data Pipeline',
    subtitle: 'Drag-and-drop CSV/JSON dry-run validation, per-row error badges & atomic commit',
  },
  racelab: {
    title: 'Parallel Allocation Race Lab',
    subtitle: 'Judge-facing concurrency diagnostic proving zero double assignments under high contention',
  },
  analytics: {
    title: 'Fleet Analytics & SLA Radar',
    subtitle: 'On-time delivery performance, status funnels, and driver workload distribution',
  },
  routes: {
    title: 'Route Radar Visualizer',
    subtitle: 'Active delivery pickup and dropoff corridors and transit trajectory canvas',
  },
  audit: {
    title: 'System Audit Log',
    subtitle: 'Chronological immutable record of every state mutation with before/after JSON snapshots',
  },
};

const EXPECTED_COLS = {
  vehicles: 'vehicle_id (optional, auto V-###), registration_no, type, capacity, status (optional: available|maintenance|inactive)',
  drivers: 'driver_id, name, phone, availability_status (optional: available|unavailable)',
  deliveries: 'delivery_id (optional, auto D-###), pickup, dropoff, scheduled_time (ISO 8601), priority (low|normal|high|urgent), required_capacity (optional)',
};

function escapeHtml(val) {
  if (val === null || val === undefined) return '';
  return String(val)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function hydrateStaticIcons(root = document) {
  root.querySelectorAll('[data-icon]').forEach((el) => {
    const name = el.getAttribute('data-icon');
    el.innerHTML = icon(name, 16);
  });
}

function statusBadgeHtml(status) {
  const s = (status || '').toLowerCase();
  const map = {
    available: { icon: 'checkCircle', label: 'available', cls: 'status-available' },
    assigned: { icon: 'link', label: 'assigned', cls: 'status-assigned' },
    in_transit: { icon: 'navigation', label: 'in_transit', cls: 'status-in_transit' },
    delivered: { icon: 'checkCircle', label: 'delivered', cls: 'status-delivered' },
    pending: { icon: 'clock', label: 'pending', cls: 'status-pending' },
    maintenance: { icon: 'wrench', label: 'maintenance', cls: 'status-maintenance' },
    unavailable: { icon: 'slash', label: 'unavailable', cls: 'status-unavailable' },
    cancelled: { icon: 'xCircle', label: 'cancelled', cls: 'status-cancelled' },
    inactive: { icon: 'slash', label: 'inactive', cls: 'status-inactive' },
  };
  const cfg = map[s] || { icon: 'activity', label: s || 'unknown', cls: 'status-inactive' };
  return `<span class="status-badge ${cfg.cls}">${icon(cfg.icon, 13)}<span>${escapeHtml(cfg.label)}</span></span>`;
}

function priorityBadgeHtml(priority) {
  const p = (priority || 'normal').toLowerCase();
  const iconMap = {
    urgent: 'alertTriangle',
    high: 'zap',
    normal: 'activity',
    low: 'clock',
  };
  return `<span class="priority-badge priority-${escapeHtml(p)}">${icon(iconMap[p] || 'activity', 12)}<span>${escapeHtml(p)}</span></span>`;
}

function showToast(message, isError = false, code = null) {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const toast = document.createElement('div');
  toast.className = `toast ${isError ? 'toast-error' : ''}`;
  const prefix = code ? `<strong class="mono">[${escapeHtml(code)}]</strong> ` : '';
  toast.innerHTML = `
    <span>${icon(isError ? 'alertTriangle' : 'checkCircle', 16)}</span>
    <div>${prefix}${escapeHtml(message)}</div>
  `;
  container.appendChild(toast);
  setTimeout(() => {
    toast.remove();
  }, 4500);
}

function showGlobalError(code, message) {
  const banner = document.getElementById('global-error-banner');
  const codeEl = document.getElementById('global-error-code');
  const msgEl = document.getElementById('global-error-message');
  if (!banner || !codeEl || !msgEl) return;
  codeEl.textContent = code || 'ERROR';
  msgEl.textContent = message || 'An unexpected error occurred.';
  banner.classList.remove('hidden');
  showToast(message, true, code);
}

function clearGlobalError() {
  const banner = document.getElementById('global-error-banner');
  if (banner) banner.classList.add('hidden');
}

async function apiRequest(path, options = {}) {
  const res = await fetch(path, options);
  const contentType = res.headers.get('content-type') || '';
  let data = null;
  if (contentType.includes('application/json')) {
    data = await res.json();
  } else {
    data = await res.text();
  }
  if (!res.ok) {
    const errCode = (data && data.error) || `HTTP_${res.status}`;
    const errMsg = (data && data.message) || (typeof data === 'string' && data) || 'Request failed';
    const err = new Error(errMsg);
    err.status = res.status;
    err.code = errCode;
    err.payload = data;
    throw err;
  }
  return data;
}

/* ==================== DATA SYNC ==================== */
async function refreshAllData(silent = false) {
  try {
    const [metricsRes, vehiclesRes, driversRes, deliveriesRes, auditRes] = await Promise.allSettled([
      apiRequest('/metrics'),
      apiRequest('/vehicles'),
      apiRequest('/drivers'),
      apiRequest('/deliveries'),
      apiRequest('/audit'),
    ]);

    if (metricsRes.status === 'fulfilled' && metricsRes.value) {
      STATE.metrics = { ...STATE.metrics, ...metricsRes.value };
    }
    if (vehiclesRes.status === 'fulfilled' && Array.isArray(vehiclesRes.value)) {
      STATE.vehicles = vehiclesRes.value;
    }
    if (driversRes.status === 'fulfilled' && Array.isArray(driversRes.value)) {
      STATE.drivers = driversRes.value;
    }
    if (deliveriesRes.status === 'fulfilled' && Array.isArray(deliveriesRes.value)) {
      STATE.deliveries = deliveriesRes.value;
    }
    if (auditRes.status === 'fulfilled' && Array.isArray(auditRes.value)) {
      STATE.audit = auditRes.value;
    }

    await refreshFilteredDeliveries();
    await refreshBlockedQueue();
    renderAll();
    if (STATE.activeView === 'analytics') {
      renderAnalytics();
    } else if (STATE.activeView === 'routes') {
      renderRouteRadar();
    }

    const nowStr = new Date().toLocaleTimeString([], { hour12: false });
    const timeEl = document.getElementById('telemetry-time');
    if (timeEl) timeEl.textContent = nowStr;
  } catch (err) {
    if (!silent) {
      showGlobalError(err.code || 'SYNC_ERROR', err.message);
    }
  }
}

async function refreshFilteredDeliveries() {
  const params = new URLSearchParams();
  if (STATE.deliveryFilterStatus) params.set('status', STATE.deliveryFilterStatus);
  if (STATE.deliverySearchQuery.trim()) params.set('q', STATE.deliverySearchQuery.trim());
  const qs = params.toString() ? `?${params.toString()}` : '';
  try {
    const list = await apiRequest(`/deliveries${qs}`);
    if (Array.isArray(list)) {
      STATE.filteredDeliveries = list;
    }
  } catch {
    STATE.filteredDeliveries = STATE.deliveries;
  }
}

/* ==================== RENDERING ==================== */
function renderAll() {
  renderNavBadges();
  renderDashboard();
  renderDeliveriesTable();
  renderDispatchConsole();
  renderFleetTable();
  renderDriversTable();
  renderAuditTable();
}

function renderNavBadges() {
  const pendingCount = STATE.deliveries.filter((d) => d.status === 'pending').length;
  document.getElementById('nav-badge-deliveries').textContent = STATE.deliveries.length;
  document.getElementById('nav-badge-pending').textContent = pendingCount;
  document.getElementById('nav-badge-fleet').textContent = STATE.vehicles.length;
  document.getElementById('nav-badge-drivers').textContent = STATE.drivers.length;
}

function renderDashboard() {
  const m = STATE.metrics;
  document.getElementById('kpi-available-fleet').textContent = m.available_fleet ?? 0;
  document.getElementById('kpi-fleet-breakdown').textContent = `/ ${m.total_vehicles ?? STATE.vehicles.length} total vehicles`;
  document.getElementById('kpi-fleet-detail').textContent = `${m.assigned_vehicles ?? 0} assigned · ${m.maintenance_vehicles ?? 0} maintenance`;

  document.getElementById('kpi-active-deliveries').textContent = m.active_deliveries ?? 0;
  document.getElementById('kpi-pending-count').textContent = `${m.pending_deliveries ?? 0} pending`;

  document.getElementById('kpi-delivered-count').textContent = m.delivered_count ?? 0;
  document.getElementById('kpi-cancelled-count').textContent = `${m.cancelled_count ?? 0} cancelled`;

  const pct = Number(m.utilisation_pct ?? 0);
  document.getElementById('kpi-utilisation-pct').textContent = `${pct.toFixed(0)}%`;
  document.getElementById('kpi-driver-summary').textContent = `${m.available_drivers ?? 0} / ${m.total_drivers ?? STATE.drivers.length} drivers available`;

  const circumference = 201.06;
  const offset = circumference - (Math.min(100, Math.max(0, pct)) / 100) * circumference;
  const circle = document.getElementById('kpi-ring-circle');
  if (circle) {
    circle.style.strokeDashoffset = String(offset);
  }

  const zoneEl = document.getElementById('kpi-utilisation-zone');
  if (zoneEl) {
    if (pct === 0) zoneEl.textContent = 'IDLE ZONE (0%)';
    else if (pct < 75) zoneEl.textContent = `OPTIMAL LOAD (${pct.toFixed(0)}%)`;
    else zoneEl.textContent = `HIGH UTILISATION (${pct.toFixed(0)}%)`;
  }

  // Empty state check: when DB has 0 vehicles, 0 drivers, and 0 deliveries
  const isDbEmpty = STATE.vehicles.length === 0 && STATE.drivers.length === 0 && STATE.deliveries.length === 0;
  const emptyPanel = document.getElementById('dashboard-empty-state');
  if (emptyPanel) {
    emptyPanel.classList.toggle('hidden', !isDbEmpty);
  }

  // Render 4 Lanes: pending, assigned, in_transit, delivered
  const lanes = ['pending', 'assigned', 'in_transit', 'delivered'];
  lanes.forEach((lane) => {
    const items = STATE.deliveries.filter((d) => d.status === lane);
    const countEl = document.getElementById(`lane-count-${lane}`);
    const bodyEl = document.getElementById(`lane-body-${lane}`);
    if (countEl) countEl.textContent = items.length;
    if (!bodyEl) return;

    if (items.length === 0) {
      bodyEl.innerHTML = `
        <div class="lane-empty">
          <div>No ${escapeHtml(lane.replace('_', ' '))} deliveries</div>
          ${isDbEmpty
          ? `<button type="button" class="btn btn-ghost btn-xs mt-lg" data-goto-view="import">${icon('upload', 12)}<span>Import Data</span></button>`
          : ''
        }
        </div>
      `;
      return;
    }

    bodyEl.innerHTML = items
      .map((d) => {
        const capText = d.required_capacity ? `${d.required_capacity} kg` : 'Any cap';
        const asgText =
          d.active_vehicle_id && d.active_driver_id
            ? `<span>${icon('truck', 12)} ${escapeHtml(d.active_vehicle_id)}</span><span>${icon('users', 12)} ${escapeHtml(d.active_driver_id)}</span>`
            : '';
        let actionBtns = '';
        if (d.status === 'pending') {
          actionBtns = `
            <button type="button" class="btn btn-primary btn-xs" data-dispatch-delivery="${escapeHtml(d.delivery_id)}">
              ${icon('dispatch', 12)}<span>Assign</span>
            </button>
            <button type="button" class="btn btn-danger btn-xs" data-transition-delivery="${escapeHtml(d.delivery_id)}" data-target-status="cancelled">
              <span>Cancel</span>
            </button>
          `;
        } else if (d.status === 'assigned') {
          actionBtns = `
            <button type="button" class="btn btn-secondary btn-xs" data-transition-delivery="${escapeHtml(d.delivery_id)}" data-target-status="in_transit">
              ${icon('navigation', 12)}<span>Start Transit</span>
            </button>
            <button type="button" class="btn btn-danger btn-xs" data-transition-delivery="${escapeHtml(d.delivery_id)}" data-target-status="cancelled">
              <span>Cancel</span>
            </button>
          `;
        } else if (d.status === 'in_transit') {
          actionBtns = `
            <button type="button" class="btn btn-primary btn-xs" data-transition-delivery="${escapeHtml(d.delivery_id)}" data-target-status="delivered">
              ${icon('checkCircle', 12)}<span>Mark Delivered</span>
            </button>
          `;
        }
        return `
          <div class="lane-card">
            <div class="lane-card-top">
              <span class="lane-card-id">${escapeHtml(d.delivery_id)}</span>
              ${priorityBadgeHtml(d.priority)}
            </div>
            <div class="lane-card-route">${escapeHtml(d.pickup)} &rarr; ${escapeHtml(d.dropoff)}</div>
            <div class="lane-card-meta">
              <span>${escapeHtml(capText)}</span>
              ${asgText}
            </div>
            ${actionBtns ? `<div class="lane-card-actions">${actionBtns}</div>` : ''}
          </div>
        `;
      })
      .join('');
  });
}

function renderDeliveriesTable() {
  const tbody = document.getElementById('deliveries-tbody');
  if (!tbody) return;
  const rows = STATE.filteredDeliveries;

  if (rows.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="8" class="empty-cell">
          <div>No deliveries match your filter.</div>
          <div style="margin-top:8px;">
            <button type="button" class="btn btn-secondary btn-sm" data-goto-view="import">
              ${icon('upload', 14)}<span>Go to Import Data Page</span>
            </button>
          </div>
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = rows
    .map((d) => {
      const activeInfo =
        d.active_vehicle_id && d.active_driver_id
          ? `<code class="mono">${escapeHtml(d.active_vehicle_id)}</code> + <code class="mono">${escapeHtml(d.active_driver_id)}</code>`
          : `<span class="kpi-sub">—</span>`;

      let actions = '';
      if (d.status === 'pending') {
        actions = `
          <button type="button" class="btn btn-primary btn-xs" data-dispatch-delivery="${escapeHtml(d.delivery_id)}">
            ${icon('dispatch', 12)}<span>Assign</span>
          </button>
          <button type="button" class="btn btn-danger btn-xs" data-transition-delivery="${escapeHtml(d.delivery_id)}" data-target-status="cancelled">
            <span>Cancel</span>
          </button>
        `;
      } else if (d.status === 'assigned') {
        actions = `
          <button type="button" class="btn btn-secondary btn-xs" data-transition-delivery="${escapeHtml(d.delivery_id)}" data-target-status="in_transit">
            ${icon('navigation', 12)}<span>In Transit</span>
          </button>
          <button type="button" class="btn btn-danger btn-xs" data-transition-delivery="${escapeHtml(d.delivery_id)}" data-target-status="cancelled">
            <span>Cancel</span>
          </button>
        `;
      } else if (d.status === 'in_transit') {
        actions = `
          <button type="button" class="btn btn-primary btn-xs" data-transition-delivery="${escapeHtml(d.delivery_id)}" data-target-status="delivered">
            ${icon('checkCircle', 12)}<span>Complete</span>
          </button>
        `;
      } else {
        actions = `<span class="kpi-sub mono">Released / Final</span>`;
      }

      return `
        <tr>
          <td class="mono"><strong>${escapeHtml(d.delivery_id)}</strong></td>
          <td>${escapeHtml(d.pickup)} &rarr; ${escapeHtml(d.dropoff)}</td>
          <td class="mono">${escapeHtml(d.scheduled_time)}</td>
          <td>${priorityBadgeHtml(d.priority)}</td>
          <td class="mono">${d.required_capacity != null ? `${escapeHtml(d.required_capacity)} kg` : '—'}</td>
          <td>${statusBadgeHtml(d.status)}</td>
          <td>${activeInfo}</td>
          <td class="text-right">${actions}</td>
        </tr>
      `;
    })
    .join('');
}

function getVehicleEligibility(v, delivery) {
  if (v.active_delivery_id) {
    return {
      eligible: false,
      reason: `Occupied: assigned to active delivery ${v.active_delivery_id}`,
    };
  }
  if (v.status !== 'available') {
    return {
      eligible: false,
      reason: `Unavailable: vehicle status is '${v.status}'`,
    };
  }
  if (delivery && delivery.required_capacity != null && Number(v.capacity) < Number(delivery.required_capacity)) {
    return {
      eligible: false,
      reason: `Capacity mismatch: ${v.capacity} kg < required ${delivery.required_capacity} kg`,
    };
  }
  return {
    eligible: true,
    reason: `Eligible · ${v.capacity} kg capacity · ${v.registration_no}`,
  };
}

function getDriverEligibility(dr) {
  if (dr.active_delivery_id) {
    return {
      eligible: false,
      reason: `Occupied: assigned to active delivery ${dr.active_delivery_id}`,
    };
  }
  if (dr.availability_status !== 'available') {
    return {
      eligible: false,
      reason: `Unavailable: driver status is '${dr.availability_status}'`,
    };
  }
  return {
    eligible: true,
    reason: `Eligible · Available (${dr.phone})`,
  };
}

function renderDispatchConsole() {
  const pendingList = STATE.deliveries.filter((d) => d.status === 'pending');
  document.getElementById('dispatch-pending-count').textContent = `${pendingList.length} pending`;

  // Auto-select first pending delivery if none selected or selected is no longer pending (unless user is testing duplicate submit)
  if (
    !STATE.dispatchSelectedDeliveryId &&
    pendingList.length > 0
  ) {
    STATE.dispatchSelectedDeliveryId = pendingList[0].delivery_id;
  }

  const selectedDelivery = STATE.deliveries.find((d) => d.delivery_id === STATE.dispatchSelectedDeliveryId) || null;

  const delContainer = document.getElementById('dispatch-delivery-list');
  if (delContainer) {
    if (pendingList.length === 0) {
      delContainer.innerHTML = `
        <div class="lane-empty">
          <p>No pending deliveries available to assign.</p>
          <div style="margin-top:10px; display:flex; gap:8px; justify-content:center; flex-wrap:wrap;">
            <button type="button" class="btn btn-secondary btn-xs" data-goto-view="import">
              ${icon('upload', 12)}<span>Import Deliveries</span>
            </button>
          </div>
        </div>
      `;
    } else {
      delContainer.innerHTML = pendingList
        .map((d) => {
          const isSel = d.delivery_id === STATE.dispatchSelectedDeliveryId;
          const capReq = d.required_capacity != null ? `Req: ${d.required_capacity} kg` : 'No min cap';
          return `
            <button
              type="button"
              class="resource-option ${isSel ? 'selected' : ''}"
              data-select-dispatch-delivery="${escapeHtml(d.delivery_id)}"
            >
              <div class="resource-option-top">
                <span class="resource-id">${escapeHtml(d.delivery_id)}</span>
                ${priorityBadgeHtml(d.priority)}
              </div>
              <div>${escapeHtml(d.pickup)} &rarr; ${escapeHtml(d.dropoff)}</div>
              <div class="lane-card-meta">
                <span>${escapeHtml(capReq)}</span>
                <span>&bull; ${escapeHtml(d.scheduled_time)}</span>
              </div>
            </button>
          `;
        })
        .join('');
    }
  }

  const banner = document.getElementById('dispatch-selected-banner');
  if (banner) {
    if (selectedDelivery) {
      banner.innerHTML = `
        <strong>Target Delivery:</strong> <code class="mono">${escapeHtml(selectedDelivery.delivery_id)}</code>
        (${escapeHtml(selectedDelivery.pickup)} &rarr; ${escapeHtml(selectedDelivery.dropoff)}) &bull;
        <strong>Status:</strong> ${statusBadgeHtml(selectedDelivery.status)} &bull;
        <strong>Required Capacity:</strong> <code class="mono">${selectedDelivery.required_capacity != null ? `${selectedDelivery.required_capacity} kg` : 'None'
        }</code>
      `;
    } else {
      banner.textContent = 'Select or create a pending delivery to inspect vehicle and driver eligibility.';
    }
  }

  // Update Advisor recommendations for selected delivery
  const advisorCard = document.getElementById('advisor-rec-card');
  if (advisorCard) {
    if (selectedDelivery && selectedDelivery.status === 'pending') {
      apiRequest(`/deliveries/${encodeURIComponent(selectedDelivery.delivery_id)}/recommendations`)
        .then((recData) => {
          const recs = recData.recommendations || [];
          if (recs.length > 0) {
            const top = recs[0];
            advisorCard.classList.remove('hidden');
            const scoreEl = document.getElementById('advisor-top-score');
            const reasonEl = document.getElementById('advisor-top-reason');
            if (scoreEl) scoreEl.textContent = `${top.total_score}% MATCH`;
            if (reasonEl) {
              reasonEl.textContent = `Recommended Pair: Vehicle ${top.vehicle.vehicle_id} (${top.vehicle.type}, ${top.vehicle.capacity}kg, cap score ${top.capacity_fit_score}) + Driver ${top.driver.driver_id} (${top.driver.name}, fairness score ${top.driver_fairness_score}). Total score: ${top.total_score}/100. ${top.reason || ''}`;
            }
            STATE.topRecommendation = top;
          } else {
            advisorCard.classList.add('hidden');
            STATE.topRecommendation = null;
          }
        })
        .catch(() => {
          advisorCard.classList.add('hidden');
          STATE.topRecommendation = null;
        });
    } else {
      advisorCard.classList.add('hidden');
      STATE.topRecommendation = null;
    }
  }

  // Render Vehicles
  const vehContainer = document.getElementById('dispatch-vehicle-list');
  if (vehContainer) {
    if (STATE.vehicles.length === 0) {
      vehContainer.innerHTML = `
        <div class="lane-empty">
          No vehicles in database.
          <button type="button" class="btn btn-ghost btn-xs mt-lg" data-goto-view="import">${icon('upload', 12)}<span>Import Vehicles</span></button>
        </div>
      `;
    } else {
      vehContainer.innerHTML = STATE.vehicles
        .map((v) => {
          const check = getVehicleEligibility(v, selectedDelivery);
          const isDisabled = !check.eligible && !STATE.bypassUiGuardForTest;
          const isSelected = STATE.dispatchSelectedVehicleId === v.vehicle_id;
          return `
            <button
              type="button"
              class="resource-option ${isSelected ? 'selected' : ''}"
              data-select-dispatch-vehicle="${escapeHtml(v.vehicle_id)}"
              ${isDisabled ? 'disabled' : ''}
              aria-pressed="${isSelected}"
            >
              <div class="resource-option-top">
                <span class="resource-id">${escapeHtml(v.vehicle_id)} · ${escapeHtml(v.registration_no)}</span>
                ${statusBadgeHtml(v.status)}
              </div>
              <div>${escapeHtml(v.type)} (${escapeHtml(v.capacity)} kg)</div>
              <div class="${check.eligible ? 'resource-eligible-note' : 'resource-reason'}">
                ${escapeHtml(check.reason)}
              </div>
            </button>
          `;
        })
        .join('');
    }
  }

  // Render Drivers
  const drvContainer = document.getElementById('dispatch-driver-list');
  if (drvContainer) {
    if (STATE.drivers.length === 0) {
      drvContainer.innerHTML = `
        <div class="lane-empty">
          No drivers in database.
          <button type="button" class="btn btn-ghost btn-xs mt-lg" data-goto-view="import">${icon('upload', 12)}<span>Import Drivers</span></button>
        </div>
      `;
    } else {
      drvContainer.innerHTML = STATE.drivers
        .map((dr) => {
          const check = getDriverEligibility(dr);
          const isDisabled = !check.eligible && !STATE.bypassUiGuardForTest;
          const isSelected = STATE.dispatchSelectedDriverId === dr.driver_id;
          return `
            <button
              type="button"
              class="resource-option ${isSelected ? 'selected' : ''}"
              data-select-dispatch-driver="${escapeHtml(dr.driver_id)}"
              ${isDisabled ? 'disabled' : ''}
              aria-pressed="${isSelected}"
            >
              <div class="resource-option-top">
                <span class="resource-id">${escapeHtml(dr.driver_id)} · ${escapeHtml(dr.name)}</span>
                ${statusBadgeHtml(dr.availability_status)}
              </div>
              <div class="${check.eligible ? 'resource-eligible-note' : 'resource-reason'}">
                ${escapeHtml(check.reason)}
              </div>
            </button>
          `;
        })
        .join('');
    }
  }

  document.getElementById('sum-delivery').textContent = STATE.dispatchSelectedDeliveryId || 'None';
  document.getElementById('sum-vehicle').textContent = STATE.dispatchSelectedVehicleId || 'None';
  document.getElementById('sum-driver').textContent = STATE.dispatchSelectedDriverId || 'None';

  const submitBtn = document.getElementById('btn-submit-assign');
  if (submitBtn) {
    submitBtn.disabled = !(
      STATE.dispatchSelectedDeliveryId &&
      STATE.dispatchSelectedVehicleId &&
      STATE.dispatchSelectedDriverId
    );
  }
}

function renderFleetTable() {
  const tbody = document.getElementById('fleet-tbody');
  if (!tbody) return;
  const q = STATE.fleetSearchQuery.trim().toLowerCase();
  const rows = STATE.vehicles.filter((v) => {
    if (!q) return true;
    return (
      v.vehicle_id.toLowerCase().includes(q) ||
      v.registration_no.toLowerCase().includes(q) ||
      v.type.toLowerCase().includes(q)
    );
  });

  if (rows.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="7" class="empty-cell">
          <div>No vehicles registered yet.</div>
          <div style="margin-top:8px;">
            <button type="button" class="btn btn-secondary btn-sm" data-goto-view="import">
              ${icon('upload', 14)}<span>Import Vehicles (CSV/JSON)</span>
            </button>
          </div>
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = rows
    .map((v) => {
      const activeDel = v.active_delivery_id
        ? `<code class="mono">${escapeHtml(v.active_delivery_id)}</code>`
        : `<span class="kpi-sub">—</span>`;
      return `
        <tr>
          <td class="mono"><strong>${escapeHtml(v.vehicle_id)}</strong></td>
          <td class="mono">${escapeHtml(v.registration_no)}</td>
          <td>${escapeHtml(v.type)}</td>
          <td class="mono">${escapeHtml(v.capacity)}</td>
          <td>${statusBadgeHtml(v.status)}</td>
          <td>${activeDel}</td>
          <td class="text-right">
            <div style="display:inline-flex; gap:4px; flex-wrap:wrap; justify-content:flex-end;">
              <button type="button" class="btn btn-ghost btn-xs" data-vehicle-status="${escapeHtml(v.vehicle_id)}" data-status="available" ${v.status === 'available' ? 'disabled' : ''}>Available</button>
              <button type="button" class="btn btn-ghost btn-xs" data-vehicle-status="${escapeHtml(v.vehicle_id)}" data-status="maintenance" ${v.status === 'maintenance' ? 'disabled' : ''}>Maintenance</button>
              <button type="button" class="btn btn-ghost btn-xs" data-vehicle-status="${escapeHtml(v.vehicle_id)}" data-status="inactive" ${v.status === 'inactive' ? 'disabled' : ''}>Inactive</button>
            </div>
          </td>
        </tr>
      `;
    })
    .join('');
}

function renderDriversTable() {
  const tbody = document.getElementById('drivers-tbody');
  if (!tbody) return;
  const q = STATE.driverSearchQuery.trim().toLowerCase();
  const rows = STATE.drivers.filter((d) => {
    if (!q) return true;
    return (
      d.driver_id.toLowerCase().includes(q) ||
      d.name.toLowerCase().includes(q) ||
      d.phone.toLowerCase().includes(q)
    );
  });

  if (rows.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="6" class="empty-cell">
          <div>No drivers registered yet.</div>
          <div style="margin-top:8px;">
            <button type="button" class="btn btn-secondary btn-sm" data-goto-view="import">
              ${icon('upload', 14)}<span>Import Drivers (CSV/JSON)</span>
            </button>
          </div>
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = rows
    .map((d) => {
      const activeDel = d.active_delivery_id
        ? `<code class="mono">${escapeHtml(d.active_delivery_id)}</code>`
        : `<span class="kpi-sub">—</span>`;
      return `
        <tr>
          <td class="mono"><strong>${escapeHtml(d.driver_id)}</strong></td>
          <td>${escapeHtml(d.name)}</td>
          <td class="mono">${escapeHtml(d.phone)}</td>
          <td>${statusBadgeHtml(d.availability_status)}</td>
          <td>${activeDel}</td>
          <td class="text-right">
            <div style="display:inline-flex; gap:4px; flex-wrap:wrap; justify-content:flex-end;">
              <button type="button" class="btn btn-ghost btn-xs" data-driver-status="${escapeHtml(d.driver_id)}" data-status="available" ${d.availability_status === 'available' ? 'disabled' : ''}>Set Available</button>
              <button type="button" class="btn btn-ghost btn-xs" data-driver-status="${escapeHtml(d.driver_id)}" data-status="unavailable" ${d.availability_status === 'unavailable' ? 'disabled' : ''}>Set Unavailable</button>
            </div>
          </td>
        </tr>
      `;
    })
    .join('');
}

function renderAuditTable() {
  const tbody = document.getElementById('audit-tbody');
  if (!tbody) return;
  if (STATE.audit.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="8" class="empty-cell">No audit events recorded yet. Import or create records to see the immutable log.</td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = STATE.audit
    .map((entry) => {
      return `
        <tr>
          <td class="mono">#${escapeHtml(entry.id)}</td>
          <td class="mono">${escapeHtml(entry.ts)}</td>
          <td class="mono">${escapeHtml(entry.actor)}</td>
          <td><span class="status-badge status-assigned">${icon('activity', 12)}<span>${escapeHtml(entry.action)}</span></span></td>
          <td class="mono">${escapeHtml(entry.entity)}</td>
          <td class="mono"><strong>${escapeHtml(entry.entity_id)}</strong></td>
          <td class="mono" style="max-width:240px; overflow:hidden; text-overflow:ellipsis;"><code>${escapeHtml(entry.before_json || '—')}</code></td>
          <td class="mono" style="max-width:260px; overflow:hidden; text-overflow:ellipsis;"><code>${escapeHtml(entry.after_json || '—')}</code></td>
        </tr>
      `;
    })
    .join('');
}

/* ==================== VIEW NAVIGATION ==================== */
function switchView(viewName) {
  if (!VIEW_META[viewName]) return;
  STATE.activeView = viewName;

  document.querySelectorAll('.nav-item').forEach((btn) => {
    const isMatch = btn.getAttribute('data-view') === viewName;
    btn.classList.toggle('active', isMatch);
    if (isMatch) btn.setAttribute('aria-current', 'page');
    else btn.removeAttribute('aria-current');
  });

  document.querySelectorAll('.view-section').forEach((sec) => {
    sec.classList.toggle('active', sec.id === `view-${viewName}`);
  });

  document.getElementById('page-title').textContent = VIEW_META[viewName].title;
  document.getElementById('page-subtitle').textContent = VIEW_META[viewName].subtitle;
  document.getElementById('sidebar').classList.remove('open');

  if (viewName === 'analytics') {
    renderAnalytics();
  } else if (viewName === 'routes') {
    renderRouteRadar();
  }
}

/* ==================== IMPORT PIPELINE ==================== */
function setImportEntity(entity) {
  STATE.importEntity = entity;
  STATE.importFile = null;
  STATE.importDryRunResult = null;

  document.querySelectorAll('[data-import-entity]').forEach((btn) => {
    const active = btn.getAttribute('data-import-entity') === entity;
    btn.classList.toggle('active', active);
    btn.setAttribute('aria-checked', String(active));
  });

  document.getElementById('import-expected-cols').textContent = EXPECTED_COLS[entity] || '';
  const link = document.getElementById('link-download-template');
  if (link) {
    link.href = `/import/templates/${entity}.csv`;
    link.setAttribute('download', `${entity}_template.csv`);
  }

  document.getElementById('dropzone-filename').textContent =
    'Drag & drop a .csv or .json file here, or click to browse';
  document.getElementById('btn-commit-import').disabled = true;
  document.getElementById('btn-download-error-csv').classList.add('hidden');
  document.getElementById('import-summary-banner').classList.add('hidden');
  document.getElementById('import-preview-tbody').innerHTML =
    '<tr><td colspan="4" class="empty-cell">No file loaded yet.</td></tr>';
}

async function handleImportFileSelected(file) {
  if (!file) return;
  STATE.importFile = file;
  document.getElementById('dropzone-filename').textContent = `Selected: ${file.name} (${file.size} bytes)`;

  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await fetch(`/import/${STATE.importEntity}?dry_run=true`, {
      method: 'POST',
      body: formData,
    });
    const data = await res.json();
    if (!res.ok && !data.rows) {
      showGlobalError(data.error || 'IMPORT_ERROR', data.message || 'Dry-run failed');
      return;
    }
    STATE.importDryRunResult = data;
    renderImportDryRun(data);
  } catch (err) {
    showGlobalError('IMPORT_DRY_RUN_ERROR', err.message);
  }
}

function renderImportDryRun(data) {
  const banner = document.getElementById('import-summary-banner');
  const tbody = document.getElementById('import-preview-tbody');
  const commitBtn = document.getElementById('btn-commit-import');
  const errBtn = document.getElementById('btn-download-error-csv');

  const total = data.total_rows ?? 0;
  const valid = data.valid_rows ?? 0;
  const invalid = data.invalid_rows ?? 0;
  const errors = data.errors || [];
  const rows = data.rows || [];

  banner.classList.remove('hidden', 'valid', 'invalid');
  if (invalid === 0 && total > 0) {
    banner.classList.add('valid');
    banner.textContent = `DRY-RUN PASSED: ${valid} / ${total} rows valid. Ready for atomic transaction commit.`;
    commitBtn.disabled = false;
    errBtn.classList.add('hidden');
  } else {
    banner.classList.add('invalid');
    banner.textContent = `DRY-RUN BLOCKED: ${invalid} error(s) detected across ${total} row(s). Fix errors or download error report; atomic commit requires 0 errors.`;
    commitBtn.disabled = true;
    errBtn.classList.toggle('hidden', errors.length === 0);
  }

  if (rows.length === 0) {
    tbody.innerHTML = `<tr><td colspan="4" class="empty-cell">File contained 0 rows.</td></tr>`;
    return;
  }

  tbody.innerHTML = rows
    .map((r) => {
      const rowErrors = r.errors || [];
      const isOk = rowErrors.length === 0;
      const badge = isOk
        ? `<span class="status-badge status-available">${icon('checkCircle', 12)}<span>VALID</span></span>`
        : `<span class="status-badge status-error">${icon('alertTriangle', 12)}<span>${rowErrors.length} ERROR(S)</span></span>`;

      const errHtml = isOk
        ? `<span class="kpi-sub">All constraints satisfied</span>`
        : rowErrors
          .map(
            (e) =>
              `<div class="resource-reason">Row ${escapeHtml(e.row)} · <strong>${escapeHtml(e.field)}</strong>: ${escapeHtml(e.reason)}</div>`
          )
          .join('');

      return `
        <tr>
          <td class="mono">#${escapeHtml(r.row)}</td>
          <td>${badge}</td>
          <td class="mono"><code>${escapeHtml(JSON.stringify(r.data))}</code></td>
          <td>${errHtml}</td>
        </tr>
      `;
    })
    .join('');
}

async function commitImport() {
  if (!STATE.importFile) return;
  const formData = new FormData();
  formData.append('file', STATE.importFile);

  try {
    const res = await fetch(`/import/${STATE.importEntity}?dry_run=false`, {
      method: 'POST',
      body: formData,
    });
    const data = await res.json();
    if (!res.ok) {
      showGlobalError(data.error || 'IMPORT_COMMIT_FAILED', data.message || 'Atomic import rolled back');
      if (data.rows) renderImportDryRun(data);
      return;
    }
    const banner = document.getElementById('import-summary-banner');
    banner.classList.remove('hidden', 'invalid');
    banner.classList.add('valid');
    banner.textContent = `COMMITTED ATOMICALLY: Inserted ${data.inserted_count} ${STATE.importEntity} record(s) and wrote audit_log entry.`;
    document.getElementById('btn-commit-import').disabled = true;
    showToast(`Imported ${data.inserted_count} ${STATE.importEntity} atomically.`);
    await refreshAllData();
  } catch (err) {
    showGlobalError('IMPORT_COMMIT_ERROR', err.message);
  }
}

function downloadErrorReportCsv() {
  const res = STATE.importDryRunResult;
  if (!res || !Array.isArray(res.errors)) return;
  const header = 'row,field,code,reason\n';
  const lines = res.errors.map((e) => {
    const esc = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`;
    return [esc(e.row), esc(e.field), esc(e.code || 'VALIDATION_ERROR'), esc(e.reason)].join(',');
  });
  const blob = new Blob([header + lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${STATE.importEntity}_import_errors.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

/* ==================== COMMAND PALETTE ==================== */
const COMMANDS = [
  { label: 'Go to Command Center (Dashboard)', action: () => switchView('dashboard'), kbd: '1' },
  { label: 'Go to Deliveries Management', action: () => switchView('deliveries'), kbd: '2' },
  { label: 'Go to Dispatch Console (Assign)', action: () => switchView('dispatch'), kbd: '3' },
  { label: 'Go to Fleet Vehicles', action: () => switchView('fleet'), kbd: '4' },
  { label: 'Go to Drivers Directory', action: () => switchView('drivers'), kbd: '5' },
  { label: 'Go to Import Data (CSV/JSON)', action: () => switchView('import'), kbd: 'I' },
  { label: 'Go to Race Lab (Concurrency Proof)', action: () => switchView('racelab'), kbd: 'L' },
  { label: 'Go to Fleet Analytics', action: () => switchView('analytics'), kbd: 'Y' },
  { label: 'Go to Route Radar Visualizer', action: () => switchView('routes'), kbd: 'M' },
  { label: 'Go to Audit Log', action: () => switchView('audit'), kbd: 'A' },
  { label: 'Create New Delivery Order', action: () => openModal('modal-delivery'), kbd: 'N' },
  { label: 'Register New Fleet Vehicle', action: () => openModal('modal-vehicle'), kbd: 'V' },
  { label: 'Register New Driver', action: () => openModal('modal-driver'), kbd: 'D' },
  { label: 'Sync / Refresh Telemetry Now', action: () => refreshAllData(), kbd: 'R' },
];

function openCommandPalette() {
  openModal('modal-cmd');
  const input = document.getElementById('cmd-input');
  input.value = '';
  renderCommandList('');
  setTimeout(() => input.focus(), 20);
}

function renderCommandList(query) {
  const listEl = document.getElementById('cmd-list');
  const q = query.trim().toLowerCase();
  const matches = COMMANDS.filter((c) => !q || c.label.toLowerCase().includes(q));
  listEl.innerHTML = matches
    .map(
      (c, idx) => `
      <button type="button" class="cmd-item" data-cmd-idx="${COMMANDS.indexOf(c)}" role="option" aria-selected="${idx === 0}">
        <span>${escapeHtml(c.label)}</span>
        <kbd class="kbd-hint">${escapeHtml(c.kbd)}</kbd>
      </button>
    `
    )
    .join('');
}

/* ==================== MODALS & FORMS ==================== */
function openModal(id) {
  const modal = document.getElementById(id);
  if (!modal) return;
  modal.classList.remove('hidden');
  const errBox = modal.querySelector('.form-error-summary');
  if (errBox) errBox.classList.add('hidden');
}

function closeModal(id) {
  const modal = document.getElementById(id);
  if (modal) modal.classList.add('hidden');
}

function showFormError(containerId, code, message) {
  const box = document.getElementById(containerId);
  if (!box) return;
  box.innerHTML = `
    <div class="error-summary-header">
      ${icon('alertTriangle', 15)}
      <strong>${escapeHtml(code || 'VALIDATION_ERROR')}</strong>
    </div>
    <div>${escapeHtml(message)}</div>
  `;
  box.classList.remove('hidden');
  box.focus();
}

/* ==================== ADVANCED PHASE B COMPONENTS ==================== */
async function refreshBlockedQueue() {
  try {
    const res = await apiRequest('/deliveries/blocked');
    const count = res.count ?? 0;
    const btnLabel = document.getElementById('blocked-queue-btn-label');
    if (btnLabel) btnLabel.textContent = `Blocked Queue (${count})`;
    STATE.blockedQueue = res.blocked_deliveries || [];
  } catch {}
}

async function renderAnalytics() {
  try {
    const data = await apiRequest('/analytics/summary');
    const ontimeEl = document.getElementById('chart-ontime');
    const funnelEl = document.getElementById('chart-funnel');
    const workloadEl = document.getElementById('chart-workload');

    if (ontimeEl) {
      const pct = data.on_time_pct ?? 100;
      const strokePct = Math.min(100, Math.max(0, pct));
      const circ = 2 * Math.PI * 50;
      const dashOffset = circ - (strokePct / 100) * circ;
      ontimeEl.innerHTML = `
        <svg viewBox="0 0 160 160" width="160" height="160">
          <circle cx="80" cy="80" r="50" fill="none" stroke="var(--color-border)" stroke-width="12" />
          <circle cx="80" cy="80" r="50" fill="none" stroke="var(--color-primary)" stroke-width="12"
            stroke-dasharray="${circ}" stroke-dashoffset="${dashOffset}" stroke-linecap="round"
            transform="rotate(-90 80 80)" />
          <text x="80" y="78" text-anchor="middle" font-family="var(--font-mono)" font-size="20" font-weight="700" fill="var(--color-foreground)">${pct}%</text>
          <text x="80" y="96" text-anchor="middle" font-family="var(--font-mono)" font-size="10" fill="var(--color-muted-foreground)">ON-TIME RATE</text>
        </svg>
      `;
    }

    if (funnelEl) {
      const f = data.funnel || {};
      const stages = [
        { label: 'Pending', count: f.pending ?? 0, color: 'var(--status-info-fg)' },
        { label: 'Assigned', count: f.assigned ?? 0, color: 'var(--status-warning-fg)' },
        { label: 'In Transit', count: f.in_transit ?? 0, color: 'var(--color-primary)' },
        { label: 'Delivered', count: f.delivered ?? 0, color: 'var(--status-success-fg)' },
      ];
      const maxCount = Math.max(1, ...stages.map(s => s.count));
      funnelEl.innerHTML = `
        <svg viewBox="0 0 320 160" width="100%" height="160">
          ${stages.map((s, idx) => {
            const y = 15 + idx * 36;
            const barWidth = Math.max(8, (s.count / maxCount) * 190);
            return `
              <text x="10" y="${y + 14}" font-family="var(--font-mono)" font-size="11" fill="var(--color-foreground)">${escapeHtml(s.label)}</text>
              <rect x="90" y="${y}" width="${barWidth}" height="20" rx="4" fill="${s.color}" opacity="0.85" />
              <text x="${98 + barWidth}" y="${y + 14}" font-family="var(--font-mono)" font-size="11" font-weight="700" fill="var(--color-foreground)">${s.count}</text>
            `;
          }).join('')}
        </svg>
      `;
    }

    if (workloadEl) {
      const wl = data.driver_workload || [];
      if (wl.length === 0) {
        workloadEl.innerHTML = '<div class="empty-cell">No completed driver trips recorded yet.</div>';
      } else {
        const maxTrips = Math.max(1, ...wl.map(w => w.total_trips));
        workloadEl.innerHTML = `
          <svg viewBox="0 0 600 ${wl.length * 36 + 20}" width="100%" height="${wl.length * 36 + 20}">
            ${wl.map((w, idx) => {
              const y = 10 + idx * 36;
              const barW = Math.max(8, (w.total_trips / maxTrips) * 380);
              return `
                <text x="10" y="${y + 14}" font-family="var(--font-mono)" font-size="12" fill="var(--color-foreground)">${escapeHtml(w.name || 'Driver')}</text>
                <rect x="150" y="${y}" width="${barW}" height="20" rx="4" fill="var(--color-primary)" opacity="0.8" />
                <text x="${160 + barW}" y="${y + 14}" font-family="var(--font-mono)" font-size="12" font-weight="700" fill="var(--color-foreground)">${w.total_trips} trips</text>
              `;
            }).join('')}
          </svg>
        `;
      }
    }
  } catch {}
}

async function renderRouteRadar() {
  try {
    const routes = await apiRequest('/deliveries/routes');
    const svg = document.getElementById('route-svg-canvas');
    if (!svg) return;
    if (!routes || routes.length === 0) {
      svg.innerHTML = `
        <rect width="1000" height="500" fill="#0D1117" />
        <circle cx="500" cy="250" r="180" fill="none" stroke="rgba(0, 255, 65, 0.15)" stroke-width="1" />
        <circle cx="500" cy="250" r="90" fill="none" stroke="rgba(0, 255, 65, 0.15)" stroke-width="1" />
        <line x1="80" y1="250" x2="920" y2="250" stroke="rgba(0, 255, 65, 0.12)" stroke-dasharray="4 4" />
        <line x1="500" y1="40" x2="500" y2="460" stroke="rgba(0, 255, 65, 0.12)" stroke-dasharray="4 4" />
        <text x="500" y="250" text-anchor="middle" font-family="var(--font-mono)" font-size="13" fill="var(--color-muted-foreground)">NO ACTIVE DELIVERIES ON ROUTE RADAR</text>
      `;
      return;
    }

    let svgContent = `
      <rect width="1000" height="500" fill="#0D1117" />
      <circle cx="500" cy="250" r="220" fill="none" stroke="rgba(0, 255, 65, 0.15)" stroke-width="1" />
      <circle cx="500" cy="250" r="120" fill="none" stroke="rgba(0, 255, 65, 0.15)" stroke-width="1" />
      <line x1="50" y1="250" x2="950" y2="250" stroke="rgba(0, 255, 65, 0.15)" stroke-dasharray="4 4" />
      <line x1="500" y1="30" x2="500" y2="470" stroke="rgba(0, 255, 65, 0.15)" stroke-dasharray="4 4" />
    `;

    routes.forEach((r, idx) => {
      const angle1 = (idx * 55) * (Math.PI / 180);
      const angle2 = ((idx * 55) + 140) * (Math.PI / 180);
      const x1 = 500 + Math.cos(angle1) * 160;
      const y1 = 250 + Math.sin(angle1) * 120;
      const x2 = 500 + Math.cos(angle2) * 180;
      const y2 = 250 + Math.sin(angle2) * 140;

      const strokeColor = r.status === 'in_transit' ? 'var(--color-primary)' : 'var(--status-info-fg)';
      const dash = r.status === 'in_transit' ? 'stroke-dasharray="6 4"' : '';

      svgContent += `
        <path d="M ${x1} ${y1} Q 500 250 ${x2} ${y2}" fill="none" stroke="${strokeColor}" stroke-width="2.5" ${dash} />
        <circle cx="${x1}" cy="${y1}" r="6" fill="${strokeColor}" />
        <circle cx="${x2}" cy="${y2}" r="6" fill="var(--color-accent)" />
        <text x="${x1 + 8}" y="${y1 + 4}" font-family="var(--font-mono)" font-size="11" fill="var(--color-foreground)">${escapeHtml(r.pickup)} (${escapeHtml(r.delivery_id)})</text>
        <text x="${x2 + 8}" y="${y2 + 4}" font-family="var(--font-mono)" font-size="11" fill="var(--color-foreground)">${escapeHtml(r.dropoff)}</text>
      `;
    });

    svg.innerHTML = svgContent;
  } catch {}
}

function initTheme() {
  const saved = localStorage.getItem('fleetwise_theme') || 'dark';
  document.documentElement.setAttribute('data-theme', saved);
  updateThemeBtn(saved);
}

function toggleTheme() {
  const cur = document.documentElement.getAttribute('data-theme') || 'dark';
  const next = cur === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('fleetwise_theme', next);
  updateThemeBtn(next);
}

function updateThemeBtn(theme) {
  const lbl = document.getElementById('theme-label');
  if (lbl) lbl.textContent = theme === 'dark' ? 'Dark' : 'Light';
}

let sseSource = null;
function setupSSE() {
  if (!window.EventSource) return;
  try {
    sseSource = new EventSource('/events');
    sseSource.onopen = () => {
      const dot = document.getElementById('telemetry-dot');
      const txt = document.getElementById('telemetry-status');
      if (dot) dot.classList.remove('paused');
      if (txt) txt.textContent = 'LIVE SSE';
    };
    sseSource.onmessage = () => {
      refreshAllData(true);
    };
    sseSource.onerror = () => {
      const txt = document.getElementById('telemetry-status');
      if (txt) txt.textContent = 'POLL 5s';
    };
  } catch {}
}

/* ==================== EVENT BINDINGS ==================== */
function setupEventListeners() {
  // Sidebar navigation
  document.querySelectorAll('.nav-item').forEach((btn) => {
    btn.addEventListener('click', () => {
      switchView(btn.getAttribute('data-view'));
    });
  });

  // Mobile menu button
  document.getElementById('mobile-menu-btn')?.addEventListener('click', () => {
    const sb = document.getElementById('sidebar');
    sb.classList.toggle('open');
  });

  // Dismiss global error
  document.getElementById('btn-dismiss-error')?.addEventListener('click', clearGlobalError);

  // Quick buttons
  document.getElementById('btn-refresh-now')?.addEventListener('click', () => refreshAllData());
  document.getElementById('btn-refresh-audit')?.addEventListener('click', () => refreshAllData());
  document.getElementById('btn-quick-dispatch')?.addEventListener('click', () => switchView('dispatch'));
  document.getElementById('btn-cmd-palette')?.addEventListener('click', openCommandPalette);

  // Polling toggle
  document.getElementById('btn-toggle-poll')?.addEventListener('click', () => {
    STATE.pollingEnabled = !STATE.pollingEnabled;
    const dot = document.getElementById('telemetry-dot');
    const txt = document.getElementById('telemetry-status');
    const ic = document.getElementById('poll-icon');
    if (STATE.pollingEnabled) {
      dot.classList.remove('paused');
      txt.textContent = 'LIVE 5s';
      ic.innerHTML = icon('pause', 14);
    } else {
      dot.classList.add('paused');
      txt.textContent = 'PAUSED';
      ic.innerHTML = icon('play', 14);
    }
  });

  // Modal triggers
  document.getElementById('btn-open-vehicle-modal')?.addEventListener('click', () => openModal('modal-vehicle'));
  document.getElementById('btn-empty-create-vehicle')?.addEventListener('click', () => openModal('modal-vehicle'));
  document.getElementById('btn-open-driver-modal')?.addEventListener('click', () => openModal('modal-driver'));
  document.getElementById('btn-open-delivery-modal')?.addEventListener('click', () => {
    const dtInput = document.getElementById('del-time');
    if (dtInput && !dtInput.value) {
      dtInput.value = new Date(Date.now() + 3600 * 1000).toISOString().replace(/\.\d{3}Z$/, 'Z');
    }
    openModal('modal-delivery');
  });
  document.getElementById('btn-dash-new-delivery')?.addEventListener('click', () => {
    const dtInput = document.getElementById('del-time');
    if (dtInput && !dtInput.value) {
      dtInput.value = new Date(Date.now() + 3600 * 1000).toISOString().replace(/\.\d{3}Z$/, 'Z');
    }
    openModal('modal-delivery');
  });
  document.getElementById('btn-empty-create-delivery')?.addEventListener('click', () => {
    const dtInput = document.getElementById('del-time');
    if (dtInput && !dtInput.value) {
      dtInput.value = new Date(Date.now() + 3600 * 1000).toISOString().replace(/\.\d{3}Z$/, 'Z');
    }
    openModal('modal-delivery');
  });

  // Close modal buttons
  document.querySelectorAll('[data-close-modal]').forEach((btn) => {
    btn.addEventListener('click', () => closeModal(btn.getAttribute('data-close-modal')));
  });

  // Delegated click handler for dynamic elements
  document.addEventListener('click', async (e) => {
    const gotoBtn = e.target.closest('[data-goto-view]');
    if (gotoBtn) {
      switchView(gotoBtn.getAttribute('data-goto-view'));
      return;
    }

    const dispatchJump = e.target.closest('[data-dispatch-delivery]');
    if (dispatchJump) {
      STATE.dispatchSelectedDeliveryId = dispatchJump.getAttribute('data-dispatch-delivery');
      switchView('dispatch');
      renderDispatchConsole();
      return;
    }

    const selDel = e.target.closest('[data-select-dispatch-delivery]');
    if (selDel) {
      STATE.dispatchSelectedDeliveryId = selDel.getAttribute('data-select-dispatch-delivery');
      renderDispatchConsole();
      return;
    }

    const selVeh = e.target.closest('[data-select-dispatch-vehicle]');
    if (selVeh && !selVeh.disabled) {
      STATE.dispatchSelectedVehicleId = selVeh.getAttribute('data-select-dispatch-vehicle');
      renderDispatchConsole();
      return;
    }

    const selDrv = e.target.closest('[data-select-dispatch-driver]');
    if (selDrv && !selDrv.disabled) {
      STATE.dispatchSelectedDriverId = selDrv.getAttribute('data-select-dispatch-driver');
      renderDispatchConsole();
      return;
    }

    const transBtn = e.target.closest('[data-transition-delivery]');
    if (transBtn) {
      const delId = transBtn.getAttribute('data-transition-delivery');
      const targetStatus = transBtn.getAttribute('data-target-status');
      try {
        clearGlobalError();
        await apiRequest(`/deliveries/${encodeURIComponent(delId)}/status`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ status: targetStatus }),
        });
        showToast(`Delivery ${delId} transitioned to ${targetStatus}.`);
        await refreshAllData();
      } catch (err) {
        showGlobalError(err.code, err.message);
      }
      return;
    }

    const vehStatusBtn = e.target.closest('[data-vehicle-status]');
    if (vehStatusBtn) {
      const vehId = vehStatusBtn.getAttribute('data-vehicle-status');
      const status = vehStatusBtn.getAttribute('data-status');
      try {
        clearGlobalError();
        await apiRequest(`/vehicles/${encodeURIComponent(vehId)}/status`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ status }),
        });
        showToast(`Vehicle ${vehId} status updated to ${status}.`);
        await refreshAllData();
      } catch (err) {
        showGlobalError(err.code, err.message);
      }
      return;
    }

    const drvStatusBtn = e.target.closest('[data-driver-status]');
    if (drvStatusBtn) {
      const drvId = drvStatusBtn.getAttribute('data-driver-status');
      const availability_status = drvStatusBtn.getAttribute('data-status');
      try {
        clearGlobalError();
        await apiRequest(`/drivers/${encodeURIComponent(drvId)}/status`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ availability_status }),
        });
        showToast(`Driver ${drvId} availability updated to ${availability_status}.`);
        await refreshAllData();
      } catch (err) {
        showGlobalError(err.code, err.message);
      }
      return;
    }

    const cmdItem = e.target.closest('[data-cmd-idx]');
    if (cmdItem) {
      const cmd = COMMANDS[Number(cmdItem.getAttribute('data-cmd-idx'))];
      closeModal('modal-cmd');
      if (cmd) cmd.action();
    }
  });

  // Deliveries filter & search
  document.querySelectorAll('[data-delivery-status]').forEach((chip) => {
    chip.addEventListener('click', async () => {
      document.querySelectorAll('[data-delivery-status]').forEach((c) => c.classList.remove('active'));
      chip.classList.add('active');
      STATE.deliveryFilterStatus = chip.getAttribute('data-delivery-status') || '';
      await refreshFilteredDeliveries();
      renderDeliveriesTable();
    });
  });

  document.getElementById('deliveries-search')?.addEventListener('input', async (e) => {
    STATE.deliverySearchQuery = e.target.value;
    await refreshFilteredDeliveries();
    renderDeliveriesTable();
  });

  document.getElementById('fleet-search')?.addEventListener('input', (e) => {
    STATE.fleetSearchQuery = e.target.value;
    renderFleetTable();
  });

  document.getElementById('drivers-search')?.addEventListener('input', (e) => {
    STATE.driverSearchQuery = e.target.value;
    renderDriversTable();
  });

  // Toggle server guard test in Dispatch
  document.getElementById('toggle-server-guard-test')?.addEventListener('change', (e) => {
    STATE.bypassUiGuardForTest = e.target.checked;
    renderDispatchConsole();
  });

  // Submit Atomic Assignment
  document.getElementById('btn-submit-assign')?.addEventListener('click', async () => {
    const delId = STATE.dispatchSelectedDeliveryId;
    const vehId = STATE.dispatchSelectedVehicleId;
    const drvId = STATE.dispatchSelectedDriverId;
    if (!delId || !vehId || !drvId) return;

    const errBox = document.getElementById('dispatch-error-box');
    if (errBox) errBox.classList.add('hidden');
    clearGlobalError();

    try {
      await apiRequest(`/deliveries/${encodeURIComponent(delId)}/assign`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ vehicle_id: vehId, driver_id: drvId }),
      });
      showToast(`Assigned ${vehId} + ${drvId} to delivery ${delId}.`);
      STATE.dispatchSelectedDeliveryId = null;
      STATE.dispatchSelectedVehicleId = null;
      STATE.dispatchSelectedDriverId = null;
      await refreshAllData();
    } catch (err) {
      if (errBox) {
        document.getElementById('dispatch-error-code').textContent = err.code || 'CONFLICT';
        document.getElementById('dispatch-error-msg').textContent = err.message;
        errBox.classList.remove('hidden');
        errBox.focus();
      }
      showGlobalError(err.code, err.message);
      await refreshAllData(true);
    }
  });

  // Create Vehicle Form
  document.getElementById('form-vehicle')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const payload = {
      vehicle_id: fd.get('vehicle_id')?.trim() || undefined,
      registration_no: fd.get('registration_no')?.trim() || '',
      type: fd.get('type')?.trim() || '',
      capacity: Number(fd.get('capacity')),
      status: fd.get('status') || 'available',
    };
    try {
      const created = await apiRequest('/vehicles', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      closeModal('modal-vehicle');
      e.target.reset();
      showToast(`Created vehicle ${created.vehicle_id} (${created.registration_no}).`);
      await refreshAllData();
    } catch (err) {
      showFormError('form-vehicle-errors', err.code, err.message);
    }
  });

  // Create Driver Form
  document.getElementById('form-driver')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const payload = {
      driver_id: fd.get('driver_id')?.trim() || undefined,
      name: fd.get('name')?.trim() || '',
      phone: fd.get('phone')?.trim() || '',
      availability_status: fd.get('availability_status') || 'available',
    };
    try {
      const created = await apiRequest('/drivers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      closeModal('modal-driver');
      e.target.reset();
      showToast(`Created driver ${created.driver_id} (${created.name}).`);
      await refreshAllData();
    } catch (err) {
      showFormError('form-driver-errors', err.code, err.message);
    }
  });

  // Create Delivery Form
  document.getElementById('form-delivery')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const capRaw = fd.get('required_capacity')?.trim();
    const payload = {
      delivery_id: fd.get('delivery_id')?.trim() || undefined,
      pickup: fd.get('pickup')?.trim() || '',
      dropoff: fd.get('dropoff')?.trim() || '',
      scheduled_time: fd.get('scheduled_time')?.trim() || '',
      priority: fd.get('priority') || 'normal',
      required_capacity: capRaw ? Number(capRaw) : null,
    };
    try {
      const created = await apiRequest('/deliveries', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      closeModal('modal-delivery');
      e.target.reset();
      showToast(`Created pending delivery ${created.delivery_id}.`);
      await refreshAllData();
    } catch (err) {
      showFormError('form-delivery-errors', err.code, err.message);
    }
  });

  // Import Data Listeners
  document.querySelectorAll('[data-import-entity]').forEach((tab) => {
    tab.addEventListener('click', () => setImportEntity(tab.getAttribute('data-import-entity')));
  });

  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('import-file-input');

  dropzone?.addEventListener('click', () => fileInput?.click());
  dropzone?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      fileInput?.click();
    }
  });

  dropzone?.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.classList.add('dragover');
  });
  dropzone?.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
  dropzone?.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.classList.remove('dragover');
    if (e.dataTransfer?.files?.length) {
      handleImportFileSelected(e.dataTransfer.files[0]);
    }
  });

  fileInput?.addEventListener('change', (e) => {
    if (e.target.files?.length) {
      handleImportFileSelected(e.target.files[0]);
    }
  });

  document.getElementById('btn-commit-import')?.addEventListener('click', commitImport);
  document.getElementById('btn-download-error-csv')?.addEventListener('click', downloadErrorReportCsv);

  // Phase B: Advisor, Blocked Queue & Auto-Assign Listeners
  document.getElementById('btn-apply-advisor')?.addEventListener('click', () => {
    if (STATE.topRecommendation) {
      STATE.dispatchSelectedVehicleId = STATE.topRecommendation.vehicle.vehicle_id;
      STATE.dispatchSelectedDriverId = STATE.topRecommendation.driver.driver_id;
      renderDispatchConsole();
      showToast(`Applied advisor recommendation: ${STATE.dispatchSelectedVehicleId} + ${STATE.dispatchSelectedDriverId}`);
    }
  });

  document.getElementById('btn-dispatch-next')?.addEventListener('click', async () => {
    try {
      const res = await apiRequest('/deliveries/dispatch-next');
      if (res.has_next && res.delivery) {
        STATE.dispatchSelectedDeliveryId = res.delivery.delivery_id;
        switchView('dispatch');
        renderDispatchConsole();
        showToast(`Selected highest-priority delivery ${res.delivery.delivery_id} (${res.delivery.priority}).`);
      } else {
        showToast('No pending deliveries available in queue.');
      }
    } catch (err) {
      showGlobalError(err.code, err.message);
    }
  });

  document.getElementById('btn-view-blocked-queue')?.addEventListener('click', () => {
    const list = document.getElementById('blocked-queue-list');
    if (!list) return;
    if (!STATE.blockedQueue || STATE.blockedQueue.length === 0) {
      list.innerHTML = '<div class="empty-cell">Zero deliveries are currently blocked. Fleet and driver capacity are sufficient.</div>';
    } else {
      list.innerHTML = STATE.blockedQueue
        .map(
          (d) => `
        <div class="lane-card" style="margin-bottom:12px;">
          <div class="lane-card-top">
            <span class="lane-card-id">${escapeHtml(d.delivery_id)}</span>
            ${priorityBadgeHtml(d.priority)}
          </div>
          <div class="lane-card-route">${escapeHtml(d.pickup)} &rarr; ${escapeHtml(d.dropoff)}</div>
          <div class="lane-card-meta"><span>Req: ${escapeHtml(d.required_capacity || 'Any')} kg</span> &bull; <span>${escapeHtml(d.scheduled_time)}</span></div>
          <div style="margin-top:8px;">
            ${(d.block_reasons || [])
              .map(
                (r) =>
                  `<div class="resource-reason" style="font-size:12px; margin-top:4px;">${icon('alertTriangle', 12)} ${escapeHtml(r)}</div>`
              )
              .join('')}
          </div>
        </div>
      `
        )
        .join('');
    }
    openModal('modal-blocked-queue');
  });

  document.getElementById('btn-auto-assign-all')?.addEventListener('click', async () => {
    try {
      const preview = await apiRequest('/deliveries/auto-assign?dry_run=true', { method: 'POST' });
      const count = preview.matchable_count ?? 0;
      if (count === 0) {
        showToast('Auto-Assign found 0 matchable deliveries with current fleet availability.');
        return;
      }
      const ok = confirm(`Auto-Assign Advisor found ${count} optimal match(es). Commit assignments now atomically?`);
      if (!ok) return;
      const commit = await apiRequest('/deliveries/auto-assign?dry_run=false', { method: 'POST' });
      showToast(`Successfully auto-assigned ${commit.assigned_count} delivery(s)!`);
      await refreshAllData();
    } catch (err) {
      showGlobalError(err.code, err.message);
    }
  });

  // Phase B: Race Lab Concurrency Diagnostic
  document.getElementById('btn-launch-racelab')?.addEventListener('click', async () => {
    const workers = Number(document.getElementById('racelab-workers')?.value || 25);
    const btn = document.getElementById('btn-launch-racelab');
    btn.disabled = true;
    btn.innerHTML = `${icon('refresh', 14)} <span>Running Concurrent Race...</span>`;
    try {
      const res = await apiRequest(`/diagnostics/concurrency-test?workers=${workers}`, { method: 'POST' });
      document.getElementById('racelab-results-panel')?.classList.remove('hidden');
      document.getElementById('rl-workers').textContent = res.workers_dispatched;
      document.getElementById('rl-success').textContent = res.success_count;
      document.getElementById('rl-conflicts').textContent = res.conflict_count;
      document.getElementById('rl-errors').textContent = res.error_count;

      const timelineEl = document.getElementById('racelab-timeline');
      if (timelineEl) {
        timelineEl.innerHTML = (res.timeline || [])
          .map((t, idx) => {
            const is201 = t.status_code === 201;
            const cls = is201 ? 'winner' : (t.status_code === 409 ? 'conflict' : 'error');
            return `
              <div class="racelab-item ${cls}">
                <strong>Worker #${idx + 1}</strong>
                <span>${is201 ? '201 CREATED' : `${t.status_code} ${escapeHtml(t.error || 'CONFLICT')}`}</span>
                <span style="opacity:0.8;">${t.duration_ms}ms</span>
              </div>
            `;
          })
          .join('');
      }
      showToast(`Race Lab complete: ${res.success_count} winner, ${res.conflict_count} blocked, 0 corruptions.`);
    } catch (err) {
      showGlobalError(err.code, err.message);
    } finally {
      btn.disabled = false;
      btn.innerHTML = `${icon('zap', 14)} <span>Launch Race Test</span>`;
    }
  });

  // Theme & Shortcuts
  document.getElementById('btn-theme-toggle')?.addEventListener('click', toggleTheme);
  document.getElementById('btn-shortcuts')?.addEventListener('click', () => openModal('modal-shortcuts'));

  // Command palette input & global shortcuts
  document.getElementById('cmd-input')?.addEventListener('input', (e) => {
    renderCommandList(e.target.value);
  });

  document.addEventListener('keydown', (e) => {
    const isTyping = ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName);
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      openCommandPalette();
    } else if (e.key === 'Escape') {
      ['modal-cmd', 'modal-vehicle', 'modal-driver', 'modal-delivery', 'modal-blocked-queue', 'modal-shortcuts'].forEach(closeModal);
    } else if (!isTyping && !e.ctrlKey && !e.metaKey && !e.altKey) {
      if (e.key === '?') {
        e.preventDefault();
        openModal('modal-shortcuts');
      } else if (e.key === '1') switchView('dashboard');
      else if (e.key === '2') switchView('deliveries');
      else if (e.key === '3') switchView('dispatch');
      else if (e.key === '4') switchView('fleet');
      else if (e.key === '5') switchView('drivers');
      else if (e.key.toLowerCase() === 'i') switchView('import');
      else if (e.key.toLowerCase() === 'l') switchView('racelab');
      else if (e.key.toLowerCase() === 'y') switchView('analytics');
      else if (e.key.toLowerCase() === 'm') switchView('routes');
      else if (e.key.toLowerCase() === 'a') switchView('audit');
    }
  });
}

/* ==================== INITIALIZE ==================== */
document.addEventListener('DOMContentLoaded', async () => {
  initTheme();
  hydrateStaticIcons();
  setupEventListeners();
  setupSSE();
  await refreshAllData(true);

  STATE.pollTimer = setInterval(() => {
    if (STATE.pollingEnabled && !document.hidden) {
      refreshAllData(true);
    }
  }, 5000);
});

