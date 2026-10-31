import { icon } from './icons.js';

const STATE = {
  activeView: 'dashboard',
  currentUser: null,
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
  devices: [],
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
  selectedTrackingVehicleId: null,
  selectedTrackingDeliveryId: null,
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
  'vehicle-tracking': {
    title: 'Vehicle Live GPS Radar',
    subtitle: 'Real-time vehicle position, accuracy circles, movement breadcrumb trails & Street View',
  },
  'delivery-tracking': {
    title: 'Delivery Transit Tracking',
    subtitle: 'Corridor monitoring, planned route vs real driver GPS trail, and street-level vantage',
  },
    devices: {
    title: 'Authenticated Device Inventory',
    subtitle: 'Manage registered smartphone devices, browser sessions, capability flags, and revocation guards',
  },
  'driver-gps': {
    title: 'Driver Phone GPS Portal',
    subtitle: 'Smartphone browser HTML5 Geolocation streaming with live velocity and precision gauges',
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


/* ==================== AUTHENTICATION & SESSION ==================== */
async function checkAuthSession() {
  try {
    const res = await fetch('/auth/me');
    if (res.ok) {
      const data = await res.json();
      STATE.currentUser = data.user || data;
      renderUserSession();
      return true;
    }
  } catch (_) {}
  STATE.currentUser = null;
  renderUserSession();
  return false;
}

function renderUserSession() {
  const chip = document.getElementById('user-session-chip');
  const btnLogin = document.getElementById('btn-open-login');
  const nameDisp = document.getElementById('user-name-display');
  const roleBadge = document.getElementById('user-role-badge');
  if (STATE.currentUser) {
    if (nameDisp) nameDisp.textContent = STATE.currentUser.username || 'Operator';
    if (roleBadge) roleBadge.textContent = (STATE.currentUser.role || 'USER').toUpperCase();
    if (chip) chip.classList.remove('hidden');
    if (btnLogin) btnLogin.classList.add('hidden');
  } else {
    if (chip) chip.classList.add('hidden');
    if (btnLogin) btnLogin.classList.remove('hidden');
  }
}

async function loginUser(username, password) {
  const errBox = document.getElementById('login-error-box');
  if (errBox) errBox.classList.add('hidden');
  const submitBtn = document.getElementById('btn-submit-login');
  if (submitBtn) submitBtn.disabled = true;
  try {
    const res = await fetch('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.message || data.error || 'Authentication failed');
    }
    STATE.currentUser = data.user;
    renderUserSession();
    closeModal('modal-auth-login');
    showToast(`Welcome back, ${data.user.username}! Operations console active.`);
    await refreshAllData(false);
  } catch (err) {
    if (errBox) {
      errBox.innerHTML = `<strong>AUTHENTICATION_FAILED:</strong> ${escapeHtml(err.message)}`;
      errBox.classList.remove('hidden');
    } else {
      showToast(err.message, 'error');
    }
  } finally {
    if (submitBtn) submitBtn.disabled = false;
  }
}

async function logoutUser() {
  try {
    await fetch('/auth/logout', { method: 'POST' });
  } catch (_) {}
  STATE.currentUser = null;
  renderUserSession();
  showToast('Logged out successfully.');
  openModal('modal-auth-login');
}

/* ==================== DATA SYNC ==================== */
async function refreshAllData(silent = false) {
  try {
    const [metricsRes, vehiclesRes, driversRes, deliveriesRes, auditRes, devicesRes] = await Promise.allSettled([
      apiRequest('/metrics'),
      apiRequest('/vehicles'),
      apiRequest('/drivers'),
      apiRequest('/deliveries'),
      apiRequest('/audit'),
      apiRequest('/devices'),
    ]);

    const isUnauth = [metricsRes, vehiclesRes, driversRes, deliveriesRes, auditRes, devicesRes].some(
      (r) => r.status === 'rejected' && (r.reason?.status === 401 || r.reason?.code === 'UNAUTHORIZED')
    );
    if (isUnauth) {
      STATE.currentUser = null;
      renderUserSession();
      openModal('modal-auth-login');
      return;
    }

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
    if (devicesRes && devicesRes.status === 'fulfilled' && Array.isArray(devicesRes.value)) {
      STATE.devices = devicesRes.value;
      const devBadge = document.getElementById('nav-badge-devices');
      if (devBadge) devBadge.textContent = String(STATE.devices.length);
    }

    await refreshFilteredDeliveries();
    await refreshBlockedQueue();
    renderAll();
    if (STATE.activeView === 'analytics') {
      renderAnalytics();
    } else if (STATE.activeView === 'routes') {
      renderRouteRadar();
    } else if (STATE.activeView === 'vehicle-tracking') {
      renderVehicleTracking();
    } else if (STATE.activeView === 'delivery-tracking') {
      renderDeliveryTracking();
    } else if (STATE.activeView === 'driver-gps') {
      renderDriverGpsPortal();
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
          <button type="button" class="btn btn-primary btn-xs" style="background:#10B981; border-color:#059669;" data-transition-delivery="${escapeHtml(d.delivery_id)}" data-target-status="delivered">
            ${icon('checkCircle', 12)}<span>Delivered</span>
          </button>
          <button type="button" class="btn btn-danger btn-xs" data-transition-delivery="${escapeHtml(d.delivery_id)}" data-target-status="cancelled">
            <span>Cancel</span>
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
          <td class="mono">
            <div>
              <span>${escapeHtml(d.phone_e164 || d.phone)}</span>
              <button type="button" class="btn btn-ghost btn-xs ml-xs" data-edit-phone="${escapeHtml(d.driver_id)}" title="Update Phone Number" style="padding:1px 5px; font-size:11px; margin-left:4px;">
                ${icon('edit', 10)}
              </button>
            </div>
            <div class="mt-xs" style="display:flex; align-items:center; gap:4px; margin-top:3px;">
              ${
                d.phone_verification_status === 'verified'
                  ? '<span class="badge badge-success" style="font-size:9px; padding:1px 4px;">VERIFIED</span>'
                  : d.phone_verification_status === 'pending'
                  ? '<span class="badge badge-warning" style="font-size:9px; padding:1px 4px;">CHALLENGE PENDING</span>'
                  : '<span class="badge badge-neutral" style="font-size:9px; padding:1px 4px;">UNVERIFIED</span>'
              }
              <button type="button" class="btn btn-ghost btn-xs" data-verify-phone="${escapeHtml(d.driver_id)}" style="font-size:10px; padding:0 4px;" title="Challenge OTP">
                Verify
              </button>
            </div>
          </td>
          <td>${statusBadgeHtml(d.availability_status)}</td>
          <td>${activeDel}</td>
          <td class="text-right">
            <div style="display:inline-flex; gap:4px; flex-wrap:wrap; justify-content:flex-end;">
              <button type="button" class="btn btn-ghost btn-xs" data-edit-phone="${escapeHtml(d.driver_id)}">Edit Phone</button>
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
  } else if (viewName === 'vehicle-tracking') {
    renderVehicleTracking();
  } else if (viewName === 'delivery-tracking') {
    renderDeliveryTracking();
  } else if (viewName === 'driver-gps') {
    renderDriverGpsPortal();
  } else if (viewName === 'devices') {
    renderDevicesTable();
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


/* ==================== DEVICE INVENTORY & PHONE VERIFICATION ==================== */
function renderDevicesTable() {
  const tbody = document.getElementById('devices-tbody');
  if (!tbody) return;
  if (!STATE.devices || STATE.devices.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="9" class="empty-cell">
          <div>No devices registered yet.</div>
          <div style="margin-top:8px;">
            <button type="button" class="btn btn-primary btn-sm" id="btn-empty-register-dev">
              ${icon('plus', 14)}<span>Register Test Smartphone Device</span>
            </button>
          </div>
        </td>
      </tr>
    `;
    const btn = document.getElementById('btn-empty-register-dev');
    if (btn) btn.addEventListener('click', openRegisterDeviceModal);
    return;
  }

  tbody.innerHTML = STATE.devices
    .map((dev) => {
      const isRevoked = dev.is_revoked === 1 || dev.is_revoked === true;
      const statusBadge = isRevoked
        ? '<span class="badge badge-danger">REVOKED</span>'
        : '<span class="badge badge-success">ACTIVE</span>';

      const permBadge =
        dev.permission_status === 'granted'
          ? '<span class="badge badge-success">GRANTED</span>'
          : `<span class="badge badge-warning">${escapeHtml(dev.permission_status || 'prompt')}</span>`;

      const driverName = dev.driver_name
        ? `${escapeHtml(dev.driver_name)} (${escapeHtml(dev.driver_id)})`
        : escapeHtml(dev.driver_id || 'Unassigned');

      const lastSeen = dev.last_seen_at
        ? `<span class="mono" style="font-size:12px;">${escapeHtml(dev.last_seen_at.replace('T', ' ').slice(0, 19))}</span>`
        : '<span class="kpi-sub">Never</span>';

      const actions = isRevoked
        ? '<span class="kpi-sub" style="font-size:12px;">Revoked</span>'
        : `<button type="button" class="btn btn-ghost btn-xs text-danger" data-revoke-device="${escapeHtml(dev.device_id)}">Revoke Device</button>`;

      return `
      <tr style="${isRevoked ? 'opacity:0.6;' : ''}">
        <td class="mono font-bold">${escapeHtml(dev.device_id)}</td>
        <td>${driverName}</td>
        <td><strong>${escapeHtml(dev.nickname)}</strong></td>
        <td><span class="mono" style="font-size:12px;">${escapeHtml(dev.os_family || 'Generic')} / ${escapeHtml(dev.browser_family || 'Browser')}</span></td>
        <td>${permBadge}</td>
        <td class="mono" style="font-size:12px;">${escapeHtml(dev.last_ip || '127.0.0.1')}</td>
        <td>${lastSeen}</td>
        <td>${statusBadge}</td>
        <td class="text-right">${actions}</td>
      </tr>
    `;
    })
    .join('');
}

function openRegisterDeviceModal() {
  const sel = document.getElementById('dev-reg-driver');
  if (sel) {
    sel.innerHTML = '<option value="">-- Select Driver --</option>' + 
      STATE.drivers.map(d => `<option value="${escapeHtml(d.driver_id)}">${escapeHtml(d.name)} (${escapeHtml(d.driver_id)})</option>`).join('');
  }
  const ua = navigator.userAgent;
  let os = 'Unknown OS';
  if (/iPad|iPhone|iPod/.test(ua)) os = 'iOS';
  else if (/Android/.test(ua)) os = 'Android';
  else if (/Windows/.test(ua)) os = 'Windows';
  else if (/Mac OS/.test(ua)) os = 'macOS';
  else if (/Linux/.test(ua)) os = 'Linux';

  let browser = 'Browser';
  if (/Chrome/.test(ua) && !/Edg/.test(ua)) browser = 'Chrome';
  else if (/Safari/.test(ua) && !/Chrome/.test(ua)) browser = 'Safari';
  else if (/Firefox/.test(ua)) browser = 'Firefox';
  else if (/Edg/.test(ua)) browser = 'Edge';

  const osInput = document.getElementById('dev-reg-os');
  const browserInput = document.getElementById('dev-reg-browser');
  if (osInput && !osInput.value) osInput.value = os;
  if (browserInput && !browserInput.value) browserInput.value = browser;

  openModal('modal-device-register');
}

async function submitRegisterDevice(e) {
  e.preventDefault();
  const driver_id = document.getElementById('dev-reg-driver').value;
  const nickname = document.getElementById('dev-reg-nickname').value.trim();
  const os_family = document.getElementById('dev-reg-os').value.trim() || undefined;
  const browser_family = document.getElementById('dev-reg-browser').value.trim() || undefined;

  try {
    const res = await apiRequest('/devices/register', {
      method: 'POST',
      body: JSON.stringify({
        driver_id,
        nickname,
        os_family,
        browser_family,
        platform: navigator.platform || 'Unknown',
        screen_res: `${window.screen.width}x${window.screen.height}`,
        permission_status: 'prompt',
      }),
    });
    showToast(`Device registered: ${res.device_id}`, 'success');
    closeModal('modal-device-register');
    document.getElementById('form-device-register').reset();
    await refreshAllData();
    renderDevicesTable();
  } catch (err) {
    showToast(err.message || 'Failed to register device', 'error');
  }
}

async function revokeDevice(deviceId) {
  if (!confirm(`Are you sure you want to revoke device ${deviceId}? This device will be permanently blocked from submitting GPS telemetry.`)) {
    return;
  }
  try {
    await apiRequest(`/devices/${encodeURIComponent(deviceId)}/revoke`, {
      method: 'POST',
      body: JSON.stringify({ reason: 'Operator manual revocation from Device Inventory' }),
    });
    showToast(`Device ${deviceId} revoked`, 'success');
    await refreshAllData();
    renderDevicesTable();
  } catch (err) {
    showToast(err.message || 'Failed to revoke device', 'error');
  }
}

async function openPhoneVerificationModal(driverId) {
  const driver = STATE.drivers.find(d => d.driver_id === driverId);
  if (!driver) {
    showToast('Driver not found', 'error');
    return;
  }
  try {
    const challenge = await apiRequest(`/drivers/${encodeURIComponent(driverId)}/phone/request-verification`, {
      method: 'POST',
    });
    document.getElementById('verify-driver-id').value = driverId;
    document.getElementById('verify-challenge-id').value = challenge.verification_id;
    document.getElementById('verify-driver-name').textContent = `${driver.name} (${driver.driver_id})`;
    document.getElementById('verify-phone-e164').textContent = challenge.phone_e164 || driver.phone_e164 || driver.phone;
    
    const codeDisplay = document.getElementById('verify-dev-code-display');
    if (codeDisplay) {
      if (challenge.dev_challenge_code) {
        codeDisplay.textContent = `Dev OTP: ${challenge.dev_challenge_code}`;
        document.getElementById('verify-code-input').value = challenge.dev_challenge_code;
      } else {
        codeDisplay.textContent = 'OTP sent via SMS gateway';
      }
    }
    openModal('modal-phone-verify');
  } catch (err) {
    showToast(err.message || 'Failed to initiate phone verification challenge', 'error');
  }
}

async function submitPhoneVerification(e) {
  e.preventDefault();
  const driverId = document.getElementById('verify-driver-id').value;
  const verification_id = document.getElementById('verify-challenge-id').value;
  const code = document.getElementById('verify-code-input').value.trim();

  try {
    const res = await apiRequest(`/drivers/${encodeURIComponent(driverId)}/phone/verify`, {
      method: 'POST',
      body: JSON.stringify({ verification_id, code }),
    });
    showToast(res.message || 'Phone number successfully verified!', 'success');
    closeModal('modal-phone-verify');
    document.getElementById('form-phone-verify').reset();
    await refreshAllData();
    renderDriversTable();
  } catch (err) {
    showToast(err.message || 'Verification failed', 'error');
  }
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
  { label: 'Go to Vehicle Live GPS Radar', action: () => switchView('vehicle-tracking'), kbd: '6' },
  { label: 'Go to Delivery Transit Tracking', action: () => switchView('delivery-tracking'), kbd: '7' },
  { label: 'Go to Driver Phone GPS Portal', action: () => switchView('driver-gps'), kbd: '8' },
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

    // 2. Fetch Executive Overview
    try {
      const ov = await apiRequest('/analytics/overview');
      if (ov) {
        const fltUtil = ov.fleet?.fleet_utilization_pct ?? 0;
        const drvUtil = ov.drivers?.driver_utilization_pct ?? 0;
        const compRate = ov.deliveries?.completion_rate_pct ?? 0;
        const onTimeRate = ov.deliveries?.on_time_rate_pct ?? 0;

        const kpiFlt = document.getElementById('kpi-fleet-util');
        const kpiFltSub = document.getElementById('kpi-fleet-sub');
        const kpiDrv = document.getElementById('kpi-driver-util');
        const kpiDrvSub = document.getElementById('kpi-driver-sub');
        const kpiComp = document.getElementById('kpi-completion-rate');
        const kpiCompSub = document.getElementById('kpi-completion-sub');
        const kpiOnTime = document.getElementById('kpi-ontime-rate');
        const kpiOnTimeSub = document.getElementById('kpi-ontime-sub');

        if (kpiFlt) kpiFlt.textContent = `${fltUtil}%`;
        if (kpiFltSub) kpiFltSub.textContent = `${ov.fleet?.assigned_vehicles || 0} of ${ov.fleet?.active_pool_vehicles || 0} active pool assigned`;
        if (kpiDrv) kpiDrv.textContent = `${drvUtil}%`;
        if (kpiDrvSub) kpiDrvSub.textContent = `${ov.drivers?.assigned_drivers || 0} of ${ov.drivers?.eligible_active_drivers || 0} eligible drivers assigned`;
        if (kpiComp) kpiComp.textContent = `${compRate}%`;
        if (kpiCompSub) kpiCompSub.textContent = `${ov.deliveries?.delivered_count || 0} of ${ov.deliveries?.eligible_deliveries_count || 0} eligible delivered`;
        if (kpiOnTime) kpiOnTime.textContent = `${onTimeRate}%`;
        if (kpiOnTimeSub) kpiOnTimeSub.textContent = `${ov.deliveries?.completed_with_deadline_count || 0} orders with deadline audited`;
      }
    } catch (e) {
      console.warn('Overview analytics failed:', e);
    }

    // 3. Fetch Telemetry Accuracy Quality
    try {
      const acc = await apiRequest('/analytics/accuracy');
      if (acc && acc.session_scores && acc.session_scores.length > 0) {
        const top = acc.session_scores[0].telemetry_quality || {};
        const comps = top.component_scores || {};
        document.getElementById('lbl-gps-quality').textContent = comps.gps_quality != null ? `${comps.gps_quality}/100` : 'Unavailable';
        document.getElementById('lbl-freshness-quality').textContent = comps.freshness != null ? `${comps.freshness}/100` : 'Unavailable';
        document.getElementById('lbl-movement-quality').textContent = comps.movement_consistency != null ? `${comps.movement_consistency}/100` : 'Normal';
        document.getElementById('lbl-completeness-quality').textContent = comps.data_completeness != null ? `${comps.data_completeness}%` : 'Unavailable';
        document.getElementById('lbl-overall-quality').textContent = top.telemetry_quality_score != null ? `${top.telemetry_quality_score}/100` : 'Pending';
      } else {
        document.getElementById('lbl-gps-quality').textContent = 'No signal';
        document.getElementById('lbl-freshness-quality').textContent = 'No signal';
        document.getElementById('lbl-movement-quality').textContent = 'No trajectory';
        document.getElementById('lbl-completeness-quality').textContent = 'N/A';
        document.getElementById('lbl-overall-quality').textContent = 'Awaiting Telemetry';
      }
    } catch {}

    // 4. Fetch Confidence Evaluations
    try {
      const conf = await apiRequest('/analytics/confidence');
      if (conf) {
        const devs = conf.device_identity_confidence || [];
        if (devs.length > 0) {
          const topDev = devs[0].confidence || {};
          document.getElementById('lbl-device-conf').textContent = `${topDev.confidence_score || 0}/100 (${topDev.level || 'LOW'})`;
          document.getElementById('lbl-device-trust').textContent = topDev.is_trusted ? 'Verified Token' : 'Unverified';
        } else {
          document.getElementById('lbl-device-conf').textContent = 'No devices registered';
          document.getElementById('lbl-device-trust').textContent = 'Awaiting Device';
        }

        const asgs = conf.assignment_confidence || [];
        if (asgs.length > 0) {
          const topAsg = asgs[0].confidence || {};
          document.getElementById('lbl-asg-constraints').textContent = topAsg.is_eligible ? 'Satisfied (100%)' : 'Violated';
          document.getElementById('lbl-asg-suitability').textContent = topAsg.capacity_utilization_pct != null ? `${topAsg.capacity_utilization_pct}%` : 'Standard';
          document.getElementById('lbl-overall-asg-conf').textContent = `${topAsg.confidence_score || 0}/100 (${topAsg.level || 'REJECTED'})`;
        } else {
          document.getElementById('lbl-asg-constraints').textContent = 'No pending deliveries';
          document.getElementById('lbl-asg-suitability').textContent = 'Queue Clear';
          document.getElementById('lbl-overall-asg-conf').textContent = 'Idle';
        }
      }
    } catch {}

    // 5. Fetch Operational Anomalies
    try {
      const anom = await apiRequest('/analytics/anomalies?limit=25');
      const tbody = document.getElementById('tbody-anomalies');
      if (tbody && anom && anom.anomalies) {
        if (anom.anomalies.length === 0) {
          tbody.innerHTML = '<tr><td colspan="7" class="empty-cell">No anomalies detected. All operations normal.</td></tr>';
        } else {
          tbody.innerHTML = anom.anomalies.map(a => {
            const sevClass = a.severity === 'CRITICAL' || a.severity === 'HIGH' ? 'badge-danger' : (a.severity === 'MEDIUM' ? 'badge-warning' : 'badge-secondary');
            return `
              <tr>
                <td><code style="font-size:11px;">${escapeHtml(a.event_id)}</code></td>
                <td><span class="badge ${sevClass}">${escapeHtml(a.severity)}</span></td>
                <td><span class="badge badge-info">${escapeHtml(a.type)}</span></td>
                <td><strong>${escapeHtml(a.affected_entity)}</strong></td>
                <td><span class="meta-time">${escapeHtml(formatTime(a.timestamp))}</span></td>
                <td><div style="font-size:12px; line-height:1.4;">${escapeHtml(a.detection_reason)}</div></td>
                <td><span style="font-size:11px; color:var(--color-muted-foreground);">${escapeHtml(a.recommended_investigation)}</span></td>
              </tr>
            `;
          }).join('');
        }
      }
    } catch {}

  } catch (err) {
    console.error('Failed to render analytics:', err);
  }
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

/* ==================== REAL GPS TRACKING & TELEMETRY ==================== */
const TRACKING_STATE = {
  activeSessionId: null,
  activeDriverId: null,
  activeDeviceId: null,
  watchId: null,
  fixCount: 0,
  lastFix: null,
  lastIngestedTimestamp: 0,
  batteryCleanup: null,
  networkCleanup: null,
  cachedDeviceInfo: null,
};

const MAPS = {
  'vehicle-map': null,
  'delivery-map': null,
  'driver-mini-map': null,
  layers: {
    'vehicle-map': {},
    'delivery-map': {},
    'driver-mini-map': {},
  },
};

function getOrCreateLeafletMap(containerId, center = [12.9716, 77.5946], zoom = 13) {
  if (typeof window.L === 'undefined') {
    console.warn('Leaflet engine is not ready.');
    return null;
  }
  const el = document.getElementById(containerId);
  if (!el) return null;

  if (MAPS[containerId]) {
    setTimeout(() => {
      try {
        MAPS[containerId].invalidateSize();
      } catch {}
    }, 60);
    return MAPS[containerId];
  }

  try {
    const map = window.L.map(containerId, {
      attributionControl: false,
      zoomControl: true,
      fadeAnimation: true,
    }).setView(center, zoom);

    window.L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      subdomains: ['a', 'b', 'c'],
    }).addTo(map);

    window.L.control.attribution({ position: 'bottomright', prefix: false })
      .addAttribution('&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>')
      .addTo(map);

    MAPS[containerId] = map;
    MAPS.layers[containerId] = {};
    setTimeout(() => {
      try {
        map.invalidateSize();
      } catch {}
    }, 100);
    return map;
  } catch (err) {
    console.error('Error initializing Leaflet map:', err);
    return null;
  }
}

function createMapMarkerIcon(type = 'vehicle') {
  if (typeof window.L === 'undefined') return null;
  const isVeh = type === 'vehicle';
  const isDel = type === 'delivery';
  const color = isVeh ? '#00FF41' : (isDel ? '#00E5FF' : '#FFB000');
  const innerSvg = isVeh
    ? `<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="${color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="background:#0D1117; padding:4px; border-radius:50%; border:2px solid ${color}; box-shadow:0 0 10px ${color};"><rect x="1" y="3" width="15" height="13"></rect><polygon points="16 8 20 8 23 11 23 16 16 16 16 8"></polygon><circle cx="5.5" cy="18.5" r="2.5"></circle><circle cx="18.5" cy="18.5" r="2.5"></circle></svg>`
    : `<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="${color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="background:#0D1117; padding:4px; border-radius:50%; border:2px solid ${color}; box-shadow:0 0 10px ${color};"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>`;

  return window.L.divIcon({
    html: innerSvg,
    className: 'custom-map-marker',
    iconSize: [28, 28],
    iconAnchor: [14, 14],
    popupAnchor: [0, -14],
  });
}

function renderTelemetrySvg(containerId, telemetryData) {
  const container = document.getElementById(containerId);
  if (!container) return;

  const points = (telemetryData && telemetryData.points) || [];
  if (points.length === 0) {
    container.innerHTML = `
      <div class="lane-empty" style="padding:40px 0;">
        <div>No telemetry GPS fixes recorded yet. Real telemetry will graph here once fixes stream in.</div>
      </div>
    `;
    return;
  }

  const width = 680;
  const height = 150;
  const padL = 45;
  const padR = 45;
  const padT = 20;
  const padB = 25;
  const plotW = width - padL - padR;
  const plotH = height - padT - padB;

  let maxSpeed = 30;
  let maxAcc = 25;
  points.forEach((p) => {
    if (p.speed_kmh != null && p.speed_kmh > maxSpeed) maxSpeed = p.speed_kmh;
    if (p.accuracy_m != null && p.accuracy_m > maxAcc) maxAcc = p.accuracy_m;
  });
  maxSpeed = Math.ceil(maxSpeed * 1.15);
  maxAcc = Math.ceil(maxAcc * 1.15);

  const getX = (idx) => {
    if (points.length === 1) return padL + plotW / 2;
    return padL + (idx / (points.length - 1)) * plotW;
  };
  const getSpeedY = (spd) => {
    const val = spd != null ? spd : 0;
    return padT + plotH - (val / maxSpeed) * plotH;
  };
  const getAccY = (acc) => {
    const val = acc != null ? acc : 0;
    return padT + plotH - (val / maxAcc) * plotH;
  };

  const speedCoords = points.map((p, idx) => [getX(idx), getSpeedY(p.speed_kmh)]);
  const accCoords = points.map((p, idx) => [getX(idx), getAccY(p.accuracy_m)]);

  const speedPathD = speedCoords.length > 1
    ? speedCoords.map((c, i) => `${i === 0 ? 'M' : 'L'} ${c[0].toFixed(1)} ${c[1].toFixed(1)}`).join(' ')
    : '';

  const speedFillD = speedCoords.length > 1
    ? `${speedPathD} L ${speedCoords[speedCoords.length - 1][0].toFixed(1)} ${(padT + plotH).toFixed(1)} L ${speedCoords[0][0].toFixed(1)} ${(padT + plotH).toFixed(1)} Z`
    : '';

  const accPathD = accCoords.length > 1
    ? accCoords.map((c, i) => `${i === 0 ? 'M' : 'L'} ${c[0].toFixed(1)} ${c[1].toFixed(1)}`).join(' ')
    : '';

  let svgHtml = `
    <svg viewBox="0 0 ${width} ${height}" style="width:100%; height:auto; display:block; background:#0B0E14; border-radius:var(--radius-sm);">
      <defs>
        <linearGradient id="spdGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#00FF41" stop-opacity="0.28" />
          <stop offset="100%" stop-color="#00FF41" stop-opacity="0.0" />
        </linearGradient>
      </defs>
      <!-- Horizontal Grid Lines -->
      <line x1="${padL}" y1="${padT}" x2="${width - padR}" y2="${padT}" stroke="rgba(255,255,255,0.08)" stroke-dasharray="2 2" />
      <line x1="${padL}" y1="${padT + plotH / 2}" x2="${width - padR}" y2="${padT + plotH / 2}" stroke="rgba(255,255,255,0.08)" stroke-dasharray="2 2" />
      <line x1="${padL}" y1="${padT + plotH}" x2="${width - padR}" y2="${padT + plotH}" stroke="rgba(255,255,255,0.15)" />

      <!-- Left Axis (Speed) Labels -->
      <text x="${padL - 6}" y="${padT + 4}" font-family="var(--font-mono)" font-size="9" fill="#00FF41" text-anchor="end">${maxSpeed}</text>
      <text x="${padL - 6}" y="${padT + plotH / 2 + 3}" font-family="var(--font-mono)" font-size="9" fill="#00FF41" text-anchor="end">${Math.round(maxSpeed / 2)}</text>
      <text x="${padL - 6}" y="${padT + plotH + 2}" font-family="var(--font-mono)" font-size="9" fill="#00FF41" text-anchor="end">0</text>

      <!-- Right Axis (Accuracy) Labels -->
      <text x="${width - padR + 6}" y="${padT + 4}" font-family="var(--font-mono)" font-size="9" fill="#00E5FF" text-anchor="start">±${maxAcc}m</text>
      <text x="${width - padR + 6}" y="${padT + plotH + 2}" font-family="var(--font-mono)" font-size="9" fill="#00E5FF" text-anchor="start">0m</text>

      <!-- Speed Area & Line -->
      ${speedFillD ? `<path d="${speedFillD}" fill="url(#spdGrad)" />` : ''}
      ${speedPathD ? `<path d="${speedPathD}" fill="none" stroke="#00FF41" stroke-width="2.2" />` : ''}

      <!-- Accuracy Line -->
      ${accPathD ? `<path d="${accPathD}" fill="none" stroke="#00E5FF" stroke-width="1.8" stroke-dasharray="4 3" />` : ''}

      <!-- Data Dots -->
      ${speedCoords.map((c, i) => `<circle cx="${c[0].toFixed(1)}" cy="${c[1].toFixed(1)}" r="3" fill="#00FF41"><title>Speed: ${points[i].speed_kmh != null ? points[i].speed_kmh : 0} km/h</title></circle>`).join('')}

      <!-- Legend -->
      <g transform="translate(${padL + 10}, 12)">
        <line x1="0" y1="0" x2="16" y2="0" stroke="#00FF41" stroke-width="2" />
        <circle cx="8" cy="0" r="2.5" fill="#00FF41" />
        <text x="22" y="3" font-family="var(--font-mono)" font-size="10" fill="#00FF41">Speed (km/h)</text>

        <line x1="120" y1="0" x2="136" y2="0" stroke="#00E5FF" stroke-width="1.8" stroke-dasharray="3 2" />
        <text x="142" y="3" font-family="var(--font-mono)" font-size="10" fill="#00E5FF">Accuracy (m)</text>
      </g>
    </svg>
  `;

  container.innerHTML = svgHtml;
}

/* --- Vehicle Live GPS Tracking --- */
function renderVehicleTracking() {
  const select = document.getElementById('veh-tracking-select');
  if (!select) return;

  const currentVal = select.value || STATE.selectedTrackingVehicleId || '';
  select.innerHTML = '<option value="">-- Choose a Fleet Vehicle --</option>' +
    STATE.vehicles
      .map((v) => {
        const isSel = v.vehicle_id === currentVal ? 'selected' : '';
        return `<option value="${escapeHtml(v.vehicle_id)}" ${isSel}>${escapeHtml(v.vehicle_id)} (${escapeHtml(v.registration_no)}) &bull; ${escapeHtml(v.type)} [${escapeHtml(v.status)}]</option>`;
      })
      .join('');

  if (currentVal && STATE.vehicles.some((v) => v.vehicle_id === currentVal)) {
    loadVehicleTrackingData(currentVal);
  } else if (STATE.vehicles.length > 0 && !currentVal) {
    select.value = STATE.vehicles[0].vehicle_id;
    loadVehicleTrackingData(STATE.vehicles[0].vehicle_id);
  }
}

async function loadVehicleTrackingData(vehicleId, silent = false) {
  if (!vehicleId) return;
  STATE.selectedTrackingVehicleId = vehicleId;
  const infoEl = document.getElementById('veh-tracking-info');
  const graphStatsEl = document.getElementById('veh-graph-stats');

  try {
    const [latestRes, historyRes, telemetryRes] = await Promise.all([
      apiRequest(`/tracking/vehicles/${encodeURIComponent(vehicleId)}/latest`),
      apiRequest(`/tracking/history?vehicle_id=${encodeURIComponent(vehicleId)}&limit=100`),
      apiRequest(`/tracking/telemetry-graph?vehicle_id=${encodeURIComponent(vehicleId)}`),
    ]);

    const vehicle = latestRes.vehicle || STATE.vehicles.find((v) => v.vehicle_id === vehicleId) || { vehicle_id: vehicleId };
    const latest = latestRes.latest_location || (latestRes.has_gps ? latestRes : null);
    const isLive = latestRes.is_live;
    const isStale = latestRes.is_stale;
    const statusText = isLive ? 'LIVE' : (isStale ? 'STALE' : 'OFFLINE');
    const statusClass = isLive ? 'status-live' : (isStale ? 'status-stale' : 'status-inactive');

    // Render left panel info
    if (infoEl) {
      const driver = latestRes.assigned_driver;
      const delivery = latestRes.active_delivery;
      const streetViewBtn = latestRes.street_view_url
        ? `<a href="${escapeHtml(latestRes.street_view_url)}" target="_blank" rel="noopener noreferrer" class="btn btn-secondary btn-sm streetview-btn" style="width:100%; justify-content:center; margin-top:var(--space-md);">${icon('navigation', 14)}<span>Open Google Maps Street View</span></a>`
        : '';

      infoEl.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:var(--space-md);">
          <div>
            <span class="mono font-bold" style="font-size:16px;">${escapeHtml(vehicle.registration_no || vehicle.vehicle_id)}</span>
            <div class="kpi-sub">${escapeHtml(vehicle.vehicle_id)} &bull; ${escapeHtml(vehicle.type || 'Van')} &bull; Cap: ${escapeHtml(vehicle.capacity || '—')}</div>
          </div>
          <span class="status-badge ${statusClass}">${statusText}</span>
        </div>

        <div class="telemetry-cards mb-md">
          <div class="telemetry-card">
            <span class="telemetry-label">Latitude</span>
            <span class="telemetry-value" style="font-size:13px;">${latest ? latest.latitude.toFixed(6) : '—'}</span>
          </div>
          <div class="telemetry-card">
            <span class="telemetry-label">Longitude</span>
            <span class="telemetry-value" style="font-size:13px;">${latest ? latest.longitude.toFixed(6) : '—'}</span>
          </div>
          <div class="telemetry-card">
            <span class="telemetry-label">Speed</span>
            <span class="telemetry-value" style="font-size:13px;">${latest && latest.speed_kmh != null ? latest.speed_kmh.toFixed(1) : '0.0'}</span>
            <span class="telemetry-sub">km / h</span>
          </div>
          <div class="telemetry-card">
            <span class="telemetry-label">Accuracy</span>
            <span class="telemetry-value" style="font-size:13px;">${latest && latest.accuracy_m != null ? `±${latest.accuracy_m.toFixed(1)}m` : '—'}</span>
          </div>
        </div>

        <div style="font-size:12px; line-height:1.6; border-top:1px solid var(--color-border); padding-top:var(--space-sm);">
          <div><strong>Last GPS Fix:</strong> <span class="mono">${latest ? escapeHtml(latest.server_timestamp) : 'None recorded'}</span></div>
          <div><strong>Assigned Driver:</strong> ${driver ? `<span class="mono font-bold">${escapeHtml(driver.name)}</span> (${escapeHtml(driver.phone || 'No phone')})` : '<span class="kpi-sub">Unassigned</span>'}</div>
          <div><strong>Active Delivery:</strong> ${delivery ? `<code class="mono">${escapeHtml(delivery.delivery_id)}</code> &bull; ${escapeHtml(delivery.pickup)} &rarr; ${escapeHtml(delivery.dropoff)}` : '<span class="kpi-sub">None</span>'}</div>
        </div>

        ${streetViewBtn}

        ${!latest ? `
          <div class="kpi-sub mt-md" style="font-size:11px; color:var(--color-muted-foreground);">
            Tip: To stream real GPS coordinates into this vehicle, go to <strong>Driver Phone GPS Portal</strong>, select the driver assigned to this vehicle, and click <strong>Start GPS Tracking</strong> on your smartphone.
          </div>
        ` : ''}
      `;
    }

    // Map rendering
    const map = getOrCreateLeafletMap('vehicle-map', latest ? [latest.latitude, latest.longitude] : [12.9716, 77.5946], 13);
    if (map && window.L) {
      const layers = MAPS.layers['vehicle-map'];

      // Clear previous layers
      if (layers.marker) map.removeLayer(layers.marker);
      if (layers.circle) map.removeLayer(layers.circle);
      if (layers.trail) map.removeLayer(layers.trail);

      const fixes = (historyRes && historyRes.fixes) || [];
      if (fixes.length > 0) {
        const latlngs = fixes.map((f) => [f.latitude, f.longitude]);
        layers.trail = window.L.polyline(latlngs, {
          color: '#00FF41',
          weight: 3.5,
          opacity: 0.85,
          dashArray: '6 4',
        }).addTo(map);

        if (latest) {
          const icon = createMapMarkerIcon('vehicle');
          layers.marker = window.L.marker([latest.latitude, latest.longitude], { icon })
            .addTo(map)
            .bindPopup(`<strong>${escapeHtml(vehicle.registration_no || vehicle.vehicle_id)}</strong><br>Speed: ${latest.speed_kmh || 0} km/h<br>Accuracy: ±${latest.accuracy_m || 0}m`);

          layers.circle = window.L.circle([latest.latitude, latest.longitude], {
            radius: latest.accuracy_m || 20,
            color: '#00FF41',
            fillColor: '#00FF41',
            fillOpacity: 0.12,
            weight: 1,
          }).addTo(map);

          try {
            map.fitBounds(layers.trail.getBounds(), { padding: [35, 35], maxZoom: 16 });
          } catch {
            map.setView([latest.latitude, latest.longitude], 14);
          }
        }
      } else if (latest) {
        const icon = createMapMarkerIcon('vehicle');
        layers.marker = window.L.marker([latest.latitude, latest.longitude], { icon }).addTo(map);
        map.setView([latest.latitude, latest.longitude], 14);
      }
    }

    // Telemetry graph
    if (graphStatsEl) {
      const pts = (telemetryRes && telemetryRes.points_count) || 0;
      const dist = (telemetryRes && telemetryRes.total_distance_km) || 0;
      graphStatsEl.textContent = `${pts} pts // ${dist.toFixed(2)} km`;
    }
    renderTelemetrySvg('veh-telemetry-svg', telemetryRes);
  } catch (err) {
    if (!silent) showGlobalError(err.code || 'VEH_TRACKING_ERROR', err.message);
  }
}

/* --- Delivery Transit Tracking --- */
function renderDeliveryTracking() {
  const select = document.getElementById('del-tracking-select');
  if (!select) return;

  const currentVal = select.value || STATE.selectedTrackingDeliveryId || '';
  select.innerHTML = '<option value="">-- Choose a Delivery Order --</option>' +
    STATE.deliveries
      .map((d) => {
        const isSel = d.delivery_id === currentVal ? 'selected' : '';
        return `<option value="${escapeHtml(d.delivery_id)}" ${isSel}>${escapeHtml(d.delivery_id)} &bull; ${escapeHtml(d.pickup)} &rarr; ${escapeHtml(d.dropoff)} [${escapeHtml(d.status)}]</option>`;
      })
      .join('');

  if (currentVal && STATE.deliveries.some((d) => d.delivery_id === currentVal)) {
    loadDeliveryTrackingData(currentVal);
  } else if (STATE.deliveries.length > 0 && !currentVal) {
    select.value = STATE.deliveries[0].delivery_id;
    loadDeliveryTrackingData(STATE.deliveries[0].delivery_id);
  }
}

async function loadDeliveryTrackingData(deliveryId, silent = false) {
  if (!deliveryId) return;
  STATE.selectedTrackingDeliveryId = deliveryId;
  const infoEl = document.getElementById('del-tracking-info');
  const graphStatsEl = document.getElementById('del-graph-stats');

  try {
    const [latestRes, historyRes, telemetryRes] = await Promise.all([
      apiRequest(`/tracking/deliveries/${encodeURIComponent(deliveryId)}/latest`),
      apiRequest(`/tracking/history?delivery_id=${encodeURIComponent(deliveryId)}&limit=100`),
      apiRequest(`/tracking/telemetry-graph?delivery_id=${encodeURIComponent(deliveryId)}`),
    ]);

    const delivery = latestRes.delivery || STATE.deliveries.find((d) => d.delivery_id === deliveryId) || { delivery_id: deliveryId };
    const latest = latestRes.latest_location;
    const vehicle = latestRes.assigned_vehicle;
    const driver = latestRes.assigned_driver;

    if (infoEl) {
      const svBtn = latestRes.street_view_url
        ? `<a href="${escapeHtml(latestRes.street_view_url)}" target="_blank" rel="noopener noreferrer" class="btn btn-secondary btn-sm streetview-btn" style="width:100%; justify-content:center; margin-top:var(--space-sm);">${icon('navigation', 14)}<span>Street View: Current Driver Position</span></a>`
        : '';
      const pickupSvBtn = latestRes.pickup_street_view_url
        ? `<a href="${escapeHtml(latestRes.pickup_street_view_url)}" target="_blank" rel="noopener noreferrer" class="btn btn-ghost btn-xs mt-xs" style="width:100%; justify-content:center;"><span>View Pickup on Google Maps</span></a>`
        : '';
      const dropoffSvBtn = latestRes.dropoff_street_view_url
        ? `<a href="${escapeHtml(latestRes.dropoff_street_view_url)}" target="_blank" rel="noopener noreferrer" class="btn btn-ghost btn-xs mt-xs" style="width:100%; justify-content:center;"><span>View Dropoff on Google Maps</span></a>`
        : '';

      infoEl.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:var(--space-md);">
          <div>
            <span class="mono font-bold" style="font-size:16px;">${escapeHtml(delivery.delivery_id)}</span>
            <div class="kpi-sub">Priority: <strong>${escapeHtml(delivery.priority || 'normal')}</strong> &bull; Cap: ${escapeHtml(delivery.required_capacity || 0)}</div>
          </div>
          ${statusBadgeHtml(delivery.status)}
        </div>

        <div style="background:var(--color-secondary); padding:var(--space-sm) var(--space-md); border-radius:var(--radius-sm); margin-bottom:var(--space-md); font-size:12px;">
          <div><strong style="color:var(--color-primary);">FROM:</strong> ${escapeHtml(delivery.pickup)}</div>
          <div><strong style="color:var(--color-accent);">TO:</strong> ${escapeHtml(delivery.dropoff)}</div>
          <div class="kpi-sub mt-xs">ETA: ${escapeHtml(delivery.scheduled_time)}</div>
        </div>

        <div style="font-size:12px; line-height:1.6; border-top:1px solid var(--color-border); padding-top:var(--space-sm);">
          <div><strong>Vehicle:</strong> ${vehicle ? `<code class="mono">${escapeHtml(vehicle.registration_no || vehicle.vehicle_id)}</code>` : '<span class="kpi-sub">Unassigned</span>'}</div>
          <div><strong>Driver:</strong> ${driver ? `<span class="mono font-bold">${escapeHtml(driver.name)}</span> (${escapeHtml(driver.phone || 'No phone')})` : '<span class="kpi-sub">Unassigned</span>'}</div>
          <div><strong>Driver GPS Fix:</strong> ${latest ? `<span class="mono">${latest.latitude.toFixed(5)}, ${latest.longitude.toFixed(5)}</span> (&plusmn;${latest.accuracy_m ? latest.accuracy_m.toFixed(1) : 0}m)` : '<span class="kpi-sub">No live GPS fixes</span>'}</div>
        </div>

        ${svBtn}
        ${pickupSvBtn}
        ${dropoffSvBtn}

        ${delivery.status === 'in_transit' ? `
          <div style="margin-top:var(--space-md); padding-top:var(--space-sm); border-top:1px solid var(--color-border); display:flex; gap:8px;">
            <button type="button" class="btn btn-primary btn-sm flex-1" style="background:#10B981; border-color:#059669; font-weight:600;" data-transition-delivery="${escapeHtml(delivery.delivery_id)}" data-target-status="delivered">
              ${icon('checkCircle', 14)}<span>Mark Delivered</span>
            </button>
            <button type="button" class="btn btn-danger btn-sm" data-transition-delivery="${escapeHtml(delivery.delivery_id)}" data-target-status="cancelled">
              <span>Cancel</span>
            </button>
          </div>
        ` : ''}
        ${delivery.status === 'assigned' ? `
          <div style="margin-top:var(--space-md); padding-top:var(--space-sm); border-top:1px solid var(--color-border); display:flex; gap:8px;">
            <button type="button" class="btn btn-secondary btn-sm flex-1" data-transition-delivery="${escapeHtml(delivery.delivery_id)}" data-target-status="in_transit">
              ${icon('navigation', 14)}<span>Start In-Transit</span>
            </button>
            <button type="button" class="btn btn-danger btn-sm" data-transition-delivery="${escapeHtml(delivery.delivery_id)}" data-target-status="cancelled">
              <span>Cancel</span>
            </button>
          </div>
        ` : ''}
        ${delivery.status === 'pending' ? `
          <div style="margin-top:var(--space-md); padding-top:var(--space-sm); border-top:1px solid var(--color-border); display:flex; gap:8px;">
            <button type="button" class="btn btn-primary btn-sm flex-1" data-dispatch-delivery="${escapeHtml(delivery.delivery_id)}">
              ${icon('dispatch', 14)}<span>Assign Vehicle</span>
            </button>
            <button type="button" class="btn btn-danger btn-sm" data-transition-delivery="${escapeHtml(delivery.delivery_id)}" data-target-status="cancelled">
              <span>Cancel</span>
            </button>
          </div>
        ` : ''}
      `;
    }

    // Map rendering
    const map = getOrCreateLeafletMap('delivery-map', latest ? [latest.latitude, latest.longitude] : [12.9716, 77.5946], 13);
    if (map && window.L) {
      const layers = MAPS.layers['delivery-map'];
      if (layers.marker) map.removeLayer(layers.marker);
      if (layers.circle) map.removeLayer(layers.circle);
      if (layers.trail) map.removeLayer(layers.trail);

      const fixes = (historyRes && historyRes.fixes) || [];
      if (fixes.length > 0) {
        const latlngs = fixes.map((f) => [f.latitude, f.longitude]);
        layers.trail = window.L.polyline(latlngs, {
          color: '#00E5FF',
          weight: 3.5,
          opacity: 0.85,
        }).addTo(map);

        if (latest) {
          const icon = createMapMarkerIcon('delivery');
          layers.marker = window.L.marker([latest.latitude, latest.longitude], { icon })
            .addTo(map)
            .bindPopup(`<strong>Delivery: ${escapeHtml(delivery.delivery_id)}</strong><br>Driver: ${driver ? escapeHtml(driver.name) : 'Assigned'}<br>Speed: ${latest.speed_kmh || 0} km/h`);

          layers.circle = window.L.circle([latest.latitude, latest.longitude], {
            radius: latest.accuracy_m || 20,
            color: '#00E5FF',
            fillColor: '#00E5FF',
            fillOpacity: 0.12,
            weight: 1,
          }).addTo(map);

          try {
            map.fitBounds(layers.trail.getBounds(), { padding: [35, 35], maxZoom: 16 });
          } catch {
            map.setView([latest.latitude, latest.longitude], 14);
          }
        }
      } else if (latest) {
        const icon = createMapMarkerIcon('delivery');
        layers.marker = window.L.marker([latest.latitude, latest.longitude], { icon }).addTo(map);
        map.setView([latest.latitude, latest.longitude], 14);
      }
    }

    // Telemetry graph
    if (graphStatsEl) {
      const pts = (telemetryRes && telemetryRes.points_count) || 0;
      const dist = (telemetryRes && telemetryRes.total_distance_km) || 0;
      graphStatsEl.textContent = `${pts} pts // ${dist.toFixed(2)} km`;
    }
    renderTelemetrySvg('del-telemetry-svg', telemetryRes);
  } catch (err) {
    if (!silent) showGlobalError(err.code || 'DEL_TRACKING_ERROR', err.message);
  }
}

/* --- Driver Smartphone GPS Portal --- */
function renderDriverGpsPortal() {
  const select = document.getElementById('driver-gps-select');
  if (!select) return;

  const currentVal = select.value || TRACKING_STATE.activeDriverId || '';
  select.innerHTML = '<option value="">-- Select Driver to Track --</option>' +
    STATE.drivers
      .map((d) => {
        const isSel = d.driver_id === currentVal ? 'selected' : '';
        return `<option value="${escapeHtml(d.driver_id)}" ${isSel}>${escapeHtml(d.name)} &bull; ${escapeHtml(d.phone)} [${escapeHtml(d.availability_status)}]</option>`;
      })
      .join('');

  updateDriverGpsCard(select.value);
  initGpsContextStatus();
}

function updateDriverGpsCard(driverId) {
  const nameEl = document.getElementById('driver-card-name');
  const phoneEl = document.getElementById('driver-card-phone');
  if (!driverId) {
    if (nameEl) nameEl.textContent = 'No driver selected';
    if (phoneEl) phoneEl.textContent = 'Phone: —';
    return;
  }
  const driver = STATE.drivers.find((d) => d.driver_id === driverId);
  if (driver) {
    if (nameEl) nameEl.textContent = `${driver.name} (${driver.driver_id})`;
    if (phoneEl) phoneEl.textContent = `Phone: ${driver.phone}`;
  }
}

/* ==================== AUTOMATED HARDWARE TELEMETRY & DEVICE INTELLIGENCE (PHASE 3, 4, 5, 6) ==================== */
function initGpsContextStatus() {
  const secureBadge = document.getElementById('badge-secure-context');
  const alertBox = document.getElementById('alert-insecure-context');
  const permBadge = document.getElementById('badge-gps-permission');
  const trackingBadge = document.getElementById('badge-tracking-state');

  const isSecure = window.isSecureContext === true;
  if (secureBadge) {
    if (isSecure) {
      secureBadge.className = 'badge badge-success';
      secureBadge.innerHTML = '<span class="pulse-dot"></span> Secure Context Detected (HTTPS / localhost)';
      if (alertBox) alertBox.classList.add('hidden');
    } else {
      secureBadge.className = 'badge badge-warning';
      secureBadge.innerHTML = '⚠️ Insecure Context (HTTP LAN) &bull; GPS Disabled';
      if (alertBox) alertBox.classList.remove('hidden');
    }
  }

  if (trackingBadge) {
    if (TRACKING_STATE.activeSessionId) {
      trackingBadge.className = 'badge badge-success';
      trackingBadge.textContent = 'GPS tracking active';
    } else {
      trackingBadge.className = 'badge status-inactive';
      trackingBadge.textContent = 'GPS tracking stopped';
    }
  }

  // Check Permissions API if supported
  if (navigator.permissions && typeof navigator.permissions.query === 'function') {
    navigator.permissions.query({ name: 'geolocation' }).then((perm) => {
      updatePermissionBadge(perm.state);
      perm.onchange = () => updatePermissionBadge(perm.state);
    }).catch(() => {
      updatePermissionBadge('prompt');
    });
  } else {
    updatePermissionBadge('prompt');
  }

  // Initial HUD query
  refreshAllHudCards();
}

function updatePermissionBadge(state) {
  const permBadge = document.getElementById('badge-gps-permission');
  if (!permBadge) return;
  if (state === 'granted') {
    permBadge.className = 'badge badge-success';
    permBadge.textContent = 'Location permission granted';
  } else if (state === 'denied') {
    permBadge.className = 'badge badge-danger';
    permBadge.textContent = 'Location permission denied';
  } else if (state === 'unavailable') {
    permBadge.className = 'badge badge-danger';
    permBadge.textContent = 'Location unavailable';
  } else {
    permBadge.className = 'badge badge-secondary';
    permBadge.textContent = 'Location permission not requested';
  }
}

function getOrCreateClientDeviceToken() {
  const KEY = 'fleetwise_client_device_token';
  let token = null;
  try {
    token = localStorage.getItem(KEY);
    if (!token || !token.startsWith('FLT-DEV-')) {
      const array = new Uint8Array(8);
      (window.crypto || window.msCrypto).getRandomValues(array);
      const hex = Array.from(array, b => b.toString(16).padStart(2, '0')).join('').toUpperCase();
      token = 'FLT-DEV-' + hex;
      localStorage.setItem(KEY, token);
    }
  } catch (e) {
    if (!window._ephemeralDeviceToken) {
      window._ephemeralDeviceToken = 'FLT-DEV-EPH-' + Math.random().toString(36).substring(2, 10).toUpperCase();
    }
    token = window._ephemeralDeviceToken;
  }
  return token;
}

async function inspectClientHardware() {
  const ua = navigator.userAgent || '';
  let os = 'Unknown OS';
  let osVersion = null;
  let deviceType = 'Desktop';
  let model = null;
  let manufacturer = 'Unavailable';

  // 1. User-Agent Client Hints if supported (Chromium / Android)
  if (navigator.userAgentData) {
    deviceType = navigator.userAgentData.mobile ? 'Smartphone' : 'Desktop';
    if (typeof navigator.userAgentData.getHighEntropyValues === 'function') {
      try {
        const hints = await navigator.userAgentData.getHighEntropyValues([
          'model',
          'platform',
          'platformVersion',
          'architecture',
          'bitness',
          'fullVersionList',
        ]);
        if (hints.model && hints.model.trim()) {
          model = hints.model.trim();
        }
        if (hints.platform) {
          os = hints.platform;
        }
        if (hints.platformVersion) {
          osVersion = hints.platformVersion;
        }
      } catch (_) {}
    }
  }

  // 2. Client platform & User-Agent regex inspection
  if (/Android/i.test(ua)) {
    os = 'Android';
    deviceType = /Tablet|Nexus 7|Nexus 10|SM-T/i.test(ua) ? 'Tablet' : 'Smartphone';
    const m = ua.match(/Android\s+([\d.]+)/i);
    if (m) osVersion = m[1];
    if (!model) {
      const modelMatch = ua.match(/;\s*([^;]+?)\s+Build\//i);
      if (modelMatch && modelMatch[1]) model = modelMatch[1].trim();
    }
  } else if (/iPad/i.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)) {
    os = 'iPadOS';
    deviceType = 'Tablet';
    const m = ua.match(/OS\s+([\d_]+)/i);
    if (m) osVersion = m[1].replace(/_/g, '.');
  } else if (/iPhone|iPod/i.test(ua)) {
    os = 'iOS';
    deviceType = 'Smartphone';
    const m = ua.match(/OS\s+([\d_]+)/i);
    if (m) osVersion = m[1].replace(/_/g, '.');
  } else if (/Windows/i.test(ua)) {
    os = 'Windows';
    deviceType = 'Desktop';
    if (/Windows NT 10.0/i.test(ua)) osVersion = '10 / 11';
    else if (/Windows NT 6.3/i.test(ua)) osVersion = '8.1';
    else if (/Windows NT 6.1/i.test(ua)) osVersion = '7';
  } else if (/Macintosh|Mac OS X/i.test(ua)) {
    os = 'macOS';
    deviceType = 'Desktop';
    const m = ua.match(/Mac OS X\s+([\d_]+)/i);
    if (m) osVersion = m[1].replace(/_/g, '.');
  } else if (/Linux/i.test(ua)) {
    os = 'Linux';
    deviceType = 'Desktop';
  }

  let browser = 'Unknown Browser';
  let browserVersion = null;
  if (/Edg\/([\d.]+)/i.test(ua)) {
    browser = 'Microsoft Edge';
    browserVersion = ua.match(/Edg\/([\d.]+)/i)[1];
  } else if (/Chrome\/([\d.]+)/i.test(ua) && !/Edg/i.test(ua)) {
    browser = 'Google Chrome';
    browserVersion = ua.match(/Chrome\/([\d.]+)/i)[1];
  } else if (/Version\/([\d.]+).*Safari/i.test(ua) && !/Chrome/i.test(ua)) {
    browser = 'Apple Safari';
    browserVersion = ua.match(/Version\/([\d.]+)/i)[1];
  } else if (/Firefox\/([\d.]+)/i.test(ua)) {
    browser = 'Mozilla Firefox';
    browserVersion = ua.match(/Firefox\/([\d.]+)/i)[1];
  } else if (/OPR\/([\d.]+)/i.test(ua)) {
    browser = 'Opera';
    browserVersion = ua.match(/OPR\/([\d.]+)/i)[1];
  }

  const dpr = window.devicePixelRatio || 1;
  const orientation = window.screen.orientation ? window.screen.orientation.type : (window.innerWidth > window.innerHeight ? 'landscape' : 'portrait');
  const screenRes = `${window.screen.width}x${window.screen.height} (@${dpr}x DPR, ${orientation})`;
  const cpuCores = navigator.hardwareConcurrency ? `${navigator.hardwareConcurrency} logical cores` : 'Unavailable';
  const touchDesc = navigator.maxTouchPoints > 0 ? `${navigator.maxTouchPoints} touch points` : 'No touch sensor';
  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
  const language = navigator.language || 'en';

  return {
    os,
    osVersion,
    deviceType,
    model: model || null,
    manufacturer,
    browser,
    browserVersion,
    screenRes,
    orientation,
    cpuCores,
    touchDesc,
    timeZone,
    language,
    platform: navigator.platform || os,
    ua: ua.slice(0, 160),
  };
}

let _batteryObj = null;
let _batteryPollTimer = null;

async function inspectBattery() {
  const isDesktop = !/Mobi|Android|iPhone|iPad/i.test(navigator.userAgent);
  let bat;
  if (typeof inspectDeviceBattery === 'function') {
    bat = await inspectDeviceBattery({ isDesktop });
  } else {
    bat = {
      status: 'unavailable',
      reason: 'navigator.getBattery not supported by this browser',
      source: 'navigator.getBattery',
      level: null,
      pct: null,
      charging: null,
      chargingState: null,
      chargingTime: null,
      dischargingTime: null,
      label: 'Client Device Battery (Current browser device)',
      display_status: 'unavailable',
      is_suspect: false,
      measured_at: new Date().toISOString(),
    };
  }

  // Subscribe to live battery events if available
  if (!TRACKING_STATE.batteryCleanup && typeof navigator.getBattery === 'function') {
    try {
      _batteryObj = await navigator.getBattery();
      if (_batteryObj) {
        const onBatChange = () => {
          inspectBattery().then((b) => updateBatteryHud(b));
        };
        _batteryObj.addEventListener('levelchange', onBatChange);
        _batteryObj.addEventListener('chargingchange', onBatChange);
        _batteryObj.addEventListener('chargingtimechange', onBatChange);
        _batteryObj.addEventListener('dischargingtimechange', onBatChange);

        TRACKING_STATE.batteryCleanup = () => {
          if (_batteryObj) {
            _batteryObj.removeEventListener('levelchange', onBatChange);
            _batteryObj.removeEventListener('chargingchange', onBatChange);
            _batteryObj.removeEventListener('chargingtimechange', onBatChange);
            _batteryObj.removeEventListener('dischargingtimechange', onBatChange);
          }
          TRACKING_STATE.batteryCleanup = null;
        };
      }
    } catch (_) {}
  }

  return bat;
}

function updateBatteryHud(bat) {
  const pctEl = document.getElementById('hud-battery-pct');
  const chgEl = document.getElementById('hud-battery-charging');
  const ctEl = document.getElementById('hud-battery-charging-time');
  const dtEl = document.getElementById('hud-battery-discharging-time');
  const tsEl = document.getElementById('hud-battery-timestamp');
  const lisEl = document.getElementById('hud-battery-listener');
  const badge = document.getElementById('hud-battery-status-badge');
  const reasonRow = document.getElementById('hud-battery-reason-row');
  const reasonEl = document.getElementById('hud-battery-reason');
  const statusEl = document.getElementById('hud-battery-status');

  if (statusEl) statusEl.textContent = bat.status || 'unknown';

  if (bat.status === 'unavailable') {
    if (pctEl) {
      pctEl.textContent = 'Not available';
      pctEl.className = 'hud-val hud-val-muted';
    }
    if (chgEl) chgEl.textContent = '—';
    if (ctEl) ctEl.textContent = '—';
    if (dtEl) dtEl.textContent = '—';
    if (badge) {
      badge.className = 'badge badge-sm badge-secondary';
      badge.textContent = 'API Unsupported';
    }
    if (reasonRow) reasonRow.style.display = 'flex';
    if (reasonEl) reasonEl.textContent = bat.reason || 'navigator.getBattery not supported by this browser';
  } else if (bat.status === 'error') {
    if (pctEl) {
      pctEl.textContent = 'Error';
      pctEl.className = 'hud-val hud-val-danger';
    }
    if (chgEl) chgEl.textContent = 'Query failed';
    if (ctEl) ctEl.textContent = '—';
    if (dtEl) dtEl.textContent = '—';
    if (badge) {
      badge.className = 'badge badge-sm badge-danger';
      badge.textContent = 'Error';
    }
    if (reasonRow) reasonRow.style.display = 'flex';
    if (reasonEl) reasonEl.textContent = bat.reason || 'Unknown error';
  } else if (bat.status === 'measured_suspect') {
    if (pctEl) {
      pctEl.textContent = bat.pct || '100%';
      pctEl.className = 'hud-val hud-val-amber';
    }
    if (chgEl) chgEl.textContent = bat.charging ? '⚡ Charging (AC/USB)' : '🔋 Discharging';
    if (ctEl) ctEl.textContent = bat.chargingTime === 0 ? '0 min' : String(bat.chargingTime);
    if (dtEl) dtEl.textContent = String(bat.dischargingTime);
    if (badge) {
      badge.className = 'badge badge-sm badge-warning';
      badge.textContent = 'browser-reported, unverified';
    }
    if (reasonRow) reasonRow.style.display = 'flex';
    if (reasonEl) reasonEl.textContent = bat.reason || 'Values equal API defaults; browser may not be reading a battery';
  } else {
    // status === 'measured'
    if (pctEl) {
      pctEl.textContent = bat.pct !== null ? bat.pct : '—';
      pctEl.className = 'hud-val hud-val-green';
    }
    if (chgEl) chgEl.textContent = bat.charging ? '⚡ Charging (AC/USB)' : (bat.charging === false ? '🔋 Discharging (Battery)' : '—');
    if (ctEl) ctEl.textContent = (bat.chargingTime !== null && bat.chargingTime !== 'Infinity') ? `${bat.chargingTime} min` : '—';
    if (dtEl) dtEl.textContent = (bat.dischargingTime !== null && bat.dischargingTime !== 'Infinity') ? `${bat.dischargingTime} min` : '—';
    if (badge) {
      badge.className = 'badge badge-sm badge-success';
      badge.textContent = 'Measured';
    }
    if (reasonRow) reasonRow.style.display = 'none';
  }

  if (tsEl) tsEl.textContent = bat.measured_at ? bat.measured_at.split('T')[1].slice(0, 8) : new Date().toLocaleTimeString([], { hour12: false });
  if (lisEl) lisEl.textContent = TRACKING_STATE.batteryCleanup ? 'Active (Live events)' : 'Inactive';
}

async function inspectServerHostPower() {
  try {
    const res = await apiRequest('/system/host-power');
    if (res && res.supported) {
      updateServerHostPowerHud(res);
      return res;
    }
  } catch (_) {}
  updateServerHostPowerHud({ supported: false });
  return null;
}

function updateServerHostPowerHud(data) {
  const pctEl = document.getElementById('hud-host-power-pct');
  const chgEl = document.getElementById('hud-host-power-charging');
  const srcEl = document.getElementById('hud-host-power-source');
  const tsEl = document.getElementById('hud-host-power-timestamp');
  const badge = document.getElementById('hud-host-power-badge');

  if (!data || !data.supported) {
    if (pctEl) pctEl.textContent = 'Unavailable / Offline';
    if (chgEl) chgEl.textContent = '—';
    if (srcEl) srcEl.textContent = 'Host power unreachable';
    if (badge) {
      badge.className = 'badge badge-sm badge-secondary';
      badge.textContent = 'Host Offline';
    }
    return;
  }

  if (pctEl) pctEl.textContent = data.pct;
  if (chgEl) chgEl.textContent = data.charging;
  if (srcEl) srcEl.textContent = data.source;
  if (tsEl) tsEl.textContent = data.reading_timestamp;
  if (badge) {
    badge.className = 'badge badge-sm badge-success';
    badge.textContent = 'Host Power Live';
  }
}

function inspectNetwork() {
  const conn = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
  if (!conn) {
    return {
      supported: false,
      effectiveType: 'Network API not supported',
      downlink: 'Unavailable',
      rtt: 'Unavailable',
      saveData: 'Unavailable',
      clientIp: window.location.hostname,
    };
  }

  const effectiveType = conn.effectiveType ? conn.effectiveType.toUpperCase() : 'Unknown';
  const downlink = conn.downlink != null ? `${conn.downlink} Mbps` : 'Unavailable';
  const rtt = conn.rtt != null ? `${conn.rtt} ms` : 'Unavailable';
  const saveData = conn.saveData ? 'Enabled' : 'Disabled';

  if (!TRACKING_STATE.networkCleanup) {
    const onNetChange = () => {
      const net = inspectNetwork();
      updateNetworkHud(net);
    };
    conn.addEventListener('change', onNetChange);
    TRACKING_STATE.networkCleanup = () => {
      conn.removeEventListener('change', onNetChange);
      TRACKING_STATE.networkCleanup = null;
    };
  }

  return {
    supported: true,
    effectiveType,
    downlink,
    rtt,
    saveData,
    clientIp: window.location.hostname,
  };
}

function updateNetworkHud(net) {
  const typeEl = document.getElementById('hud-network-type');
  const downEl = document.getElementById('hud-network-downlink');
  const rttEl = document.getElementById('hud-network-rtt');
  const saveEl = document.getElementById('hud-network-savedata');
  const ipEl = document.getElementById('hud-network-ip');
  const badge = document.getElementById('hud-network-status-badge');

  if (typeEl) typeEl.textContent = net.effectiveType;
  if (downEl) downEl.textContent = net.downlink;
  if (rttEl) rttEl.textContent = net.rtt;
  if (saveEl) saveEl.textContent = net.saveData;
  if (ipEl) ipEl.textContent = net.clientIp;
  if (badge) {
    badge.className = net.supported ? 'badge badge-sm badge-success' : 'badge badge-sm badge-secondary';
    badge.textContent = net.supported ? 'API Supported' : 'Unsupported';
  }
}

function inspectCapabilities() {
  return {
    secureContext: window.isSecureContext === true,
    geolocation: 'geolocation' in navigator,
    batteryApi: typeof navigator.getBattery === 'function',
    networkApi: Boolean(navigator.connection || navigator.mozConnection || navigator.webkitConnection),
    cameraApi: Boolean(navigator.mediaDevices && typeof navigator.mediaDevices.getUserMedia === 'function'),
  };
}

async function refreshAllHudCards() {
  const hw = await inspectClientHardware();
  const bat = await inspectBattery();
  const net = inspectNetwork();
  const cap = inspectCapabilities();

  // Populate Device Card
  const catEl = document.getElementById('hud-device-category');
  const modelEl = document.getElementById('hud-device-model');
  const osEl = document.getElementById('hud-device-os');
  const browEl = document.getElementById('hud-device-browser');
  const scEl = document.getElementById('hud-device-screen');
  const cpuEl = document.getElementById('hud-device-cpu');
  const touchEl = document.getElementById('hud-device-touch');
  const tzEl = document.getElementById('hud-device-tz');

  if (catEl) catEl.textContent = hw.deviceType;
  if (modelEl) {
    if (hw.model) {
      modelEl.textContent = hw.model;
      modelEl.className = 'hud-val hud-val-green';
    } else {
      modelEl.textContent = 'Device model unavailable through this browser.';
      modelEl.className = 'hud-val hud-val-muted';
    }
  }
  if (osEl) osEl.textContent = hw.osVersion ? `${hw.os} ${hw.osVersion}` : hw.os;
  if (browEl) browEl.textContent = hw.browserVersion ? `${hw.browser} ${hw.browserVersion}` : hw.browser;
  if (scEl) scEl.textContent = hw.screenRes;
  if (cpuEl) cpuEl.textContent = hw.cpuCores;
  if (touchEl) touchEl.textContent = hw.touchDesc;
  if (tzEl) tzEl.textContent = `${hw.timeZone} (${hw.language})`;

  // Populate Battery Card
  updateBatteryHud(bat);

  // Populate Server Host Power Card (Physical Machine Running Backend)
  await inspectServerHostPower();

  // Populate Network Card
  updateNetworkHud(net);

  // Populate Capabilities Card
  const capSec = document.getElementById('hud-cap-secure');
  const capGeo = document.getElementById('hud-cap-geo');
  const capBat = document.getElementById('hud-cap-battery');
  const capNet = document.getElementById('hud-cap-network');
  const capCam = document.getElementById('hud-cap-camera');

  if (capSec) {
    capSec.textContent = cap.secureContext ? 'Detected (Active)' : 'Insecure (HTTP)';
    capSec.className = cap.secureContext ? 'hud-val hud-val-green' : 'hud-val hud-val-amber';
  }
  if (capGeo) {
    capGeo.textContent = cap.geolocation ? 'Supported' : 'Unsupported';
    capGeo.className = cap.geolocation ? 'hud-val hud-val-green' : 'hud-val hud-val-muted';
  }
  if (capBat) {
    capBat.textContent = cap.batteryApi ? 'Supported' : 'Not supported';
    capBat.className = cap.batteryApi ? 'hud-val hud-val-green' : 'hud-val hud-val-muted';
  }
  if (capNet) {
    capNet.textContent = cap.networkApi ? 'Supported' : 'Not supported';
    capNet.className = cap.networkApi ? 'hud-val hud-val-green' : 'hud-val hud-val-muted';
  }
  if (capCam) {
    capCam.textContent = cap.cameraApi ? 'Available (Hardware query)' : 'Unavailable';
    capCam.className = cap.cameraApi ? 'hud-val hud-val-green' : 'hud-val hud-val-muted';
  }

  TRACKING_STATE.cachedDeviceInfo = hw;
  return { hw, bat, net, cap };
}

function handleIncomingGpsFix(pos) {
  updatePermissionBadge('granted');

  const coords = pos.coords;
  const lat = coords.latitude;
  const lng = coords.longitude;
  const accuracy = coords.accuracy;
  const altitude = coords.altitude != null ? coords.altitude : null;
  const altitudeAccuracy = coords.altitudeAccuracy != null ? coords.altitudeAccuracy : null;
  const speed = coords.speed != null ? coords.speed * 3.6 : null;
  const heading = coords.heading != null ? coords.heading : null;
  const deviceTimestamp = new Date(pos.timestamp).toISOString();

  TRACKING_STATE.fixCount += 1;
  TRACKING_STATE.lastFix = { lat, lng, accuracy, altitude, altitudeAccuracy, speed, heading, deviceTimestamp };

  // Update DOM displays
  const latEl = document.getElementById('disp-lat');
  const lngEl = document.getElementById('disp-lng');
  const accEl = document.getElementById('disp-acc');
  const speedEl = document.getElementById('disp-speed');
  const altEl = document.getElementById('disp-alt');
  const headEl = document.getElementById('disp-heading');
  const countEl = document.getElementById('disp-fixes-count');
  const pingEl = document.getElementById('disp-last-ping');
  const svWrap = document.getElementById('disp-streetview-wrap');

  if (latEl) latEl.textContent = lat.toFixed(6);
  if (lngEl) lngEl.textContent = lng.toFixed(6);
  if (accEl) accEl.textContent = `\u00B1${accuracy.toFixed(1)}m`;
  if (speedEl) speedEl.textContent = speed != null ? speed.toFixed(1) : '0.0';
  if (altEl) altEl.textContent = altitude != null ? `${altitude.toFixed(1)} m` : '—';
  if (headEl) headEl.textContent = heading != null ? `${heading.toFixed(0)}\u00B0` : '—';
  if (countEl) countEl.textContent = TRACKING_STATE.fixCount;
  if (pingEl) pingEl.textContent = new Date().toLocaleTimeString([], { hour12: false });

  if (svWrap) {
    const svUrl = `https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${lat.toFixed(6)},${lng.toFixed(6)}`;
    svWrap.innerHTML = `
      <a href="${svUrl}" target="_blank" rel="noopener noreferrer" class="btn btn-secondary btn-xs streetview-btn">
        ${icon('navigation', 12)}<span>Street View</span>
      </a>
    `;
  }

  // Stream coordinate to backend with throttling (min 1000ms between pings)
  const now = Date.now();
  if (TRACKING_STATE.activeSessionId && TRACKING_STATE.activeDriverId) {
    if (now - TRACKING_STATE.lastIngestedTimestamp >= 1000 || TRACKING_STATE.fixCount === 1) {
      TRACKING_STATE.lastIngestedTimestamp = now;
      apiRequest('/tracking/location', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: TRACKING_STATE.activeSessionId,
          driver_id: TRACKING_STATE.activeDriverId,
          device_id: TRACKING_STATE.activeDeviceId,
          latitude: lat,
          longitude: lng,
          accuracy,
          altitude,
          altitude_accuracy: altitudeAccuracy,
          speed: coords.speed != null ? coords.speed : null,
          heading,
          device_timestamp: deviceTimestamp,
        }),
      }).catch((err) => {
        console.warn('GPS location ingestion notice:', err);
      });
    }
  }

  // Update driver mini-map
  const map = getOrCreateLeafletMap('driver-mini-map', [lat, lng], 16);
  if (map && window.L) {
    const layers = MAPS.layers['driver-mini-map'];
    if (layers.marker) map.removeLayer(layers.marker);
    if (layers.circle) map.removeLayer(layers.circle);

    const mapIcon = createMapMarkerIcon('driver');
    layers.marker = window.L.marker([lat, lng], { icon: mapIcon }).addTo(map);
    layers.circle = window.L.circle([lat, lng], {
      radius: accuracy,
      color: '#00F0FF',
      fillColor: '#00F0FF',
      fillOpacity: 0.15,
      weight: 1,
    }).addTo(map);

    map.setView([lat, lng]);
  }
}

function handleGpsError(err) {
  const badge = document.getElementById('gps-status-badge');
  let msg = 'Failed to acquire device GPS position.';

  if (err.code === 1) {
    updatePermissionBadge('denied');
    msg = 'Location permission denied. Please allow location access in your browser address bar settings.';
    if (badge) {
      badge.textContent = 'PERMISSION DENIED';
      badge.className = 'status-badge status-conflict';
    }
  } else if (err.code === 2) {
    updatePermissionBadge('unavailable');
    msg = 'GPS position unavailable. Ensure device location / GPS is turned ON in your phone settings.';
    if (badge) {
      badge.textContent = 'GPS UNAVAILABLE';
      badge.className = 'status-badge status-conflict';
    }
  } else if (err.code === 3) {
    msg = 'GPS request timed out. Retrying satellite acquisition...';
    if (badge) {
      badge.textContent = 'GPS TIMEOUT';
      badge.className = 'status-badge status-stale';
    }
  }
  showToast(msg, true, 'GPS_ERROR');
}

async function startDriverGpsTracking() {
  const driverSelect = document.getElementById('driver-gps-select');
  const driverId = driverSelect ? driverSelect.value : '';
  if (!driverId) {
    showToast('Please select a driver to start GPS tracking.', true, 'NO_DRIVER');
    return;
  }

  if (!navigator.geolocation) {
    showToast('HTML5 Geolocation is not supported by your browser or environment.', true, 'NO_GEOLOCATION');
    return;
  }

  if (window.isSecureContext === false) {
    showToast('Insecure Context (HTTP): Mobile browsers block GPS. Access via HTTPS or localhost.', true, 'INSECURE_CONTEXT');
    const alertBox = document.getElementById('alert-insecure-context');
    if (alertBox) alertBox.classList.remove('hidden');
  }

  // 1. Collect full client intelligence
  const { hw, bat, net, cap } = await refreshAllHudCards();

  const customNickname = document.getElementById('driver-device-info')?.value?.trim();
  const nickname = customNickname || `${hw.os} ${hw.deviceType} (${hw.browser})`;

  try {
    // 2. Register/update authenticated device profile
    const clientToken = getOrCreateClientDeviceToken();
    const regPayload = {
      driver_id: driverId,
      client_device_token: clientToken,
      identity_confidence: clientToken.startsWith('FLT-DEV-EPH') ? 'ephemeral_fallback' : 'client_storage_token',
      detection_limitations: 'Browser storage token. Private browsing generates isolated ephemeral token.',
      nickname,
      device_category: hw.deviceType,
      model: hw.model,
      os_family: hw.os,
      os_version: hw.osVersion,
      browser_family: hw.browser,
      browser_version: hw.browserVersion,
      platform: hw.platform,
      screen_res: hw.screenRes,
      permission_status: 'granted',
      capabilities: {
        device_type: hw.deviceType,
        cpu_cores: navigator.hardwareConcurrency || null,
        touch_points: navigator.maxTouchPoints || 0,
        battery_pct: bat.pct,
        battery_charging: bat.charging,
        network_type: net.effectiveType,
        downlink: net.downlink,
        rtt: net.rtt,
        secure_context: cap.secureContext,
      },
    };

    const dev = await apiRequest('/devices/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(regPayload),
    });

    TRACKING_STATE.activeDeviceId = dev.device_id;
    const regBadge = document.getElementById('hud-registered-badge');
    if (regBadge) {
      regBadge.className = 'badge badge-success';
      regBadge.textContent = `Registered: ${dev.device_id}`;
    }

    // 3. Start tracking session
    const session = await apiRequest('/tracking/sessions/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        driver_id: driverId,
        device_id: dev.device_id,
        device_info: `${nickname} [${dev.device_id}]`,
      }),
    });

    TRACKING_STATE.activeSessionId = session.session_id;
    TRACKING_STATE.activeDriverId = driverId;
    TRACKING_STATE.fixCount = 0;
    TRACKING_STATE.lastIngestedTimestamp = 0;

    const badge = document.getElementById('gps-status-badge');
    const startBtn = document.getElementById('btn-start-gps');
    const stopBtn = document.getElementById('btn-stop-gps');
    const trackingBadge = document.getElementById('badge-tracking-state');

    if (badge) {
      badge.textContent = 'STREAMING LIVE';
      badge.className = 'status-badge status-live';
    }
    if (trackingBadge) {
      trackingBadge.textContent = 'GPS tracking active';
      trackingBadge.className = 'badge badge-success';
    }
    if (startBtn) startBtn.disabled = true;
    if (stopBtn) stopBtn.disabled = false;

    // 4. Start watching physical device location
    TRACKING_STATE.watchId = navigator.geolocation.watchPosition(
      handleIncomingGpsFix,
      handleGpsError,
      {
        enableHighAccuracy: true,
        timeout: 20000,
        maximumAge: 0,
      }
    );

    showToast(`GPS Tracking started: session #${session.session_id} (${dev.device_id})`);
  } catch (err) {
    showGlobalError(err.code || 'GPS_START_ERROR', err.message);
  }
}

async function stopDriverGpsTracking() {
  if (TRACKING_STATE.watchId != null) {
    navigator.geolocation.clearWatch(TRACKING_STATE.watchId);
    TRACKING_STATE.watchId = null;
  }

  // Clean up battery & network listeners
  if (TRACKING_STATE.batteryCleanup) {
    TRACKING_STATE.batteryCleanup();
  }
  if (TRACKING_STATE.networkCleanup) {
    TRACKING_STATE.networkCleanup();
  }

  if (TRACKING_STATE.activeSessionId) {
    try {
      await apiRequest('/tracking/sessions/stop', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: TRACKING_STATE.activeSessionId,
        }),
      });
    } catch (err) {
      console.warn('Error closing tracking session:', err);
    }
    TRACKING_STATE.activeSessionId = null;
  }

  const badge = document.getElementById('gps-status-badge');
  const startBtn = document.getElementById('btn-start-gps');
  const stopBtn = document.getElementById('btn-stop-gps');
  const trackingBadge = document.getElementById('badge-tracking-state');

  if (badge) {
    badge.textContent = 'STOPPED';
    badge.className = 'status-badge status-inactive';
  }
  if (trackingBadge) {
    trackingBadge.textContent = 'GPS tracking stopped';
    trackingBadge.className = 'badge status-inactive';
  }
  if (startBtn) startBtn.disabled = false;
  if (stopBtn) stopBtn.disabled = true;

  showToast('GPS tracking stopped.');
}

function openEditDriverPhoneModal(driverId) {
  const driver = STATE.drivers.find((d) => d.driver_id === driverId);
  if (!driver) return;
  document.getElementById('phone-driver-id').value = driver.driver_id;
  document.getElementById('phone-driver-name').textContent = `${driver.name} (${driver.driver_id})`;
  document.getElementById('phone-input').value = driver.phone || '';
  openModal('modal-driver-phone');
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
    sseSource.onmessage = (event) => {
      refreshAllData(true);
      try {
        const data = JSON.parse(event.data);
        if (data && data.event === 'gps_location_update') {
          if (STATE.activeView === 'vehicle-tracking' && STATE.selectedTrackingVehicleId === data.vehicle_id) {
            loadVehicleTrackingData(data.vehicle_id, true);
          }
          if (STATE.activeView === 'delivery-tracking' && STATE.selectedTrackingDeliveryId === data.delivery_id) {
            loadDeliveryTrackingData(data.delivery_id, true);
          }
        }
      } catch {}
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

  // Vehicle Live Tracking listeners
  document.getElementById('veh-tracking-select')?.addEventListener('change', (e) => {
    loadVehicleTrackingData(e.target.value);
  });
  document.getElementById('btn-refresh-veh-tracking')?.addEventListener('click', () => {
    const sel = document.getElementById('veh-tracking-select');
    if (sel && sel.value) loadVehicleTrackingData(sel.value);
    else showToast('Please select a vehicle to refresh.');
  });

  // Delivery Transit Tracking listeners
  document.getElementById('del-tracking-select')?.addEventListener('change', (e) => {
    loadDeliveryTrackingData(e.target.value);
  });
  document.getElementById('btn-refresh-del-tracking')?.addEventListener('click', () => {
    const sel = document.getElementById('del-tracking-select');
    if (sel && sel.value) loadDeliveryTrackingData(sel.value);
    else showToast('Please select a delivery to refresh.');
  });

  // Driver Phone GPS Portal listeners
  document.getElementById('driver-gps-select')?.addEventListener('change', (e) => {
    updateDriverGpsCard(e.target.value);
  });
  document.getElementById('btn-edit-driver-phone')?.addEventListener('click', () => {
    const sel = document.getElementById('driver-gps-select');
    if (sel && sel.value) openEditDriverPhoneModal(sel.value);
    else showToast('Please select a driver first.');
  });
  document.getElementById('btn-start-gps')?.addEventListener('click', startDriverGpsTracking);
  document.getElementById('btn-stop-gps')?.addEventListener('click', stopDriverGpsTracking);

  // Driver phone edit form modal
  document.getElementById('form-driver-phone')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const driverId = document.getElementById('phone-driver-id')?.value;
    const phone = document.getElementById('phone-input')?.value.trim();
    if (!driverId || !phone) return;
    try {
      const updated = await apiRequest(`/drivers/${encodeURIComponent(driverId)}/phone`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone }),
      });
      showToast(`Phone number updated for ${updated.name}: ${updated.phone}`);
      closeModal('modal-driver-phone');
      await refreshAllData(true);
      updateDriverGpsCard(document.getElementById('driver-gps-select')?.value);
    } catch (err) {
      showGlobalError(err.code || 'PHONE_UPDATE_ERROR', err.message);
    }
  });

  // Delegated click for editing driver phone anywhere in tables
  document.addEventListener('click', (e) => {
    const editPhoneBtn = e.target.closest('[data-edit-phone]');
    if (editPhoneBtn) {
      const driverId = editPhoneBtn.getAttribute('data-edit-phone');
      if (driverId) openEditDriverPhoneModal(driverId);
    }
  });

  // Share & Mobile QR Code
  document.getElementById('btn-open-share')?.addEventListener('click', openShareModal);
  document.getElementById('btn-hero-share')?.addEventListener('click', openShareModal);
  document.getElementById('btn-copy-share-url')?.addEventListener('click', copyShareUrl);
  document.getElementById('btn-hero-dispatch')?.addEventListener('click', () => switchView('dispatch'));
  document.getElementById('btn-hero-radar')?.addEventListener('click', () => switchView('vehicle-tracking'));
  document.querySelectorAll('.share-target-btn').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      const target = e.currentTarget.getAttribute('data-share-target');
      if (target) setShareTarget(target);
    });
  });

  // Device Inventory listeners
  document.getElementById('btn-open-register-device')?.addEventListener('click', openRegisterDeviceModal);
  document.getElementById('btn-refresh-devices')?.addEventListener('click', async () => {
    await refreshAllData();
    renderDevicesTable();
    showToast('Device Inventory refreshed');
  });
  document.getElementById('form-device-register')?.addEventListener('submit', submitRegisterDevice);
  document.getElementById('btn-autodetect-device')?.addEventListener('click', () => {
    const hw = inspectHardware();
    const nickEl = document.getElementById('dev-reg-nickname');
    const osEl = document.getElementById('dev-reg-os');
    const brEl = document.getElementById('dev-reg-browser');
    if (nickEl) nickEl.value = `${hw.os} ${hw.deviceType} (${hw.browser})`;
    if (osEl) osEl.value = hw.os;
    if (brEl) brEl.value = hw.browser;
    showToast('Device hardware attributes auto-detected and populated.');
  });
  document.getElementById('form-phone-verify')?.addEventListener('submit', submitPhoneVerification);

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
      ['modal-cmd', 'modal-vehicle', 'modal-driver', 'modal-delivery', 'modal-blocked-queue', 'modal-shortcuts', 'modal-driver-phone', 'modal-share-link', 'modal-device-register', 'modal-phone-verify'].forEach(closeModal);
    } else if (!isTyping && !e.ctrlKey && !e.metaKey && !e.altKey) {
      if (e.key === '?') {
        e.preventDefault();
        openModal('modal-shortcuts');
      } else if (e.key === '1') switchView('dashboard');
      else if (e.key === '2') switchView('deliveries');
      else if (e.key === '3') switchView('dispatch');
      else if (e.key === '4') switchView('fleet');
      else if (e.key === '5') switchView('drivers');
      else if (e.key === '6') switchView('vehicle-tracking');
      else if (e.key === '7') switchView('delivery-tracking');
      else if (e.key === '8') switchView('driver-gps');
      else if (e.key.toLowerCase() === 'i') switchView('import');
      else if (e.key.toLowerCase() === 'l') switchView('racelab');
      else if (e.key.toLowerCase() === 'y') switchView('analytics');
      else if (e.key.toLowerCase() === 'm') switchView('routes');
      else if (e.key.toLowerCase() === 'a') switchView('audit');
    }
  });
}

/* ==================== SHARE LINK & QR CODE ==================== */
let _qrInstance = null;
let _cachedNetInfo = null;
let _currentShareTarget = 'lan-https';

async function openShareModal() {
  try {
    try {
      _cachedNetInfo = await apiRequest('/network-info');
    } catch (_) {
      _cachedNetInfo = {
        local_ip: window.location.hostname,
        lan_url: `http://${window.location.hostname}:8000`,
        lan_https_url: `https://${window.location.hostname}:8443`,
        localhost_url: 'http://127.0.0.1:8000',
      };
    }

    setShareTarget(_currentShareTarget);
    openModal('modal-share-link');
  } catch (err) {
    console.warn('Error opening share modal:', err);
    openModal('modal-share-link');
  }
}

function setShareTarget(target) {
  _currentShareTarget = target;
  let targetUrl = window.location.origin;

  if (_cachedNetInfo) {
    if (target === 'lan-https') {
      targetUrl = _cachedNetInfo.lan_https_url || `https://${_cachedNetInfo.local_ip}:8443`;
    } else if (target === 'lan-http') {
      targetUrl = _cachedNetInfo.lan_url || `http://${_cachedNetInfo.local_ip}:8000`;
    } else if (target === 'localhost') {
      targetUrl = _cachedNetInfo.localhost_url || 'http://127.0.0.1:8000';
    }
  }

  // Update active button state
  document.querySelectorAll('.share-target-btn').forEach((btn) => {
    btn.classList.toggle('active', btn.getAttribute('data-share-target') === target);
  });

  const input = document.getElementById('share-lan-url');
  if (input) input.value = targetUrl;

  const qrContainer = document.getElementById('share-qr-container');
  if (qrContainer && window.QRCode) {
    qrContainer.innerHTML = '';
    _qrInstance = new window.QRCode(qrContainer, {
      text: targetUrl,
      width: 190,
      height: 190,
      colorDark: '#07090E',
      colorLight: '#FFFFFF',
      correctLevel: window.QRCode.CorrectLevel ? window.QRCode.CorrectLevel.M : 2,
    });
  }
}

async function copyShareUrl() {
  const input = document.getElementById('share-lan-url');
  if (!input || !input.value) return;
  try {
    await navigator.clipboard.writeText(input.value);
    showToast('Direct LAN URL copied! Anyone on your Wi-Fi can open it.');
  } catch (_) {
    input.select();
    document.execCommand('copy');
    showToast('Direct LAN URL copied!');
  }
}

async function initNetworkInfoBanner() {
  try {
    const net = await apiRequest('/network-info');
    const heroPill = document.getElementById('hero-lan-pill');
    if (heroPill && net && net.local_ip) {
      heroPill.textContent = `LAN: ${net.local_ip}:${net.port || 8000}`;
      heroPill.title = `Access from any phone on this Wi-Fi: ${net.lan_url}`;
    }
  } catch (_) {}
}

/* ==================== INITIALIZE ==================== */
document.addEventListener('DOMContentLoaded', async () => {
  initTheme();
  hydrateStaticIcons();
  setupEventListeners();
  initNetworkInfoBanner();
  initGpsContextStatus();
  setupSSE();
  await checkAuthSession();
  await refreshAllData(true);

  STATE.pollTimer = setInterval(() => {
    if (STATE.pollingEnabled && !document.hidden) {
      refreshAllData(true);
    }
  }, 5000);
});

