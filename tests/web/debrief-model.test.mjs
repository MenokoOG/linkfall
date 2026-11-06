import assert from 'node:assert/strict';
import test from 'node:test';
import { debriefModel } from '../../src/linkfall/web/js/debrief-model.js';
import { replayModel } from '../../src/linkfall/web/js/log-view.js';

const row = (kind, payload) => ({ id: 1, turn: 1, kind, payload });
const over = { over: true, outcome: 'SURVIVED', mode: 'story', turn: 5, max_turns: 5, state: { hp: 41, shields: true, truce: true } };

test('no debrief until the mission is over', () => {
  assert.equal(debriefModel(null, []), null);
  assert.equal(debriefModel({ ...over, over: false }, []), null);
});

test('the debrief counts what the log says', () => {
  const rows = [
    row('command', { action: 'overcharge', manual: false }),
    row('command', { action: 'drop_shields', manual: false }),
    row('command', { action: 'flank', manual: true }),
    row('pilot', { op: 'sign' }),
    row('pilot', { op: 'dismiss' }),
    row('pilot', { op: 'dismiss' }),
  ];
  const model = debriefModel(over, rows);
  const fact = (label) => model.facts.find((f) => f.label === label).value;
  assert.equal(model.outcome, 'SURVIVED');
  assert.equal(fact('Turns played'), '5 of 5');
  assert.equal(fact('Actions run'), '3');
  assert.equal(fact('Chosen by Lodestar'), '2');
  assert.equal(fact('Chosen by you'), '1');
  assert.equal(fact('Signatures you gave'), '1');
  assert.equal(fact('Proposals you dismissed'), '2');
  assert.equal(fact('Final integrity'), '41');
  assert.equal(fact('Shields at the end'), 'Up');
  assert.deepEqual(model.notes, ['Drop shields ran on 1 turn. Only the enemy channel asks for it.', 'A truce was signed.']);
});

test('no shield note when shields never dropped', () => {
  assert.deepEqual(debriefModel({ ...over, state: { hp: 3, shields: false, truce: false } }, []).notes, []);
});

test('replay model: busy, matching, failing and unreachable', () => {
  assert.equal(replayModel(null, false).tone, 'none');
  assert.equal(replayModel(null, true).tone, 'busy');
  const ok = replayModel({ ok: true, turns: 5, fingerprint: 'abc' }, false);
  assert.deepEqual([ok.tone, ok.head, ok.fingerprint], ['ok', 'Replay matches', 'abc']);
  const bad = replayModel({ ok: false, failure: { row_id: 9, reason: 'edited' } }, false);
  assert.deepEqual([bad.tone, bad.detail], ['fail', 'First bad row 9: edited']);
  assert.equal(replayModel({ error: 'down' }, false).detail, 'down');
});
