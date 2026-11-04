import assert from 'node:assert/strict';
import test from 'node:test';
import { panelModel } from '../../src/linkfall/web/js/decision-view.js';
import { emptyTurn } from '../../src/linkfall/web/js/turn-model.js';

const run = (over = {}) => ({ run_id: 'x', mode: 'story', over: false, outcome: null, ...over });
const open = { ...emptyTurn(), ready: true, turn: 2 };
const decision = (over = {}) => ({ zone: 'ASSISTED', verdict: 'EXECUTE', eligible: ['tactical'], held: [], ...over });

test('no run, mission over and still collecting each get their own message', () => {
  assert.equal(panelModel({ run: null, turn: emptyTurn(), decision: null }).canAct, false);
  const over = panelModel({ run: run({ over: true, outcome: 'DESTROYED' }), turn: open, decision: decision() });
  assert.deepEqual([over.head, over.text, over.canAct], ['Mission over', 'DESTROYED', false]);
  const waiting = panelModel({ run: run(), turn: { ...emptyTurn(), collecting: true }, decision: null });
  assert.equal(waiting.head, 'Crew reporting');
  assert.equal(waiting.canAct, false);
});

test('the verdict decides whether Lodestar can be asked to act', () => {
  assert.equal(panelModel({ run: run(), turn: open, decision: decision() }).canAct, true);
  assert.equal(panelModel({ run: run(), turn: open, decision: decision({ verdict: 'ASK_PILOT', eligible: [] }) }).canAct, true);
  const manual = panelModel({ run: run(), turn: open, decision: decision({ zone: 'MANUAL', verdict: 'MANUAL', eligible: [] }) });
  assert.equal(manual.canAct, false);
  assert.equal(manual.manual, true);
  assert.equal(panelModel({ run: run(), turn: open, decision: decision(), acting: true }).canAct, false);
});

test('the deliberate-weakness note shows only for delegated Lodestar in story mode', () => {
  const warn = (mode, zone) => panelModel({ run: run({ mode }), turn: open, decision: decision({ zone }) }).warn;
  assert.equal(warn('story', 'DELEGATED'), true);
  assert.equal(warn('hardened', 'DELEGATED'), false);
  assert.equal(warn('story', 'ASSISTED'), false);
});
