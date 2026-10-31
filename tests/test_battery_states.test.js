/**
 * Unit tests for battery states according to the Truthfulness Contract.
 * Uses mocked navigator.getBattery strictly inside test fixtures.
 */
const test = require('node:test');
const assert = require('node:assert/strict');
const { inspectDeviceBattery } = require('../static/js/battery_telemetry.js');

test('State 1: API missing -> status "unavailable" with standard reason', async () => {
  // Mock navigator without getBattery
  const mockNav = {};
  const res = await inspectDeviceBattery({ nav: mockNav, isDesktop: false });

  assert.equal(res.status, 'unavailable');
  assert.equal(res.reason, 'navigator.getBattery not supported by this browser');
  assert.equal(res.level, null);
  assert.equal(res.pct, null);
  assert.equal(res.charging, null);
  assert.equal(res.display_status, 'unavailable');
  assert.equal(res.is_suspect, false);
});

test('State 1b: Navigator is completely null/undefined -> status "unavailable"', async () => {
  const res = await inspectDeviceBattery({ nav: null, isDesktop: false });

  assert.equal(res.status, 'unavailable');
  assert.equal(res.reason, 'navigator.getBattery not supported by this browser');
  assert.equal(res.level, null);
  assert.equal(res.pct, null);
});

test('State 2: Promise rejects -> status "error" with real error message', async () => {
  const realError = new Error('Permission to access battery denied by platform policy');
  const mockNav = {
    getBattery: () => Promise.reject(realError),
  };
  const res = await inspectDeviceBattery({ nav: mockNav, isDesktop: false });

  assert.equal(res.status, 'error');
  assert.equal(res.reason, 'Permission to access battery denied by platform policy');
  assert.equal(res.level, null);
  assert.equal(res.pct, null);
  assert.equal(res.charging, null);
  assert.equal(res.display_status, 'error');
  assert.equal(res.is_suspect, false);
});

test('State 3: Resolves normally -> status "measured" with BatteryManager values', async () => {
  const mockBatteryManager = {
    level: 0.74,
    charging: false,
    chargingTime: Infinity,
    dischargingTime: 3600,
  };
  const mockNav = {
    getBattery: () => Promise.resolve(mockBatteryManager),
  };
  const res = await inspectDeviceBattery({ nav: mockNav, isDesktop: true });

  assert.equal(res.status, 'measured');
  assert.equal(res.reason, null);
  assert.equal(res.level, 0.74);
  assert.equal(res.pct, '74%');
  assert.equal(res.charging, false);
  assert.equal(res.chargingState, 'Discharging');
  assert.equal(res.chargingTime, 'Infinity');
  assert.equal(res.dischargingTime, 3600);
  assert.equal(res.display_status, 'measured');
  assert.equal(res.is_suspect, false);
});

test('State 4: Resolves with exact defaults (level=1, charging=true, chargingTime=0, dischargingTime=Infinity) on desktop -> status "measured_suspect"', async () => {
  const mockBatteryManager = {
    level: 1.0,
    charging: true,
    chargingTime: 0,
    dischargingTime: Infinity,
  };
  const mockNav = {
    getBattery: () => Promise.resolve(mockBatteryManager),
  };
  const res = await inspectDeviceBattery({ nav: mockNav, isDesktop: true });

  assert.equal(res.status, 'measured_suspect');
  assert.equal(res.reason, "values equal the API's defaults; the browser may not be reading a battery");
  assert.equal(res.level, 1.0);
  assert.equal(res.pct, '100%');
  assert.equal(res.charging, true);
  assert.equal(res.chargingState, 'Charging');
  assert.equal(res.chargingTime, 0);
  assert.equal(res.dischargingTime, 'Infinity');
  assert.equal(res.display_status, 'browser-reported, unverified');
  assert.equal(res.is_suspect, true);
});

test('State 4b: Resolves with exact defaults on mobile -> status "measured" (not suspect)', async () => {
  const mockBatteryManager = {
    level: 1.0,
    charging: true,
    chargingTime: 0,
    dischargingTime: Infinity,
  };
  const mockNav = {
    getBattery: () => Promise.resolve(mockBatteryManager),
  };
  const res = await inspectDeviceBattery({ nav: mockNav, isDesktop: false });

  assert.equal(res.status, 'measured');
  assert.equal(res.reason, null);
  assert.equal(res.is_suspect, false);
  assert.equal(res.display_status, 'measured');
});

