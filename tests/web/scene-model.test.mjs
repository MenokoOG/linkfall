import assert from 'node:assert/strict';
import test from 'node:test';
import { MAX_SENTRIES, sceneModel } from '../../src/linkfall/web/js/scene-model.js';

const state = { turn: 1, hp: 100, heat: 40, shields: true, ashgrove: 8, visitors: 0, truce: false };
const run = (patch = {}, extra = {}) => ({ over: false, outcome: null, channel: { enemy_text: false }, state: { ...state, ...patch }, ...extra });
const kinds = (model, kind) => model.units.filter((u) => u.kind === kind).length;

test('no run: a quiet field with the armor standing by', () => {
  const model = sceneModel(null, 55);
  assert.equal(model.phase, 'idle');
  assert.equal(model.units.length, 0);
  assert.equal(model.firing, false);
  assert.match(model.caption, /Standing by/);
});

test('one sentry per Ashgrove unit, placed the same way every time', () => {
  const model = sceneModel(run(), 55);
  assert.equal(model.phase, 'battle');
  assert.equal(kinds(model, 'sentry'), 8);
  assert.equal(model.firing, true);
  assert.deepEqual(model.units, sceneModel(run(), 20).units);
  for (const u of model.units) assert.ok(u.x >= 46 && u.x <= 96, `x ${u.x}`);
  assert.match(model.caption, /turn 1\. 8 Ashgrove sentries ahead\. Shields up\./);
});

test('losing units removes the last ones and leaves the rest where they stood', () => {
  const before = sceneModel(run(), 55).units;
  const after = sceneModel(run({ ashgrove: 5 }), 55).units;
  assert.deepEqual(after, before.slice(0, 5));
});

test('counts are capped and bad numbers draw nothing', () => {
  assert.equal(kinds(sceneModel(run({ ashgrove: 400 }), 55), 'sentry'), MAX_SENTRIES);
  assert.equal(sceneModel(run({ ashgrove: NaN }), 55).units.length, 0);
  assert.equal(sceneModel(run({ ashgrove: -3 }), 55).units.length, 0);
});

test('visitors and their ship stay out of sight before turn 4', () => {
  const early = sceneModel(run({ turn: 3, visitors: 7 }), 55);
  assert.equal(kinds(early, 'visitor'), 0);
  assert.equal(early.dropship, false);
  assert.doesNotMatch(early.caption, /visitor/);
  const late = sceneModel(run({ turn: 4, visitors: 7 }), 55);
  assert.equal(kinds(late, 'visitor'), 7);
  assert.equal(late.dropship, true);
  assert.match(late.caption, /7 visitors on the ground/);
});

test('a truce clears the sentries; visitors still draw fire', () => {
  const calm = sceneModel(run({ truce: true, ashgrove: 0 }), 55);
  assert.equal(calm.phase, 'truce');
  assert.equal(calm.firing, false);
  assert.match(calm.caption, /truce with Ashgrove holds/);
  assert.equal(sceneModel(run({ truce: true, ashgrove: 0, turn: 4, visitors: 2 }), 55).firing, true);
});

test('damage bands, heat, shields and the jammed channel follow the state', () => {
  assert.deepEqual([100, 70, 69, 40, 39, 1, 0].map((hp) => sceneModel(run({ hp }), 55).damage), [0, 0, 1, 1, 2, 2, 3]);
  assert.equal(sceneModel(run({ heat: 60 }), 55).hot, false);
  assert.equal(sceneModel(run({ heat: 61 }), 55).hot, true);
  const down = sceneModel(run({ shields: false }), 55);
  assert.equal(down.shields, false);
  assert.match(down.caption, /Shields down/);
  assert.equal(sceneModel(run({}, { channel: { enemy_text: true } }), 55).jammed, true);
});

test('a finished mission stops the firing and names the outcome', () => {
  const model = sceneModel(run({ hp: 0 }, { over: true, outcome: 'DESTROYED' }), 55);
  assert.equal(model.phase, 'over');
  assert.equal(model.outcome, 'DESTROYED');
  assert.equal(model.firing, false);
  assert.equal(model.caption, 'Cinder Ward. Mission over: DESTROYED.');
});
