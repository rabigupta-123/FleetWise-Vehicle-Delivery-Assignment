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
  metricsHistory: [],
  previousMetrics: null,
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
  scheduleSelectedDate: null,
  dashDeliveriesPage: 1,
  deliveriesPage: 1,
};

function getInitials(name) {
  if (!name || typeof name !== 'string') return 'DR';
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return 'DR';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function demoBadgeHtml(isDemo, isSimulated = false) {
  let html = '';
  if (isDemo) {
    html += `<span class="demo-chip">DEMO</span>`;
  }
  if (isSimulated) {
    html += `<span class="simulated-chip">SIMULATED</span>`;
  }
  return html;
}

function formatSlaCountdown(scheduledTimeStr, status) {
  if (status === 'delivered') {
    return { text: 'Delivered', overdue: false };
  }
  if (status === 'cancelled') {
    return { text: 'Cancelled', overdue: false };
  }
  if (!scheduledTimeStr) {
    return { text: 'n/a', overdue: false };
  }
  const targetMs = Date.parse(scheduledTimeStr);
  if (Number.isNaN(targetMs)) {
    return { text: 'n/a', overdue: false };
  }
  const diffMin = Math.round((targetMs - Date.now()) / 60000);
  if (diffMin < 0) {
    const absMin = Math.abs(diffMin);
    const hrs = Math.floor(absMin / 60);
    const mins = absMin % 60;
    return {
      text: hrs > 0 ? `Overdue ${hrs}h ${mins}m` : `Overdue ${mins}m`,
      overdue: true,
    };
  }
  const hrs = Math.floor(diffMin / 60);
  const mins = diffMin % 60;
  return {
    text: hrs > 0 ? `${hrs}h ${mins}m left` : `${mins}m left`,
    overdue: false,
  };
}

function animateCountUp(el, targetNum, suffix = '') {
  if (!el) return;
  const num = Number(targetNum);
  if (!Number.isFinite(num)) {
    el.textContent = `n/a`;
    return;
  }
  const reducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const prevRaw = el.getAttribute('data-numeric-val');
  el.setAttribute('data-numeric-val', String(num));
  if (reducedMotion || prevRaw === null || Number(prevRaw) === num) {
    el.textContent = `${num}${suffix}`;
    return;
  }
  const startVal = Number(prevRaw) || 0;
  const startTime = performance.now();
  const duration = 240;
  function step(now) {
    const t = Math.min(1, (now - startTime) / duration);
    const current = Math.round(startVal + (num - startVal) * t);
    el.textContent = `${current}${suffix}`;
    if (t < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

function updateKpiDeltaPill(id, curVal, prevVal, suffix = '') {
  const el = document.getElementById(id);
  if (!el) return;
  if (prevVal === null || prevVal === undefined || !Number.isFinite(Number(prevVal))) {
    el.textContent = 'n/a';
    el.className = 'kpi-delta-pill';
    return;
  }
  const diff = Number(curVal) - Number(prevVal);
  if (diff === 0) {
    el.textContent = `0${suffix}`;
    el.className = 'kpi-delta-pill';
  } else if (diff > 0) {
    el.textContent = `+${diff}${suffix}`;
    el.className = 'kpi-delta-pill up';
  } else {
    el.textContent = `${diff}${suffix}`;
    el.className = 'kpi-delta-pill down';
  }
}

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

function showGlobalError(code, message, reqId = '') {
  const banner = document.getElementById('global-error-banner');
  const codeEl = document.getElementById('global-error-code');
  const msgEl = document.getElementById('global-error-message');
  if (!banner || !codeEl || !msgEl) return;
  codeEl.textContent = code || 'ERROR';
  msgEl.textContent = reqId ? `${message} [Req ID: ${reqId}]` : (message || 'An unexpected error occurred.');
  banner.classList.remove('hidden');
  showToast(msgEl.textContent, true, code);
}

function clearGlobalError() {
  const banner = document.getElementById('global-error-banner');
  if (banner) banner.classList.add('hidden');
}

function getCookieValue(name) {
  const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
  return match ? decodeURIComponent(match[2]) : '';
}

async function ensureCsrfToken() {
  let tok = getCookieValue('csrf_token');
  if (!tok) {
    try {
      const res = await fetch('/api/csrf-token', { credentials: 'same-origin' });
      if (res.ok) {
        const d = await res.json();
        tok = d.csrf_token || getCookieValue('csrf_token');
      }
    } catch (_) {}
  }
  return tok;
}

async function apiRequest(path, options = {}) {
  options.headers = options.headers || {};
  const opName = localStorage.getItem('fleetwise_operator_name');
  if (opName) {
    if (options.headers instanceof Headers) {
      options.headers.set('X-Operator-Name', opName);
    } else {
      options.headers['X-Operator-Name'] = opName;
    }
  }
  const method = (options.method || 'GET').toUpperCase();
  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
    const csrfToken = await ensureCsrfToken();
    if (csrfToken) {
      if (options.headers instanceof Headers) {
        options.headers.set('X-CSRF-Token', csrfToken);
      } else {
        options.headers['X-CSRF-Token'] = csrfToken;
      }
    }
  }
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
    const reqId = (data && data.request_id) || res.headers.get('x-request-id') || '';
    const err = new Error(reqId ? `${errMsg} [Req ID: ${reqId}]` : errMsg);
    err.status = res.status;
    err.code = errCode;
    err.requestId = reqId;
    err.rawMessage = errMsg;
    err.payload = data;
    throw err;
  }
  return data;
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



    if (metricsRes.status === 'fulfilled' && metricsRes.value) {
      if (STATE.metricsHistory.length > 0) {
        STATE.previousMetrics = { ...STATE.metrics };
      }
      STATE.metrics = { ...STATE.metrics, ...metricsRes.value };
      STATE.metricsHistory.push({
        ts: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }),
        available_fleet: Number(STATE.metrics.available_fleet ?? 0),
        active_deliveries: Number(STATE.metrics.active_deliveries ?? 0),
        delivered_count: Number(STATE.metrics.delivered_count ?? 0),
        utilisation_pct: Number(STATE.metrics.utilisation_pct ?? 0),
      });
      if (STATE.metricsHistory.length > 24) {
        STATE.metricsHistory.shift();
      }
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

    try {
      const [netInfo, simStatus] = await Promise.all([
        apiRequest('/network-info').catch(() => null),
        apiRequest('/demo/status').catch(() => null),
      ]);
      const modeBadge = document.getElementById('access-mode-badge');
      if (netInfo && netInfo.is_share_lan) {
        document.getElementById('share-lan-banner')?.classList.remove('hidden');
        if (modeBadge) modeBadge.textContent = 'SHARING ON LAN';
      } else if (modeBadge) {
        modeBadge.textContent = 'LOCAL DEMO MODE';
      }
      if (simStatus) {
        const lbl = document.getElementById('sim-status-label');
        if (lbl) {
          lbl.textContent = simStatus.simulator_running ? `Sim: Step ${simStatus.step}` : 'Sim: Paused';
        }
      }
    } catch (_) {}
    if (devicesRes && devicesRes.status === 'fulfilled' && Array.isArray(devicesRes.value)) {
      STATE.devices = devicesRes.value;
      const devBadge = document.getElementById('nav-badge-devices');
      if (devBadge) devBadge.textContent = String(STATE.devices.length);
    }

    await refreshFilteredDeliveries();
    await refreshBlockedQueue();
    renderAll();
    if (STATE.activeView === 'dashboard') {
      updateDashboardLiveMap();
    } else if (STATE.activeView === 'analytics') {
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
  const prev = STATE.previousMetrics;

  animateCountUp(document.getElementById('kpi-available-fleet'), m.available_fleet ?? 0);
  document.getElementById('kpi-fleet-breakdown').textContent = `/ ${m.total_vehicles ?? STATE.vehicles.length} total`;
  document.getElementById('kpi-fleet-detail').textContent = `${m.assigned_vehicles ?? 0} assigned · ${m.maintenance_vehicles ?? 0} maintenance`;
  updateKpiDeltaPill('kpi-delta-fleet', m.available_fleet ?? 0, prev ? prev.available_fleet : null);

  animateCountUp(document.getElementById('kpi-active-deliveries'), m.active_deliveries ?? 0);
  document.getElementById('kpi-pending-count').textContent = `${m.pending_deliveries ?? 0} pending`;
  updateKpiDeltaPill('kpi-delta-active', m.active_deliveries ?? 0, prev ? prev.active_deliveries : null);

  animateCountUp(document.getElementById('kpi-delivered-count'), m.delivered_count ?? 0);
  document.getElementById('kpi-cancelled-count').textContent = `${m.cancelled_count ?? 0} cancelled`;
  updateKpiDeltaPill('kpi-delta-delivered', m.delivered_count ?? 0, prev ? prev.delivered_count : null);

  const pct = Number(m.utilisation_pct ?? 0);
  animateCountUp(document.getElementById('kpi-utilisation-pct'), Math.round(pct), '%');
  document.getElementById('kpi-driver-summary').textContent = `${m.available_drivers ?? 0} / ${m.total_drivers ?? STATE.drivers.length} drivers available`;
  updateKpiDeltaPill('kpi-delta-utilisation', Math.round(pct), prev ? Math.round(Number(prev.utilisation_pct ?? 0)) : null, '%');

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

  renderDashboardBentoCards();
  renderDashboardDateStrip();
  renderDashboardCharts();
  renderDashboardDeliveriesTable();

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
              <span class="lane-card-id">${escapeHtml(d.delivery_id)}${demoBadgeHtml(d.is_demo)}</span>
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

function renderDashboardBentoCards() {
  // 1. Orange Feature Card: "Next dispatch" + Blocked Queue count
  const blockedCountEl = document.getElementById('dash-blocked-count');
  if (blockedCountEl) {
    blockedCountEl.textContent = String((STATE.blockedQueue && STATE.blockedQueue.length) || 0);
  }
  const priorityOrder = { urgent: 0, high: 1, normal: 2, low: 3 };
  const pendingSorted = STATE.deliveries
    .filter((d) => d.status === 'pending')
    .sort((a, b) => {
      const pa = priorityOrder[(a.priority || 'normal').toLowerCase()] ?? 2;
      const pb = priorityOrder[(b.priority || 'normal').toLowerCase()] ?? 2;
      if (pa !== pb) return pa - pb;
      return String(a.scheduled_time || '').localeCompare(String(b.scheduled_time || ''));
    });

  const titleEl = document.getElementById('dash-next-dispatch-title');
  const routeEl = document.getElementById('dash-next-dispatch-route');
  const metaEl = document.getElementById('dash-next-dispatch-meta');
  const dispatchBtn = document.getElementById('btn-dash-next-dispatch');

  if (pendingSorted.length === 0) {
    if (titleEl) titleEl.textContent = 'No pending deliveries';
    if (routeEl) routeEl.textContent = 'Queue is clear — create or import deliveries to dispatch.';
    if (metaEl) metaEl.innerHTML = `<span>Priority: n/a</span><span>Capacity: n/a</span>`;
    if (dispatchBtn) {
      dispatchBtn.disabled = true;
      dispatchBtn.removeAttribute('data-dispatch-delivery');
    }
  } else {
    const nextDel = pendingSorted[0];
    const sla = formatSlaCountdown(nextDel.scheduled_time, nextDel.status);
    if (titleEl) titleEl.textContent = `Order ${nextDel.delivery_id} (${(nextDel.priority || 'normal').toUpperCase()})`;
    if (routeEl) routeEl.textContent = `${nextDel.pickup} → ${nextDel.dropoff}`;
    if (metaEl) {
      metaEl.innerHTML = `
        <span>Cap: ${nextDel.required_capacity != null ? `${escapeHtml(nextDel.required_capacity)} kg` : 'Any'}</span>
        <span>&bull; SLA: ${escapeHtml(sla.text)}</span>
        ${nextDel.is_demo ? '<span>&bull; DEMO</span>' : ''}
      `;
    }
    if (dispatchBtn) {
      dispatchBtn.disabled = false;
      dispatchBtn.setAttribute('data-dispatch-delivery', nextDel.delivery_id);
    }
  }

  // 2. Dark Contrast Card (#14161B): "Today's deliveries" with SLA countdown chips
  const todayIsoPrefix = new Date().toISOString().slice(0, 10);
  const todaysDeliveries = STATE.deliveries.filter((d) => String(d.scheduled_time || '').startsWith(todayIsoPrefix));
  const listSource = todaysDeliveries.length > 0 ? todaysDeliveries : STATE.deliveries.slice(0, 6);
  const countEl = document.getElementById('dash-todays-count');
  const slaListEl = document.getElementById('dash-todays-sla-list');
  if (countEl) countEl.textContent = String(listSource.length);
  if (slaListEl) {
    if (listSource.length === 0) {
      slaListEl.innerHTML = `
        <div class="sla-item">
          <div class="sla-item-route">No deliveries scheduled yet.</div>
        </div>
      `;
    } else {
      slaListEl.innerHTML = listSource.slice(0, 5).map((d) => {
        const sla = formatSlaCountdown(d.scheduled_time, d.status);
        return `
          <div class="sla-item">
            <div class="sla-item-top">
              <span class="sla-item-id">${escapeHtml(d.delivery_id)} &bull; ${escapeHtml(d.status)}</span>
              <span class="sla-countdown-chip ${sla.overdue ? 'overdue' : ''}">${escapeHtml(sla.text)}</span>
            </div>
            <div class="sla-item-route">${escapeHtml(d.pickup)} &rarr; ${escapeHtml(d.dropoff)}</div>
          </div>
        `;
      }).join('');
    }
  }
}

function renderDashboardDateStrip() {
  const stripEl = document.getElementById('dash-date-strip');
  const resultsEl = document.getElementById('dash-date-strip-results');
  const labelEl = document.getElementById('dash-schedule-selected-label');
  if (!stripEl || !resultsEl) return;

  // Build 7-day strip centered around today (-2 days to +4 days) or from existing delivery dates
  const baseDate = new Date();
  baseDate.setHours(0, 0, 0, 0);
  const days = [];
  for (let offset = -1; offset <= 5; offset++) {
    const dt = new Date(baseDate.getTime() + offset * 86400000);
    const isoDate = dt.toISOString().slice(0, 10);
    const dow = dt.toLocaleDateString('en-US', { weekday: 'short' });
    const dayNum = dt.getDate();
    const count = STATE.deliveries.filter((d) => String(d.scheduled_time || '').slice(0, 10) === isoDate).length;
    days.push({ isoDate, dow, dayNum, count });
  }

  stripEl.innerHTML = days.map((day) => {
    const isActive = STATE.scheduleSelectedDate === day.isoDate;
    return `
      <button
        type="button"
        class="date-pill-btn ${isActive ? 'active' : ''}"
        data-schedule-date="${escapeHtml(day.isoDate)}"
        role="tab"
        aria-selected="${isActive}"
      >
        <span class="date-pill-dow">${escapeHtml(day.dow)}</span>
        <span class="date-pill-day tabular">${escapeHtml(day.dayNum)}</span>
        <span class="date-pill-count tabular">${day.count} ord</span>
      </button>
    `;
  }).join('');

  const matching = STATE.scheduleSelectedDate
    ? STATE.deliveries.filter((d) => String(d.scheduled_time || '').slice(0, 10) === STATE.scheduleSelectedDate)
    : STATE.deliveries.slice(0, 4);

  if (labelEl) {
    labelEl.textContent = STATE.scheduleSelectedDate ? `Date: ${STATE.scheduleSelectedDate} (${matching.length})` : `Showing ${matching.length} of ${STATE.deliveries.length} scheduled`;
  }

  if (matching.length === 0) {
    resultsEl.innerHTML = `<div class="chart-empty-state" style="padding:14px;">No deliveries scheduled on ${escapeHtml(STATE.scheduleSelectedDate || 'this period')}.</div>`;
    return;
  }

  resultsEl.innerHTML = matching.slice(0, 5).map((d) => {
    const sla = formatSlaCountdown(d.scheduled_time, d.status);
    return `
      <div style="display:flex; align-items:center; justify-content:space-between; gap:10px; padding:8px 12px; border-radius:12px; background:var(--bg); border:1px solid var(--border); flex-wrap:wrap;">
        <div style="display:flex; align-items:center; gap:8px;">
          <strong class="mono" style="color:var(--orange-700);">${escapeHtml(d.delivery_id)}</strong>
          ${demoBadgeHtml(d.is_demo)}
          <span>${escapeHtml(d.pickup)} &rarr; ${escapeHtml(d.dropoff)}</span>
        </div>
        <div style="display:flex; align-items:center; gap:8px;">
          <span class="mono" style="font-size:11px; color:var(--muted);">${escapeHtml(sla.text)}</span>
          ${priorityBadgeHtml(d.priority)}
          ${statusBadgeHtml(d.status)}
        </div>
      </div>
    `;
  }).join('');
}

function renderDashboardCharts() {
  // 1. Utilisation Over Time (Area SVG with smooth curve + gradient fill)
  const areaEl = document.getElementById('dash-chart-util-area');
  if (areaEl) {
    const pts = STATE.metricsHistory;
    if (!pts || pts.length === 0 || (STATE.vehicles.length === 0 && STATE.deliveries.length === 0)) {
      areaEl.innerHTML = `<div class="chart-empty-state">No data yet</div>`;
    } else {
      const w = 360;
      const h = 175;
      const padL = 32;
      const padR = 14;
      const padT = 16;
      const padB = 26;
      const plotW = w - padL - padR;
      const plotH = h - padT - padB;
      const series = pts.length === 1 ? [pts[0], pts[0]] : pts;
      const coords = series.map((p, idx) => {
        const x = padL + (idx / (series.length - 1)) * plotW;
        const y = padT + plotH - (Math.min(100, Math.max(0, p.utilisation_pct)) / 100) * plotH;
        return { x, y, val: p.utilisation_pct, ts: p.ts };
      });
      let pathD = `M ${coords[0].x.toFixed(1)} ${coords[0].y.toFixed(1)}`;
      for (let i = 0; i < coords.length - 1; i++) {
        const cx = ((coords[i].x + coords[i + 1].x) / 2).toFixed(1);
        pathD += ` C ${cx} ${coords[i].y.toFixed(1)}, ${cx} ${coords[i + 1].y.toFixed(1)}, ${coords[i + 1].x.toFixed(1)} ${coords[i + 1].y.toFixed(1)}`;
      }
      const areaD = `${pathD} L ${coords[coords.length - 1].x.toFixed(1)} ${(padT + plotH).toFixed(1)} L ${coords[0].x.toFixed(1)} ${(padT + plotH).toFixed(1)} Z`;
      areaEl.innerHTML = `
        <svg viewBox="0 0 ${w} ${h}" width="100%" height="180" role="img" aria-label="Fleet utilisation over time area chart">
          <defs>
            <linearGradient id="orangeAreaGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="#F97316" stop-opacity="0.38"/>
              <stop offset="100%" stop-color="#F97316" stop-opacity="0.02"/>
            </linearGradient>
          </defs>
          <line x1="${padL}" y1="${padT}" x2="${w - padR}" y2="${padT}" stroke="var(--border)" stroke-dasharray="3 3" />
          <line x1="${padL}" y1="${padT + plotH / 2}" x2="${w - padR}" y2="${padT + plotH / 2}" stroke="var(--border)" stroke-dasharray="3 3" />
          <line x1="${padL}" y1="${padT + plotH}" x2="${w - padR}" y2="${padT + plotH}" stroke="var(--border)" />
          <text x="4" y="${padT + 4}" font-size="10" font-family="var(--font-mono)" fill="var(--muted)">100%</text>
          <text x="8" y="${padT + plotH / 2 + 4}" font-size="10" font-family="var(--font-mono)" fill="var(--muted)">50%</text>
          <text x="14" y="${padT + plotH + 4}" font-size="10" font-family="var(--font-mono)" fill="var(--muted)">0%</text>
          <path d="${areaD}" fill="url(#orangeAreaGrad)" />
          <path d="${pathD}" fill="none" stroke="#EA580C" stroke-width="2.5" stroke-linecap="round" />
          ${coords.map((c) => `
            <circle cx="${c.x.toFixed(1)}" cy="${c.y.toFixed(1)}" r="4" fill="#C2410C" stroke="#FFFFFF" stroke-width="1.5">
              <title>${escapeHtml(c.ts)}: ${c.val.toFixed(1)}% utilisation</title>
            </circle>
          `).join('')}
        </svg>
      `;
    }
  }

  // 2. Status Funnel (Donut SVG)
  const donutEl = document.getElementById('dash-chart-status-donut');
  if (donutEl) {
    const total = STATE.deliveries.length;
    if (total === 0) {
      donutEl.innerHTML = `<div class="chart-empty-state">No data yet</div>`;
    } else {
      const counts = [
        { label: 'Pending', count: STATE.deliveries.filter((d) => d.status === 'pending').length, color: '#B45309' },
        { label: 'Assigned', count: STATE.deliveries.filter((d) => d.status === 'assigned').length, color: '#1D4ED8' },
        { label: 'In Transit', count: STATE.deliveries.filter((d) => d.status === 'in_transit').length, color: '#F97316' },
        { label: 'Delivered', count: STATE.deliveries.filter((d) => d.status === 'delivered').length, color: '#15803D' },
        { label: 'Cancelled', count: STATE.deliveries.filter((d) => d.status === 'cancelled').length, color: '#B91C1C' },
      ];
      const r = 56;
      const circ = 2 * Math.PI * r;
      let accum = 0;
      const arcs = counts.filter((s) => s.count > 0).map((seg) => {
        const frac = seg.count / total;
        const len = frac * circ;
        const dashArray = `${len.toFixed(2)} ${(circ - len).toFixed(2)}`;
        const dashOffset = (-accum * circ).toFixed(2);
        accum += frac;
        return `<circle cx="80" cy="85" r="${r}" fill="none" stroke="${seg.color}" stroke-width="18" stroke-dasharray="${dashArray}" stroke-dashoffset="${dashOffset}" transform="rotate(-90 80 85)"><title>${seg.label}: ${seg.count} (${Math.round(frac * 100)}%)</title></circle>`;
      }).join('');

      const legend = counts.map((s) => `
        <div style="display:flex; align-items:center; justify-content:space-between; gap:8px; font-size:11.5px;">
          <span style="display:inline-flex; align-items:center; gap:6px; color:var(--ink);">
            <span style="width:9px; height:9px; border-radius:50%; background:${s.color}; display:inline-block;"></span>
            ${escapeHtml(s.label)}
          </span>
          <strong class="mono">${s.count}</strong>
        </div>
      `).join('');

      donutEl.innerHTML = `
        <div style="display:flex; align-items:center; justify-content:space-around; width:100%; gap:12px;">
          <svg viewBox="0 0 160 170" width="150" height="160" role="img" aria-label="Delivery status funnel donut chart">
            <circle cx="80" cy="85" r="${r}" fill="none" stroke="var(--border)" stroke-width="18" />
            ${arcs}
            <text x="80" y="82" text-anchor="middle" font-family="var(--font-heading)" font-size="20" font-weight="800" fill="var(--ink)">${total}</text>
            <text x="80" y="98" text-anchor="middle" font-family="var(--font-mono)" font-size="9" fill="var(--muted)">ORDERS</text>
          </svg>
          <div style="display:flex; flex-direction:column; gap:5px; flex:1; max-width:150px;">${legend}</div>
        </div>
      `;
    }
  }

  // 3. Throughput by Priority (Bar SVG)
  const barsEl = document.getElementById('dash-chart-throughput-bars');
  if (barsEl) {
    if (STATE.deliveries.length === 0) {
      barsEl.innerHTML = `<div class="chart-empty-state">No data yet</div>`;
    } else {
      const groups = [
        { key: 'urgent', label: 'Urgent', color: '#B91C1C' },
        { key: 'high', label: 'High', color: '#EA580C' },
        { key: 'normal', label: 'Normal', color: '#F97316' },
        { key: 'low', label: 'Low', color: '#5B6270' },
      ];
      const counts = groups.map((g) => ({
        ...g,
        count: STATE.deliveries.filter((d) => (d.priority || 'normal').toLowerCase() === g.key).length,
      }));
      const maxVal = Math.max(1, ...counts.map((c) => c.count));
      barsEl.innerHTML = `
        <svg viewBox="0 0 340 175" width="100%" height="175" role="img" aria-label="Delivery throughput by priority bar chart">
          ${counts.map((c, idx) => {
            const barH = Math.max(6, Math.round((c.count / maxVal) * 110));
            const x = 32 + idx * 74;
            const y = 140 - barH;
            return `
              <g>
                <rect x="${x}" y="${y}" width="42" height="${barH}" rx="8" fill="${c.color}">
                  <title>${c.label}: ${c.count} deliveries</title>
                </rect>
                <text x="${x + 21}" y="${y - 6}" text-anchor="middle" font-family="var(--font-mono)" font-size="11" font-weight="700" fill="var(--ink)">${c.count}</text>
                <text x="${x + 21}" y="158" text-anchor="middle" font-family="var(--font-mono)" font-size="10.5" fill="var(--muted)">${c.label}</text>
              </g>
            `;
          }).join('')}
          <line x1="20" y1="140" x2="320" y2="140" stroke="var(--border)" />
        </svg>
      `;
    }
  }
}

function renderDashboardDeliveriesTable() {
  const tbody = document.getElementById('dash-deliveries-tbody');
  const countPill = document.getElementById('dash-table-count-pill');
  const pagEl = document.getElementById('dash-deliveries-pagination');
  if (!tbody) return;

  const allRows = STATE.deliveries;
  if (countPill) countPill.textContent = `${allRows.length} total`;

  if (allRows.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="empty-cell">No deliveries recorded yet.</td></tr>`;
    if (pagEl) pagEl.classList.add('hidden');
    return;
  }

  const pageSize = 200;
  const totalPages = Math.max(1, Math.ceil(allRows.length / pageSize));
  if (STATE.dashDeliveriesPage > totalPages) STATE.dashDeliveriesPage = totalPages;
  const startIdx = (STATE.dashDeliveriesPage - 1) * pageSize;
  const pageRows = allRows.slice(startIdx, startIdx + pageSize);

  const driverMap = new Map(STATE.drivers.map((dr) => [dr.driver_id, dr]));

  tbody.innerHTML = pageRows.map((d) => {
    const sla = formatSlaCountdown(d.scheduled_time, d.status);
    let assignedCell = `<span class="kpi-sub">Unassigned</span>`;
    if (d.active_driver_id || d.active_vehicle_id) {
      const drv = driverMap.get(d.active_driver_id);
      const drvName = drv ? drv.name : (d.active_driver_id || 'Driver');
      const initials = getInitials(drvName);
      assignedCell = `
        <div class="driver-cell">
          <span class="initials-avatar" title="${escapeHtml(drvName)}">${escapeHtml(initials)}</span>
          <div>
            <div style="font-weight:700; font-size:12px;">${escapeHtml(drvName)}</div>
            <div class="mono" style="font-size:11px; color:var(--muted);">${escapeHtml(d.active_vehicle_id || '')}</div>
          </div>
        </div>
      `;
    }

    const actionHtml = d.status === 'pending'
      ? `<button type="button" class="btn btn-primary btn-xs" data-dispatch-delivery="${escapeHtml(d.delivery_id)}">${icon('dispatch', 12)}<span>Dispatch</span></button>`
      : `<span class="mono" style="font-size:11px; color:var(--muted);">${escapeHtml(d.status)}</span>`;

    return `
      <tr>
        <td class="mono"><strong>${escapeHtml(d.delivery_id)}</strong>${demoBadgeHtml(d.is_demo)}</td>
        <td>${escapeHtml(d.pickup)} &rarr; ${escapeHtml(d.dropoff)}</td>
        <td class="mono">
          <div>${escapeHtml(d.scheduled_time)}</div>
          <span class="sla-countdown-chip ${sla.overdue ? 'overdue' : ''}">${escapeHtml(sla.text)}</span>
        </td>
        <td>${priorityBadgeHtml(d.priority)}</td>
        <td>${statusBadgeHtml(d.status)}</td>
        <td>${assignedCell}</td>
        <td class="text-right">${actionHtml}</td>
      </tr>
    `;
  }).join('');

  if (pagEl) {
    if (allRows.length > pageSize) {
      pagEl.classList.remove('hidden');
      pagEl.innerHTML = `
        <span>Showing ${startIdx + 1}–${Math.min(allRows.length, startIdx + pageSize)} of ${allRows.length} rows</span>
        <div style="display:flex; gap:6px;">
          <button type="button" class="btn btn-secondary btn-xs" data-dash-page="${STATE.dashDeliveriesPage - 1}" ${STATE.dashDeliveriesPage <= 1 ? 'disabled' : ''}>Prev</button>
          <button type="button" class="btn btn-secondary btn-xs" data-dash-page="${STATE.dashDeliveriesPage + 1}" ${STATE.dashDeliveriesPage >= totalPages ? 'disabled' : ''}>Next</button>
        </div>
      `;
    } else {
      pagEl.classList.add('hidden');
    }
  }
}

function renderDeliveriesTable() {
  const tbody = document.getElementById('deliveries-tbody');
  const pagEl = document.getElementById('deliveries-pagination');
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
    if (pagEl) pagEl.classList.add('hidden');
    return;
  }

  const pageSize = 200;
  const totalPages = Math.max(1, Math.ceil(rows.length / pageSize));
  if (STATE.deliveriesPage > totalPages) STATE.deliveriesPage = totalPages;
  const startIdx = (STATE.deliveriesPage - 1) * pageSize;
  const pageRows = rows.slice(startIdx, startIdx + pageSize);
  const driverMap = new Map(STATE.drivers.map((dr) => [dr.driver_id, dr]));

  tbody.innerHTML = pageRows
    .map((d) => {
      const sla = formatSlaCountdown(d.scheduled_time, d.status);
      let activeInfo = `<span class="kpi-sub">—</span>`;
      if (d.active_vehicle_id && d.active_driver_id) {
        const drv = driverMap.get(d.active_driver_id);
        const drvName = drv ? drv.name : d.active_driver_id;
        activeInfo = `
          <div class="driver-cell">
            <span class="initials-avatar" title="${escapeHtml(drvName)}">${escapeHtml(getInitials(drvName))}</span>
            <div>
              <code class="mono">${escapeHtml(d.active_vehicle_id)}</code> + <code class="mono">${escapeHtml(d.active_driver_id)}</code>
            </div>
          </div>
        `;
      }

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
          <td class="mono"><strong>${escapeHtml(d.delivery_id)}</strong>${demoBadgeHtml(d.is_demo)}</td>
          <td>${escapeHtml(d.pickup)} &rarr; ${escapeHtml(d.dropoff)}</td>
          <td class="mono">
            <div>${escapeHtml(d.scheduled_time)}</div>
            <span class="sla-countdown-chip ${sla.overdue ? 'overdue' : ''}">${escapeHtml(sla.text)}</span>
          </td>
          <td>${priorityBadgeHtml(d.priority)}</td>
          <td class="mono">${d.required_capacity != null ? `${escapeHtml(d.required_capacity)} kg` : '—'}</td>
          <td>${statusBadgeHtml(d.status)}</td>
          <td>${activeInfo}</td>
          <td class="text-right">${actions}</td>
        </tr>
      `;
    })
    .join('');

  if (pagEl) {
    if (rows.length > pageSize) {
      pagEl.classList.remove('hidden');
      pagEl.innerHTML = `
        <span>Showing ${startIdx + 1}–${Math.min(rows.length, startIdx + pageSize)} of ${rows.length} rows</span>
        <div style="display:flex; gap:6px;">
          <button type="button" class="btn btn-secondary btn-xs" data-deliv-page="${STATE.deliveriesPage - 1}" ${STATE.deliveriesPage <= 1 ? 'disabled' : ''}>Prev</button>
          <button type="button" class="btn btn-secondary btn-xs" data-deliv-page="${STATE.deliveriesPage + 1}" ${STATE.deliveriesPage >= totalPages ? 'disabled' : ''}>Next</button>
        </div>
      `;
    } else {
      pagEl.classList.add('hidden');
    }
  }
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
                <span class="resource-id">${escapeHtml(d.delivery_id)}${demoBadgeHtml(d.is_demo)}</span>
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

  // Update Advisor recommendations for selected delivery with Advisor score bar
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
              const pctScore = Math.min(100, Math.max(0, Number(top.total_score) || 0));
              reasonEl.innerHTML = `
                <div>Recommended Pair: <strong>Vehicle ${escapeHtml(top.vehicle.vehicle_id)}</strong> (${escapeHtml(top.vehicle.type)}, ${escapeHtml(top.vehicle.capacity)}kg, cap score ${escapeHtml(top.capacity_fit_score)}) + <strong>Driver ${escapeHtml(top.driver.driver_id)}</strong> (${escapeHtml(top.driver.name)}, fairness score ${escapeHtml(top.driver_fairness_score)}).</div>
                <div class="advisor-score-bar-track"><div class="advisor-score-bar-fill" style="width:${pctScore}%;"></div></div>
              `;
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
                <span class="resource-id">${escapeHtml(v.vehicle_id)} · ${escapeHtml(v.registration_no)}${demoBadgeHtml(v.is_demo)}</span>
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
                <span class="resource-id">${escapeHtml(dr.driver_id)} · ${escapeHtml(dr.name)}${demoBadgeHtml(dr.is_demo)}</span>
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
          <td class="mono"><strong>${escapeHtml(v.vehicle_id)}</strong>${demoBadgeHtml(v.is_demo)}</td>
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
      const initials = getInitials(d.name);
      return `
        <tr>
          <td class="mono"><strong>${escapeHtml(d.driver_id)}</strong>${demoBadgeHtml(d.is_demo)}</td>
          <td>
            <div class="driver-cell">
              <span class="initials-avatar">${escapeHtml(initials)}</span>
              <span>${escapeHtml(d.name)}</span>
            </div>
          </td>
          <td class="mono">
            <div>
              <span>${escapeHtml(d.phone_e164 || d.phone)}</span>
              <button type="button" class="btn btn-ghost btn-xs ml-xs" data-edit-phone="${escapeHtml(d.driver_id)}" aria-label="Edit driver phone number" title="Update Phone Number" style="padding:1px 5px; font-size:11px; margin-left:4px;">
                ${icon('edit', 10)}
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
  'live-fleet-map': null,
  layers: {
    'vehicle-map': {},
    'delivery-map': {},
    'driver-mini-map': {},
    'live-fleet-map': {},
  },
};

/* ==================== LIVE FLEET TRACKING ENGINE (Task 3) ==================== */
const FLEET_MAP_STATE = {
  map: null,
  markers: new Map(),
  circles: new Map(),
  trails: new Map(),
  showCircles: true,
  activeFilter: 'all',
  driversData: [],
  lastThrottleTs: 0,
};

function computeAccuracyMetrics(accuracy_m) {
  if (accuracy_m == null || !Number.isFinite(accuracy_m) || accuracy_m < 0) {
    return { score: 'n/a', label: 'Unknown', sigma: null, r95: null, conf50: null };
  }
  const score = Math.round(Math.max(0, Math.min(100, 100 * Math.exp(-accuracy_m / 50.0))));
  let label = 'Very poor';
  if (accuracy_m <= 5.0) label = 'Excellent';
  else if (accuracy_m <= 15.0) label = 'Good';
  else if (accuracy_m <= 50.0) label = 'Fair';
  else if (accuracy_m <= 100.0) label = 'Poor';

  const sigma = accuracy_m / 1.509592;
  const r95 = (sigma * 2.4477469).toFixed(1);
  const conf50 = Math.round((1.0 - Math.exp(-(50.0 * 50.0) / (2.0 * sigma * sigma))) * 100);
  return { score, label, sigma: sigma.toFixed(1), r95, conf50 };
}

function initLiveFleetMap() {
  const container = document.getElementById('live-fleet-map');
  if (!container || typeof window.L === 'undefined') return;

  if (FLEET_MAP_STATE.map) {
    setTimeout(() => {
      try { FLEET_MAP_STATE.map.invalidateSize(); } catch {}
    }, 60);
    return FLEET_MAP_STATE.map;
  }

  const map = window.L.map('live-fleet-map', {
    attributionControl: false,
    zoomControl: true,
  }).setView([12.9716, 77.5946], 13);

  window.L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxNativeZoom: 19,
    maxZoom: 22,
    subdomains: ['a', 'b', 'c'],
  }).addTo(map);

  FLEET_MAP_STATE.map = map;
  return map;
}

async function loadLiveDriversFleet() {
  try {
    const data = await apiRequest('/tracking/drivers/live');
    if (!data || !data.drivers) return;

    FLEET_MAP_STATE.driversData = data.drivers;

    const c = data.counts || {};
    const setTxt = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
    setTxt('count-fleet-all', c.total ?? data.drivers.length);
    setTxt('count-fleet-live', c.live ?? 0);
    setTxt('count-fleet-stale', c.stale ?? 0);
    setTxt('count-fleet-offline', c.offline ?? 0);
    setTxt('count-fleet-on-delivery', c.on_delivery ?? 0);

    const syncEl = document.getElementById('fleet-last-sync-time');
    if (syncEl) syncEl.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

    renderDriverFleetList(data.drivers);
    updateAllDriverMarkers(data.drivers);
  } catch (err) {
    console.warn('Failed to load live drivers fleet:', err);
  }
}

function renderDriverFleetList(drivers) {
  const listEl = document.getElementById('driver-fleet-list');
  if (!listEl) return;

  const filter = FLEET_MAP_STATE.activeFilter;
  let filtered = drivers.filter(d => {
    if (filter === 'live') return d.status === 'live';
    if (filter === 'stale') return d.status === 'stale';
    if (filter === 'offline') return d.status === 'offline';
    if (filter === 'on_delivery') return d.vehicle && d.vehicle.delivery_id;
    return true;
  });

  const priority = { live: 0, stale: 1, offline: 2 };
  filtered.sort((a, b) => (priority[a.status] ?? 3) - (priority[b.status] ?? 3));

  if (filtered.length === 0) {
    listEl.innerHTML = `<div class="text-center p-md text-muted" style="font-size:12px;">No drivers match filter "${filter}".</div>`;
    return;
  }

  listEl.innerHTML = filtered.map(d => {
    const fix = d.latest_fix;
    const v = d.vehicle;
    const isLive = d.status === 'live';
    const isStale = d.status === 'stale';
    const statusPillClass = isLive ? 'badge badge-success' : (isStale ? 'badge badge-warning' : 'badge status-inactive');
    const statusDot = isLive ? '<span class="pulse-dot"></span> ' : '';

    let fixDetails = '<div class="kpi-sub" style="font-size:11px;">No GPS fix recorded</div>';
    if (fix) {
      const spd = fix.speed != null ? `${(fix.speed * 3.6).toFixed(1)} km/h` : '0 km/h';
      const scoreTxt = fix.accuracy_score != null ? `Score ${fix.accuracy_score}/100` : 'n/a';
      const r95Txt = fix.radius_95m != null ? `r₉₅: ${fix.radius_95m}m` : '';
      const confTxt = fix.confidence_50m != null ? `50m: ${fix.confidence_50m}%` : '';
      fixDetails = `
        <div style="display:flex; justify-content:space-between; font-size:11px; margin-top:3px; color:var(--color-foreground);">
          <span>±${fix.accuracy.toFixed(1)}m · ${scoreTxt}</span>
          <span>${spd}</span>
        </div>
        <div class="kpi-sub" style="font-size:10px; display:flex; justify-content:space-between; margin-top:1px;">
          <span>${r95Txt} ${confTxt ? '· ' + confTxt : ''}</span>
          <span>${d.age_display || ''}</span>
        </div>
      `;
    }

    const vehicleTag = v ? `
      <span class="badge badge-sm" style="background:rgba(0, 240, 255, 0.1); color:var(--color-primary); font-size:10px;">
        ${escapeHtml(v.registration_no || v.vehicle_id)} (${escapeHtml(v.vehicle_type || 'vehicle')})
      </span>
    ` : '<span class="kpi-sub" style="font-size:10px;">Unassigned</span>';

    const dev = d.device;
    const caps = (dev && dev.capabilities) || {};
    const batPct = caps.battery_pct || (caps.battery && caps.battery.value != null ? `${caps.battery.value}%` : null);
    const batChg = caps.battery && caps.battery.is_charging ? '⚡' : '🔋';
    const netType = caps.network_type || (caps.network && caps.network.effective_type) || null;
    const phoneLabel = dev && (dev.model || dev.os_family) ? `${dev.model || 'Phone'} (${dev.os_family || ''})` : null;
    const phoneTelemetryLine = (batPct || netType || phoneLabel) ? `
      <div class="kpi-sub" style="font-size:10px; display:flex; flex-wrap:wrap; gap:6px; margin-top:4px; padding-top:3px; border-top:1px dashed var(--color-border);">
        ${batPct ? `<span>${batChg} ${escapeHtml(batPct)}</span>` : ''}
        ${netType ? `<span>📶 ${escapeHtml(netType)}</span>` : ''}
        ${phoneLabel ? `<span>📱 ${escapeHtml(phoneLabel)}</span>` : ''}
      </div>
    ` : '';

    return `
      <div class="driver-fleet-card p-xs" data-driver-id="${escapeHtml(d.driver_id)}"
           style="background:var(--color-card); border:1px solid ${isLive ? 'rgba(34, 197, 94, 0.4)' : (isStale ? 'rgba(234, 179, 8, 0.4)' : 'var(--color-border)')};
                  border-radius:var(--radius-sm); padding:8px 10px; cursor:pointer; transition:border-color 0.15s ease;">
        <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:4px;">
          <div>
            <strong style="font-size:12px; color:var(--color-foreground);">${escapeHtml(d.driver_name)}</strong>
            <div style="margin-top:2px;">${vehicleTag}</div>
          </div>
          <span class="${statusPillClass}" style="font-size:10px; padding:2px 6px;">
            ${statusDot}${d.status.toUpperCase()}
          </span>
        </div>
        ${fixDetails}
        ${phoneTelemetryLine}
      </div>
    `;
  }).join('');

  listEl.querySelectorAll('.driver-fleet-card').forEach(card => {
    card.addEventListener('click', () => {
      const did = card.getAttribute('data-driver-id');
      focusDriverOnMap(did);
    });
  });
}

function updateAllDriverMarkers(drivers) {
  const map = FLEET_MAP_STATE.map;
  if (!map || typeof window.L === 'undefined') return;

  drivers.forEach(d => {
    const fix = d.latest_fix;
    if (!fix) return;

    const lat = fix.latitude;
    const lng = fix.longitude;
    const isLive = d.status === 'live';
    const isStale = d.status === 'stale';

    const color = isLive ? '#22C55E' : (isStale ? '#EAB308' : '#94A3B8');
    const opacity = isLive ? 1.0 : (isStale ? 0.8 : 0.45);

    const hdg = fix.heading || 0;
    const customIcon = window.L.divIcon({
      className: 'fleet-driver-pin',
      html: `
        <div style="position:relative; width:32px; height:32px; display:flex; align-items:center; justify-content:center; opacity:${opacity};">
          <div style="position:absolute; width:28px; height:28px; border-radius:50%; background:${color}; border:2px solid #ffffff; box-shadow:0 2px 8px rgba(0,0,0,0.5); display:flex; align-items:center; justify-content:center; transform: rotate(${hdg}deg);">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#000000" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
              <polygon points="12 2 19 21 12 17 5 21 12 2"></polygon>
            </svg>
          </div>
        </div>
      `,
      iconSize: [32, 32],
      iconAnchor: [16, 16],
    });

    let marker = FLEET_MAP_STATE.markers.get(d.driver_id);
    if (!marker) {
      marker = window.L.marker([lat, lng], { icon: customIcon }).addTo(map);
      FLEET_MAP_STATE.markers.set(d.driver_id, marker);
    } else {
      animateMarkerBetweenRealFixes(marker, FLEET_MAP_STATE.circles.get(d.driver_id), [lat, lng]);
      marker.setIcon(customIcon);
    }

    const v = d.vehicle;
    const dev = d.device;
    const caps = (dev && dev.capabilities) || {};
    const batPct = caps.battery_pct || (caps.battery && caps.battery.value != null ? `${caps.battery.value}%` : 'n/a');
    const batChg = caps.battery && caps.battery.is_charging ? '⚡ Charging' : (caps.battery && caps.battery.is_charging === false ? '🔋 Discharging' : '');
    const netType = caps.network_type || (caps.network && caps.network.effective_type) || 'n/a';
    const spd = fix.speed != null ? `${(fix.speed * 3.6).toFixed(1)} km/h` : '0 km/h';
    const scoreTxt = fix.accuracy_score != null ? `${fix.accuracy_score}/100` : 'n/a';
    const r95Txt = fix.radius_95m != null ? `${fix.radius_95m} m` : 'n/a';
    const confTxt = fix.confidence_50m != null ? `${fix.confidence_50m}%` : 'n/a';
    const svUrl = `https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${lat.toFixed(6)},${lng.toFixed(6)}`;

    const popupHtml = `
      <div style="font-family:inherit; min-width:210px; font-size:12px; line-height:1.4;">
        <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #e2e8f0; padding-bottom:4px; margin-bottom:6px;">
          <strong style="font-size:13px; color:#0f172a;">${escapeHtml(d.driver_name)}</strong>
          <span style="font-weight:700; color:${color}; text-transform:uppercase; font-size:10px;">${d.status}</span>
        </div>
        <div><strong>Vehicle:</strong> ${v ? escapeHtml(v.registration_no || v.vehicle_id) : 'None'}</div>
        <div><strong>Speed:</strong> ${spd} · <strong>Heading:</strong> ${hdg.toFixed(0)}°</div>
        <div><strong>Phone Battery:</strong> ${escapeHtml(batPct)} ${escapeHtml(batChg)} · <strong>Net:</strong> ${escapeHtml(netType)}</div>
        <div><strong>Raw Accuracy:</strong> ±${fix.accuracy.toFixed(1)} m</div>
        <div><strong>Accuracy Score:</strong> ${scoreTxt}</div>
        <div><strong>95% Radius:</strong> ${r95Txt} · <strong>50m Conf:</strong> ${confTxt}</div>
        <div><strong>Last Ping:</strong> ${d.age_display || 'Just now'}</div>
        <div style="margin-top:6px; padding-top:4px; border-top:1px solid #e2e8f0;">
          <a href="${svUrl}" target="_blank" rel="noopener noreferrer" style="color:#0284c7; text-decoration:none; font-weight:600;">
            Open Google Street View &rarr;
          </a>
        </div>
      </div>
    `;
    marker.bindPopup(popupHtml);

    let circle = FLEET_MAP_STATE.circles.get(d.driver_id);
    if (!circle) {
      circle = window.L.circle([lat, lng], {
        radius: fix.accuracy,
        color: color,
        fillColor: color,
        fillOpacity: 0.12,
        weight: 1,
      });
      if (FLEET_MAP_STATE.showCircles) circle.addTo(map);
      FLEET_MAP_STATE.circles.set(d.driver_id, circle);
    } else {
      circle.setLatLng([lat, lng]);
      circle.setRadius(fix.accuracy);
      circle.setStyle({ color: color, fillColor: color });
      if (FLEET_MAP_STATE.showCircles && !map.hasLayer(circle)) circle.addTo(map);
      else if (!FLEET_MAP_STATE.showCircles && map.hasLayer(circle)) map.removeLayer(circle);
    }

    if (d.trail && d.trail.length > 1) {
      const latlngs = d.trail.map(p => [p.lat, p.lng]);
      let trail = FLEET_MAP_STATE.trails.get(d.driver_id);
      if (!trail) {
        trail = window.L.polyline(latlngs, {
          color: color,
          weight: 2,
          dashArray: '4, 4',
          opacity: 0.6,
        }).addTo(map);
        FLEET_MAP_STATE.trails.set(d.driver_id, trail);
      } else {
        trail.setLatLngs(latlngs);
        trail.setStyle({ color: color });
      }
    }
  });
}

function focusDriverOnMap(driverId) {
  const map = FLEET_MAP_STATE.map;
  const marker = FLEET_MAP_STATE.markers.get(driverId);
  if (!map || !marker) return;

  const latlng = marker.getLatLng();
  map.setView(latlng, 17, { animate: true });
  marker.openPopup();
}

function animateMarkerBetweenRealFixes(marker, circle, targetLatLng) {
  if (!marker) return;
  const reducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const prev = marker.getLatLng();
  const [targetLat, targetLng] = targetLatLng;
  if (reducedMotion || !prev || (Math.abs(prev.lat - targetLat) < 1e-6 && Math.abs(prev.lng - targetLng) < 1e-6)) {
    marker.setLatLng(targetLatLng);
    if (circle) circle.setLatLng(targetLatLng);
    return;
  }
  const startLat = prev.lat;
  const startLng = prev.lng;
  const startTs = performance.now();
  const duration = 260;
  function step(now) {
    const t = Math.min(1, (now - startTs) / duration);
    const curLat = startLat + (targetLat - startLat) * t;
    const curLng = startLng + (targetLng - startLng) * t;
    marker.setLatLng([curLat, curLng]);
    if (circle) circle.setLatLng([curLat, curLng]);
    if (t < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

const DASH_MAP_STATE = {
  map: null,
  markers: new Map(),
  circles: new Map(),
};

async function updateDashboardLiveMap() {
  const container = document.getElementById('dashboard-live-map');
  if (!container || typeof window.L === 'undefined') return;

  if (!DASH_MAP_STATE.map) {
    DASH_MAP_STATE.map = window.L.map('dashboard-live-map', {
      attributionControl: false,
      zoomControl: true,
    }).setView([12.9716, 77.5946], 12);

    window.L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxNativeZoom: 19,
      maxZoom: 22,
      subdomains: ['a', 'b', 'c'],
    }).addTo(DASH_MAP_STATE.map);
  } else {
    setTimeout(() => {
      try { DASH_MAP_STATE.map.invalidateSize(); } catch {}
    }, 50);
  }

  try {
    const data = await apiRequest('/tracking/drivers/live');
    if (!data || !Array.isArray(data.drivers)) return;
    const driversWithFixes = data.drivers.filter((d) => d.latest_fix);
    const pillEl = document.getElementById('dash-map-driver-count');
    if (pillEl) pillEl.textContent = `${driversWithFixes.length} active fixes`;

    driversWithFixes.forEach((d) => {
      const fix = d.latest_fix;
      const lat = fix.latitude;
      const lng = fix.longitude;
      const isLive = d.status === 'live';
      const color = isLive ? '#EA580C' : '#5B6270';

      const pinIcon = window.L.divIcon({
        className: 'dash-driver-pin',
        html: `<div style="width:24px; height:24px; border-radius:50%; background:${color}; color:#FFFFFF; border:2px solid #FFFFFF; box-shadow:0 2px 6px rgba(22,24,29,0.25); font-family:var(--font-mono); font-size:9px; font-weight:800; display:flex; align-items:center; justify-content:center;">${escapeHtml(getInitials(d.driver_name))}</div>`,
        iconSize: [24, 24],
        iconAnchor: [12, 12],
      });

      let m = DASH_MAP_STATE.markers.get(d.driver_id);
      let c = DASH_MAP_STATE.circles.get(d.driver_id);
      if (!m) {
        m = window.L.marker([lat, lng], { icon: pinIcon }).addTo(DASH_MAP_STATE.map);
        DASH_MAP_STATE.markers.set(d.driver_id, m);
      } else {
        animateMarkerBetweenRealFixes(m, c, [lat, lng]);
        m.setIcon(pinIcon);
      }
      m.bindPopup(`<strong>${escapeHtml(d.driver_name)}</strong><br/>±${Number(fix.accuracy || 0).toFixed(1)}m · ${escapeHtml(d.status)}`);

      if (!c) {
        c = window.L.circle([lat, lng], {
          radius: Number(fix.accuracy || 15),
          color,
          fillColor: color,
          fillOpacity: 0.14,
          weight: 1,
        }).addTo(DASH_MAP_STATE.map);
        DASH_MAP_STATE.circles.set(d.driver_id, c);
      } else {
        c.setRadius(Number(fix.accuracy || 15));
        c.setStyle({ color, fillColor: color });
      }
    });
  } catch (_) {}
}

function fitDashboardDrivers() {
  const map = DASH_MAP_STATE.map;
  if (!map) return;
  const coords = [];
  DASH_MAP_STATE.markers.forEach((m) => coords.push(m.getLatLng()));
  if (coords.length > 0) {
    const bounds = window.L.latLngBounds(coords);
    map.fitBounds(bounds, { padding: [28, 28], maxZoom: 15 });
  }
}

function fitAllFleetDrivers() {
  const map = FLEET_MAP_STATE.map;
  if (!map) return;

  const coords = [];
  FLEET_MAP_STATE.markers.forEach(m => {
    coords.push(m.getLatLng());
  });

  if (coords.length > 0) {
    const bounds = window.L.latLngBounds(coords);
    map.fitBounds(bounds, { padding: [40, 40], maxZoom: 16 });
  }
}

function toggleAccuracyCircles() {
  FLEET_MAP_STATE.showCircles = !FLEET_MAP_STATE.showCircles;
  const map = FLEET_MAP_STATE.map;
  const txt = document.getElementById('txt-toggle-accuracy-circles');
  if (txt) txt.textContent = `Circles: ${FLEET_MAP_STATE.showCircles ? 'ON' : 'OFF'}`;

  FLEET_MAP_STATE.circles.forEach(circle => {
    if (map) {
      if (FLEET_MAP_STATE.showCircles) {
        if (!map.hasLayer(circle)) circle.addTo(map);
      } else {
        if (map.hasLayer(circle)) map.removeLayer(circle);
      }
    }
  });
}

async function openPairDriverModal() {
  const modal = document.getElementById('modal-pair-driver');
  const select = document.getElementById('select-pair-driver-target');
  const resWrap = document.getElementById('pair-token-result');
  if (resWrap) resWrap.classList.add('hidden');

  if (select) {
    select.innerHTML = '<option value="">-- Choose Driver to Pair --</option>' +
      STATE.drivers.map((d, i) => `<option value="${escapeHtml(d.driver_id)}" ${i === 0 ? 'selected' : ''}>${escapeHtml(d.name)} (${escapeHtml(d.driver_id)})</option>`).join('');
  }
  if (modal) modal.classList.remove('hidden');
  if (select && select.value) {
    generateDriverPairToken();
  }
}

async function generateDriverPairToken() {
  const select = document.getElementById('select-pair-driver-target');
  const driverId = select ? select.value : '';
  if (!driverId) {
    alert('Please select a driver to generate pairing token.');
    return;
  }

  try {
    const res = await apiRequest('/api/pairing-tokens', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ driver_id: driverId }),
    });

    const qrContainer = document.getElementById('pair-driver-qr-container');
    const urlInput = document.getElementById('pair-driver-url-input');
    const badgeEl = document.getElementById('pair-driver-name-badge');
    const resWrap = document.getElementById('pair-token-result');

    const primaryUrl = res.tunnel_url || res.url;
    if (urlInput) urlInput.value = primaryUrl;
    if (badgeEl) {
      badgeEl.textContent = res.tunnel_url
        ? `${res.driver_name || res.driver_id} Bound (Public HTTPS Tunnel Active)`
        : `${res.driver_name || res.driver_id} Bound (LAN HTTPS :8443)`;
    }

    if (qrContainer && window.QRCode) {
      qrContainer.innerHTML = '';
      new window.QRCode(qrContainer, {
        text: primaryUrl,
        width: 192,
        height: 192,
        colorDark: '#0f172a',
        colorLight: '#ffffff',
        correctLevel: window.QRCode.CorrectLevel.M,
      });
    }

    if (resWrap) resWrap.classList.remove('hidden');
  } catch (err) {
    alert(`Failed to generate pairing token: ${err.message}`);
  }
}


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
      maxNativeZoom: 19,
      maxZoom: 22,
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
  initLiveFleetMap();
  loadLiveDriversFleet();

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

  const accMetrics = computeAccuracyMetrics(accuracy);
  const accSubEl = document.getElementById('disp-acc-sub');
  if (latEl) latEl.textContent = lat.toFixed(6);
  if (lngEl) lngEl.textContent = lng.toFixed(6);
  if (accEl) accEl.textContent = `${accuracy.toFixed(1)} m`;
  if (accSubEl) {
    accSubEl.textContent = `Score ${accMetrics.score}/100 · ${accMetrics.label} (r₉₅: ${accMetrics.r95}m, 50m conf: ${accMetrics.conf50}%)`;
    accSubEl.className = 'telemetry-sub';
  }
  if (speedEl) speedEl.textContent = speed != null ? speed.toFixed(1) : '0.0';
  if (altEl) altEl.textContent = altitude != null ? `${altitude.toFixed(1)} m` : '—';
  if (headEl) headEl.textContent = heading != null ? `${heading.toFixed(0)}\u00B0` : '—';
  if (countEl) countEl.textContent = TRACKING_STATE.fixCount;
  if (pingEl) pingEl.textContent = 'Just now (0 s ago)';

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
  const saved = localStorage.getItem('fleetwise_theme') || 'light';
  document.documentElement.setAttribute('data-theme', saved);
  updateThemeBtn(saved);
}

function toggleTheme() {
  const cur = document.documentElement.getAttribute('data-theme') || 'light';
  const next = cur === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('fleetwise_theme', next);
  updateThemeBtn(next);
}

function updateThemeBtn(theme) {
  const lbl = document.getElementById('theme-label');
  const iconEl = document.getElementById('theme-icon');
  if (lbl) lbl.textContent = theme === 'dark' ? 'Dark' : 'Light';
  if (iconEl) iconEl.innerHTML = icon(theme === 'dark' ? 'moon' : 'sun', 16);
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
  // Sidebar / Top Pill navigation
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

  // Dashboard Bento & Topbar Listeners
  document.getElementById('btn-dash-fit-drivers')?.addEventListener('click', fitDashboardDrivers);
  document.getElementById('btn-dash-view-blocked')?.addEventListener('click', () => {
    document.getElementById('btn-view-blocked-queue')?.click();
  });
  document.getElementById('btn-dash-schedule-all')?.addEventListener('click', () => {
    STATE.scheduleSelectedDate = null;
    renderDashboardDateStrip();
  });
  document.getElementById('btn-notifications')?.addEventListener('click', () => {
    switchView('analytics');
    showToast('Switched to Analytics & Operational Anomaly Feed');
  });
  document.getElementById('global-search-input')?.addEventListener('input', async (e) => {
    const q = e.target.value;
    const delSearch = document.getElementById('deliveries-search');
    if (delSearch) delSearch.value = q;
    STATE.deliverySearchQuery = q;
    await refreshFilteredDeliveries();
    renderDeliveriesTable();
    if (q.trim() && STATE.activeView === 'dashboard') {
      switchView('deliveries');
    }
  });

  document.addEventListener('click', (e) => {
    const schedBtn = e.target.closest('[data-schedule-date]');
    if (schedBtn) {
      const dt = schedBtn.getAttribute('data-schedule-date');
      STATE.scheduleSelectedDate = STATE.scheduleSelectedDate === dt ? null : dt;
      renderDashboardDateStrip();
      return;
    }
    const dashPageBtn = e.target.closest('[data-dash-page]');
    if (dashPageBtn && !dashPageBtn.disabled) {
      STATE.dashDeliveriesPage = Math.max(1, Number(dashPageBtn.getAttribute('data-dash-page')) || 1);
      renderDashboardDeliveriesTable();
      return;
    }
    const delivPageBtn = e.target.closest('[data-deliv-page]');
    if (delivPageBtn && !delivPageBtn.disabled) {
      STATE.deliveriesPage = Math.max(1, Number(delivPageBtn.getAttribute('data-deliv-page')) || 1);
      renderDeliveriesTable();
      return;
    }
  });

  // Live Fleet Map toolbar & filters
  document.getElementById('btn-open-pair-driver-modal')?.addEventListener('click', openPairDriverModal);
  document.getElementById('btn-fit-all-drivers')?.addEventListener('click', fitAllFleetDrivers);
  document.getElementById('btn-toggle-accuracy-circles')?.addEventListener('click', toggleAccuracyCircles);
  document.getElementById('btn-generate-pair-token')?.addEventListener('click', generateDriverPairToken);
  document.getElementById('btn-copy-pair-url')?.addEventListener('click', () => {
    const input = document.getElementById('pair-driver-url-input');
    if (input && input.value) {
      navigator.clipboard.writeText(input.value).then(() => showToast('Pairing link copied to clipboard!'));
    }
  });

  document.querySelectorAll('.fleet-filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.fleet-filter-btn').forEach(b => {
        b.classList.remove('btn-primary', 'active');
        b.classList.add('btn-secondary');
      });
      btn.classList.remove('btn-secondary');
      btn.classList.add('btn-primary', 'active');
      FLEET_MAP_STATE.activeFilter = btn.getAttribute('data-filter') || 'all';
      renderDriverFleetList(FLEET_MAP_STATE.driversData);
    });
  });

  // Quick buttons
  document.getElementById('btn-refresh-now')?.addEventListener('click', () => refreshAllData());
  document.getElementById('btn-refresh-audit')?.addEventListener('click', () => refreshAllData());
  document.getElementById('btn-quick-dispatch')?.addEventListener('click', () => switchView('dispatch'));
  document.getElementById('btn-cmd-palette')?.addEventListener('click', openCommandPalette);

  // Operator name persistence
  const opInput = document.getElementById('operator-name-input');
  const opAvatar = document.getElementById('operator-initials-chip');
  if (opInput) {
    const savedOp = localStorage.getItem('fleetwise_operator_name') || '';
    opInput.value = savedOp;
    if (opAvatar) opAvatar.textContent = savedOp ? getInitials(savedOp) : 'OP';
    opInput.addEventListener('input', (e) => {
      const v = e.target.value.trim();
      localStorage.setItem('fleetwise_operator_name', v);
      if (opAvatar) opAvatar.textContent = v ? getInitials(v) : 'OP';
    });
  }

  // Demo controls
  document.getElementById('btn-load-demo')?.addEventListener('click', async () => {
    try {
      clearGlobalError();
      let coords = null;
      if (navigator.geolocation) {
        try {
          const pos = await new Promise((res, rej) => navigator.geolocation.getCurrentPosition(res, rej, { timeout: 1000 }));
          coords = { lat: pos.coords.latitude, lon: pos.coords.longitude };
        } catch (_) {}
      }
      const res = await apiRequest('/demo/load', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(coords ? { center_lat: coords.lat, center_lon: coords.lon } : {}),
      });
      if (res.status === 'already_loaded') {
        const counts = res.counts || {};
        showToast(`Demo data already loaded (${counts.vehicles ?? 0} vehicles, ${counts.drivers ?? 0} drivers, ${counts.deliveries ?? 0} deliveries).`);
      } else {
        showToast(`Demo data loaded: ${res.vehicles ?? 12} vehicles, ${res.drivers ?? 15} drivers, ${res.deliveries ?? 25} deliveries.`);
      }
      await refreshAllData();
    } catch (err) {
      showGlobalError(err.code || 'ERROR', err.rawMessage || 'An unexpected error occurred.', err.requestId || '');
    }
  });

  document.getElementById('btn-clear-demo')?.addEventListener('click', async () => {
    try {
      clearGlobalError();
      const res = await apiRequest('/demo/clear', { method: 'POST' });
      const del = res.deleted || {};
      showToast(`Demo data cleared: ${del.vehicles ?? 0} vehicles, ${del.drivers ?? 0} drivers, ${del.deliveries ?? 0} deliveries removed.`);
      await refreshAllData();
    } catch (err) {
      showGlobalError(err.code || 'ERROR', err.rawMessage || 'An unexpected error occurred.', err.requestId || '');
    }
  });

  document.getElementById('btn-sim-toggle')?.addEventListener('click', async () => {
    try {
      clearGlobalError();
      const res = await apiRequest('/demo/simulator/toggle', { method: 'POST' });
      const lbl = document.getElementById('sim-status-label');
      if (lbl) {
        lbl.textContent = res.is_simulator_running ? 'Sim: Running' : 'Sim: Paused';
      }
      showToast(res.is_simulator_running ? 'Demo simulator started.' : 'Demo simulator paused.');
    } catch (err) {
      showGlobalError(err.code || 'ERROR', err.rawMessage || 'An unexpected error occurred.', err.requestId || '');
    }
  });

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
  let targetUrl = `${window.location.origin}/driver`;

  if (_cachedNetInfo) {
    if (target === 'lan-https') {
      targetUrl = _cachedNetInfo.tunnel_driver_url
        || _cachedNetInfo.driver_pairing_url
        || `${_cachedNetInfo.lan_https_url || `https://${_cachedNetInfo.local_ip}:8443`}/driver`;
    } else if (target === 'lan-http') {
      targetUrl = _cachedNetInfo.driver_pairing_url
        || _cachedNetInfo.driver_http_pairing_url
        || `${_cachedNetInfo.lan_url || `http://${_cachedNetInfo.local_ip}:8000`}/driver`;
    } else if (target === 'localhost') {
      const pairQ = _cachedNetInfo.pairing_token ? `?pair=${_cachedNetInfo.pairing_token}` : '';
      targetUrl = `${_cachedNetInfo.localhost_url || 'http://127.0.0.1:8000'}/driver${pairQ}`;
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
  await refreshAllData(true);

  STATE.pollTimer = setInterval(() => {
    if (STATE.pollingEnabled && !document.hidden) {
      refreshAllData(true);
    }
  }, 5000);
});

