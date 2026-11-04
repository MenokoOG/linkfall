import assert from 'node:assert/strict';
import test from 'node:test';
import { forceRows, gaugeRows } from '../../src/linkfall/web/js/gauges-model.js';

const state = { hp: 82, power: 80, heat: 72, ammo: 31, strain: 41, shields: true, ashgrove: 8, visitors: 0, truce: false, turn: 1 };

test('five gauges with the limits that matter marked', () => {
  const rows = gaugeRows(state);
  assert.deepEqual(rows.map((r) => r.id), ['integrity', 'power', 'heat', 'ammo', 'strain']);
  assert.equal(rows.find((r) => r.id === 'heat').mark, 60);
  assert.equal(rows.find((r) => r.id === 'ammo').mark, 15);
  assert.equal(rows.find((r) => r.id === 'integrity').pct, 82);
  assert.equal(rows.find((r) => r.id === 'heat').tone, 'flare');
});

test('percentages stay between 0 and 100', () => {
  const rows = gaugeRows({ ...state, hp: -5, heat: 140, ammo: NaN });
  assert.equal(rows.find((r) => r.id === 'integrity').pct, 0);
  assert.equal(rows.find((r) => r.id === 'heat').pct, 100);
  assert.equal(rows.find((r) => r.id === 'ammo').pct, 0);
});

test('force counters: visitors hidden before turn 4, truce replaces the count, shields flag', () => {
  const early = Object.fromEntries(forceRows(state).map((r) => [r.id, r]));
  assert.equal(early.ashgrove.value, '8');
  assert.equal(early.visitors.value, '--');
  assert.equal(early.shields.value, 'UP');
  assert.equal(early.shields.bad, false);
  const late = Object.fromEntries(forceRows({ ...state, turn: 4, visitors: 7, truce: true, shields: false }).map((r) => [r.id, r]));
  assert.equal(late.ashgrove.value, 'TRUCE');
  assert.equal(late.visitors.value, '7');
  assert.equal(late.shields.value, 'DOWN');
  assert.equal(late.shields.bad, true);
});
