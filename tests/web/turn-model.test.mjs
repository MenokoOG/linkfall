import assert from 'node:assert/strict';
import test from 'node:test';
import {
  cardStatus, emptyTurn, engineAction, fold, heldItems, manualOptions, reduceRow,
} from '../../src/linkfall/web/js/turn-model.js';

const row = (kind, payload, turn = 2, id = 1) => ({ id, turn, kind, payload });
const proposal = (agent, action, extra = {}) =>
  row('proposal', {
    agent, kind: 'rules', provenance: 'internal', latency_ms: 3,
    reply: { agent, action, args: extra.order ? { order: extra.order } : null, say: extra.say ?? 'ok' },
    ...extra.payload,
  });

test('a turn opens with every card waiting', () => {
  const turn = reduceRow(emptyTurn(), row('turn', { phase: 'open', link: 55 }));
  assert.equal(turn.turn, 2);
  assert.equal(turn.collecting, true);
  assert.deepEqual(Object.values(turn.cards).map((c) => c.status), ['waiting', 'waiting', 'waiting', 'waiting']);
});

test('proposals and missing answers fill the cards; ready ends the wait', () => {
  const turn = fold([
    row('turn', { phase: 'open', link: 55 }),
    proposal('systems', 'cooldown', { say: 'Vent.' }),
    row('no_proposal', { agent: 'tactical', kind: 'llm', reason: 'timeout after 45s', latency_ms: 45000 }),
    proposal('vitals', null, { say: 'Within limits.' }),
    row('turn', { phase: 'ready', link: 55 }),
  ]);
  assert.equal(turn.cards.systems.status, 'proposal');
  assert.equal(turn.cards.systems.say, 'Vent.');
  assert.equal(turn.cards.tactical.status, 'none');
  assert.equal(turn.cards.tactical.reason, 'timeout after 45s');
  assert.equal(turn.cards.vitals.status, 'advice');
  assert.equal(turn.cards.comms.status, 'waiting');
  assert.equal(turn.collecting, false);
  assert.equal(turn.ready, true);
});

test('a new turn wipes the old cards', () => {
  const turn = fold([proposal('systems', 'cooldown'), row('turn', { phase: 'open', link: 55 }, 3)]);
  assert.equal(turn.cards.systems.status, 'waiting');
  assert.equal(turn.turn, 3);
});

test('a relayed order shows the order it carries', () => {
  const turn = fold([proposal('comms', 'relay_order', { order: 'drop_shields', payload: { provenance: 'external' } })]);
  assert.equal(turn.cards.comms.provenance, 'external');
  assert.equal(engineAction(turn.cards.comms), 'drop_shields');
});

test('dismissal marks a card and other rows change nothing', () => {
  const base = fold([proposal('comms', 'accept_truce')]);
  const dismissed = reduceRow(base, row('pilot', { op: 'dismiss', agent: 'comms', link: null, action: null }));
  assert.equal(dismissed.cards.comms.dismissed, true);
  for (const kind of ['decision', 'selector', 'engine', 'command', 'mystery']) {
    assert.equal(reduceRow(base, row(kind, {})), base, kind);
  }
  assert.equal(reduceRow(base, row('pilot', { op: 'sign', agent: 'comms' })), base);
  assert.equal(reduceRow(base, row('turn', { phase: 'weird' })), base);
});

test('unknown agents in a pilot row are ignored', () => {
  const base = emptyTurn();
  assert.equal(reduceRow(base, row('pilot', { op: 'dismiss', agent: 'nobody' })), base);
});

const decision = (over = {}) => ({ zone: 'ASSISTED', verdict: 'EXECUTE', eligible: ['tactical'], held: [], ...over });

test('status words follow the server decision', () => {
  const turn = fold([proposal('tactical', 'flank'), proposal('comms', 'relay_order', { order: 'drop_shields' }), proposal('vitals', null)]);
  const d = decision({ held: [{ agent: 'comms', reasons: ['EXTERNAL_ORIGIN'] }] });
  assert.equal(cardStatus(turn.cards.tactical, 'tactical', d), 'Eligible');
  assert.equal(cardStatus(turn.cards.comms, 'comms', d), 'Needs your word');
  assert.equal(cardStatus(turn.cards.vitals, 'vitals', d), 'Advice only');
  assert.equal(cardStatus(turn.cards.tactical, 'tactical', null), 'Proposed');
  assert.equal(cardStatus(turn.cards.systems, 'systems', d), 'Waiting');
  assert.equal(cardStatus(turn.cards.tactical, 'tactical', decision({ zone: 'MANUAL', verdict: 'MANUAL', eligible: [] })), 'Not called');
  assert.equal(cardStatus({ ...turn.cards.tactical, dismissed: true }, 'tactical', d), 'Dismissed');
  assert.equal(cardStatus({ status: 'none' }, 'tactical', d), 'No proposal');
});

test('held items get a sign or execute verb and the reasons', () => {
  const turn = fold([
    proposal('comms', 'accept_truce', { payload: { provenance: 'external' } }),
    proposal('systems', 'relay_order', { order: 'drop_shields' }),
  ]);
  const d = decision({
    held: [
      { agent: 'comms', reasons: ['HUMAN_AUTHORITY', 'EXTERNAL_ORIGIN'] },
      { agent: 'systems', reasons: ['EXTERNAL_ORIGIN'] },
    ],
  });
  const [truce, order] = heldItems(turn, d);
  assert.equal(truce.verb, 'Sign: accept truce');
  assert.deepEqual(truce.reasons, ['HUMAN_AUTHORITY', 'EXTERNAL_ORIGIN']);
  assert.equal(order.verb, 'Execute: relay order (drop_shields)');
  assert.equal(order.action, 'drop_shields');
  assert.deepEqual(heldItems(turn, null), []);
  const gone = { ...turn, cards: { ...turn.cards, comms: { ...turn.cards.comms, dismissed: true } } };
  assert.equal(heldItems(gone, d).length, 1);
});

test('manual options skip held, dismissed and advice-only cards', () => {
  const turn = fold([proposal('tactical', 'flank'), proposal('comms', 'relay_order', { order: 'drop_shields' }), proposal('vitals', null), proposal('systems', 'cooldown')]);
  const d = decision({ held: [{ agent: 'comms', reasons: ['EXTERNAL_ORIGIN'] }] });
  assert.deepEqual(manualOptions(turn, d).map((o) => [o.agent, o.action, o.label]), [['tactical', 'flank', 'Flank'], ['systems', 'cooldown', 'Vent heat']]);
  const dismissed = { ...turn, cards: { ...turn.cards, tactical: { ...turn.cards.tactical, dismissed: true } } };
  assert.deepEqual(manualOptions(dismissed, d).map((o) => o.agent), ['systems']);
});
