/**
 * FleetWise Device Battery Telemetry Engine
 * Implements strict Truthfulness Contract for device battery states.
 * Never fabricates data, defaults to 100%, or assumes causes without measurement.
 */

async function inspectDeviceBattery(options = {}) {
  const nav = options.nav !== undefined ? options.nav : (typeof navigator !== 'undefined' ? navigator : null);
  const isDesktop = options.isDesktop !== undefined
    ? Boolean(options.isDesktop)
    : (typeof window !== 'undefined' && Boolean(window.__isDesktopClient));
  const timestamp = new Date().toISOString();

  // 1. API missing -> status "unavailable", reason "navigator.getBattery not supported by this browser"
  if (!nav || typeof nav.getBattery !== 'function') {
    return {
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
      measured_at: timestamp,
      raw: {
        level: null,
        charging: null,
        chargingTime: null,
        dischargingTime: null,
      },
    };
  }

  // 2. Query BatteryManager (Promise handling)
  let battery;
  try {
    battery = await nav.getBattery();
  } catch (err) {
    // Promise rejects -> status "error", include the real error message
    const errorMsg = (err && (err.message || err.name)) ? String(err.message || err.name) : 'Battery query promise rejected';
    return {
      status: 'error',
      reason: errorMsg,
      source: 'navigator.getBattery',
      level: null,
      pct: null,
      charging: null,
      chargingState: null,
      chargingTime: null,
      dischargingTime: null,
      label: 'Client Device Battery (Current browser device)',
      display_status: 'error',
      is_suspect: false,
      measured_at: timestamp,
      raw: {
        level: null,
        charging: null,
        chargingTime: null,
        dischargingTime: null,
      },
    };
  }

  // Extract raw values from BatteryManager
  const rawLevel = battery.level;
  const rawCharging = battery.charging;
  const rawChargingTime = battery.chargingTime;
  const rawDischargingTime = battery.dischargingTime;

  // Format Infinity as explicit string "Infinity"
  const chargingTimeFormatted = rawChargingTime === Infinity ? 'Infinity' : rawChargingTime;
  const dischargingTimeFormatted = rawDischargingTime === Infinity ? 'Infinity' : rawDischargingTime;

  const pct = rawLevel != null && !isNaN(rawLevel) ? Math.round(rawLevel * 100) : null;
  const pctStr = pct != null ? `${pct}%` : null;

  let chargingStateStr = null;
  if (rawCharging === true) {
    chargingStateStr = 'Charging';
  } else if (rawCharging === false) {
    chargingStateStr = 'Discharging';
  }

  // 3. Resolves with exactly level=1, charging=true, chargingTime=0, dischargingTime=Infinity on a desktop browser
  // -> status "measured_suspect", reason "values equal the API's defaults; the browser may not be reading a battery".
  // Show them labeled "browser-reported, unverified", never as confirmed.
  const isSuspectDefault =
    isDesktop &&
    rawLevel === 1 &&
    rawCharging === true &&
    rawChargingTime === 0 &&
    rawDischargingTime === Infinity;

  if (isSuspectDefault) {
    return {
      status: 'measured_suspect',
      reason: "values equal the API's defaults; the browser may not be reading a battery",
      source: 'navigator.getBattery',
      level: rawLevel,
      pct: pctStr,
      charging: rawCharging,
      chargingState: chargingStateStr,
      chargingTime: chargingTimeFormatted,
      dischargingTime: dischargingTimeFormatted,
      label: 'Client Device Battery (Current browser device)',
      display_status: 'browser-reported, unverified',
      is_suspect: true,
      measured_at: timestamp,
      raw: {
        level: rawLevel,
        charging: rawCharging,
        chargingTime: chargingTimeFormatted,
        dischargingTime: dischargingTimeFormatted,
      },
    };
  }

  // 4. Resolves normally -> status "measured", value from the BatteryManager
  return {
    status: 'measured',
    reason: null,
    source: 'navigator.getBattery',
    level: rawLevel,
    pct: pctStr,
    charging: rawCharging,
    chargingState: chargingStateStr,
    chargingTime: chargingTimeFormatted,
    dischargingTime: dischargingTimeFormatted,
    label: 'Client Device Battery (Current browser device)',
    display_status: 'measured',
    is_suspect: false,
    measured_at: timestamp,
    raw: {
      level: rawLevel,
      charging: rawCharging,
      chargingTime: chargingTimeFormatted,
      dischargingTime: dischargingTimeFormatted,
    },
  };
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { inspectDeviceBattery };
}
if (typeof window !== 'undefined') {
  window.inspectDeviceBattery = inspectDeviceBattery;
}

