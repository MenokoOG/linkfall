import assert from 'node:assert/strict';
import test from 'node:test';
import { MODE_HELP, ZONES, ZONE_INFO, isValidLink, snapLink, zoneFor } from '../../src/linkfall/web/js/zones.js';

test('zone boundaries match the policy', () => {
  const expected = { 10: 'MANUAL', 25: 'MANUAL', 30: 'ASSISTED', 55: 'ASSISTED', 60: 'DELEGATED', 90: 'DELEGATED' };
  for (const [link, zone] of Object.entries(expected)) assert.equal(zoneFor(Number(link)), zone, link);
});

test('only 10 to 90 in steps of 5 is a valid link', () => {
  for (let v = 10; v <= 90; v += 5) assert.equal(isValidLink(v), true, v);
  for (const bad of [0, 5, 12, 95, 100, -10, 55.5, '55', null, undefined, NaN, true]) assert.equal(isValidLink(bad), false, String(bad));
});

test('snapLink rounds to the step and stays in range', () => {
  assert.equal(snapLink(12), 10);
  assert.equal(snapLink(13), 15);
  assert.equal(snapLink(57.4), 55);
  assert.equal(snapLink(-50), 10);
  assert.equal(snapLink(500), 90);
  assert.equal(snapLink(NaN), 10);
  assert.equal(snapLink(Infinity), 10);
});

test('every zone has words and an icon, and none says autonomous', () => {
  assert.deepEqual(Object.keys(ZONE_INFO).sort(), Object.keys(ZONES).sort());
  for (const info of Object.values(ZONE_INFO)) {
    assert.ok(info.name && info.help && info.icon.startsWith('/assets/'));
    assert.doesNotMatch(`${info.name} ${info.help}`, /autonom/i);
  }
  for (const text of Object.values(MODE_HELP)) assert.doesNotMatch(text, /autonom/i);
});
