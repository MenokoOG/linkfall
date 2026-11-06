import assert from 'node:assert/strict';
import test from 'node:test';
import { addRow, describeRow } from '../../src/linkfall/web/js/log-model.js';

const row = (id, kind, payload, turn = 1) => ({ id, turn, kind, payload });

test('engine rows keep their message and take a tone from their kind', () => {
  assert.deepEqual(describeRow(row(1, 'engine', { kind: 'enemy_fire', message: 'Enemy fire: -4 integrity.' })), {
    id: 1, turn: 1, tone: 'warn', text: 'Enemy fire: -4 integrity.',
  });
  assert.equal(describeRow(row(2, 'engine', { kind: 'valid', message: 'VALID flank' })).tone, 'info');
  assert.equal(describeRow(row(3, 'engine', { kind: 'over', message: 'Mission over: SURVIVED.' })).tone, 'over');
});

test('turn open is a line, turn ready and command rows are not', () => {
  assert.equal(describeRow(row(1, 'turn', { phase: 'open', link: 85 }, 2)).text, 'Turn 2 opens at link 85.');
  assert.equal(describeRow(row(2, 'turn', { phase: 'ready', link: 85 })), null);
  assert.equal(describeRow(row(3, 'command', { action: 'flank', manual: false, zone: 'ASSISTED' })), null);
});

test('proposals read as sentences, and a relayed order names its order', () => {
  const reply = (action, args = null) => ({ agent: 'comms', kind: 'llm', reply: { action, args, say: '' }, provenance: 'external' });
  assert.equal(describeRow(row(1, 'proposal', { ...reply('relay_order', { order: 'drop_shields' }), agent: 'comms' })).text, 'Comms proposes Relay order (drop_shields).');
  assert.equal(describeRow(row(2, 'proposal', { ...reply(null), agent: 'vitals' })).text, 'Vitals advises no action.');
  assert.equal(describeRow(row(3, 'no_proposal', { agent: 'tactical', reason: 'timeout' })).text, 'Tactical gave no proposal (timeout).');
});

test('decision, selector and pilot rows', () => {
  assert.equal(
    describeRow(row(1, 'decision', { verdict: 'ASK_PILOT', zone: 'ASSISTED', held: [{ agent: 'comms' }], eligible: [] })).text,
    'Policy: Your call (assisted). 1 held for your word.',
  );
  assert.equal(describeRow(row(2, 'selector', { chosen: 'tactical', fallback: null, reason: 'Fits.' })).text, 'Lodestar chose Tactical. Fits.');
  assert.match(describeRow(row(3, 'selector', { chosen: 'systems', fallback: 'timeout', reason: '' })).text, /pick failed \(timeout\)/);
  assert.equal(describeRow(row(4, 'pilot', { op: 'sign', agent: 'comms', action: 'accept_truce' })).text, "You signed Comms's proposal: Accept truce.");
  assert.equal(describeRow(row(5, 'pilot', { op: 'dismiss', agent: 'comms' })).text, "You dismissed Comms's proposal.");
  assert.equal(describeRow(row(6, 'pilot', { op: 'lodestar' })).tone, 'pilot');
});

test('unknown row kinds add nothing', () => {
  assert.equal(describeRow(row(1, 'mystery', {})), null);
});

test('addRow appends in order and ignores a repeated row', () => {
  const a = row(1, 'engine', { kind: 'system', message: 'one' });
  const b = row(2, 'engine', { kind: 'system', message: 'two' });
  let lines = addRow([], a);
  lines = addRow(lines, b);
  assert.deepEqual(lines.map((l) => l.text), ['one', 'two']);
  assert.equal(addRow(lines, b), lines);
  assert.equal(addRow(lines, a), lines);
  assert.equal(addRow(lines, row(3, 'command', {})), lines);
});
