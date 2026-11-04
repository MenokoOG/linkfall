import assert from 'node:assert/strict';
import test from 'node:test';
import { ApiError } from '../../src/linkfall/web/js/api.js';
import { createStore } from '../../src/linkfall/web/js/store.js';
import { createTurnController } from '../../src/linkfall/web/js/turn-controller.js';
import { emptyTurn } from '../../src/linkfall/web/js/turn-model.js';

const row = (kind, payload, turn = 1, id = 1) => ({ id, turn, kind, payload });
const ready = row('turn', { phase: 'ready', link: 55 });

function setup(overrides = {}) {
  const calls = [];
  const log = (name, fn) => async (...args) => { calls.push([name, ...args]); return fn(...args); };
  const api = {
    getState: log('getState', async () => ({ over: false, turn: 2, state: {} })),
    startTurn: log('startTurn', async () => ({ turn: 1 })),
    decision: log('decision', async () => ({ zone: 'ASSISTED', verdict: 'EXECUTE', eligible: ['tactical'], held: [] })),
    commit: log('commit', async () => ({
      turn: 1, command: { action: 'flank', zone: 'ASSISTED', manual: false },
      events: [{ kind: 'valid', message: 'VALID flank' }], state: {},
    })),
    dismiss: log('dismiss', async () => ({})),
    ...overrides,
  };
  const store = createStore({
    link: 55, run: { run_id: 'abc123', over: false }, turn: emptyTurn(), decision: null,
    acting: false, message: '', turnError: '',
  });
  const announced = [];
  const timers = [];
  const controller = createTurnController({
    api, store, announce: (t) => announced.push(t),
    schedule: (fn, ms) => { timers.push({ fn, ms }); return timers.length; },
    cancel: (id) => { timers[id - 1].cancelled = true; },
  });
  return { api, store, controller, calls, announced, timers };
}

const names = (calls) => calls.map((c) => c[0]);

test('rows build the cards, announce answers, and ready asks the server for the decision', async () => {
  const { store, controller, calls, announced } = setup();
  controller.onRow(row('turn', { phase: 'open', link: 55 }));
  controller.onRow(row('proposal', { agent: 'systems', kind: 'rules', provenance: 'internal', latency_ms: 1, reply: { action: 'cooldown', say: 'x' } }));
  controller.onRow(row('no_proposal', { agent: 'tactical', kind: 'llm', reason: 'timeout', latency_ms: 9 }));
  controller.onRow(ready);
  await new Promise((r) => setImmediate(r));
  assert.deepEqual(announced, ['systems: cooldown', 'tactical: no proposal']);
  assert.deepEqual(calls.filter((c) => c[0] === 'decision'), [['decision', 'abc123', 55]]);
  assert.equal(store.get().decision.verdict, 'EXECUTE');
  assert.equal(store.get().turn.ready, true);
});

test('engine and command rows refresh the run state', async () => {
  const { controller, calls } = setup();
  controller.onRow(row('engine', { message: 'hi' }));
  controller.onRow(row('command', { action: 'flank' }));
  await new Promise((r) => setImmediate(r));
  assert.deepEqual(names(calls), ['getState', 'getState']);
});

test('starting a turn clears the table and posts the current link', async () => {
  const { store, controller, calls } = setup();
  store.set({ link: 70, decision: { verdict: 'EXECUTE' } });
  await controller.startTurn();
  assert.deepEqual(calls, [['startTurn', 'abc123', 70]]);
  assert.equal(store.get().decision, null);
  assert.equal(store.get().turn.collecting, true);
});

test('a Lodestar commit sends the turn and link, shows what happened, then opens the next turn', async () => {
  const { store, controller, calls } = setup();
  controller.onRow(row('turn', { phase: 'open', link: 55 }));
  controller.onRow(ready);
  calls.length = 0;
  await controller.act({ choice: 'lodestar' });
  assert.deepEqual(calls[0], ['commit', 'abc123', { turn: 1, link: 55, choice: 'lodestar' }]);
  assert.deepEqual(names(calls).slice(1), ['getState', 'startTurn']);
  assert.match(store.get().message, /^Turn 1: Lodestar chose Flank\. VALID flank$/);
  assert.equal(store.get().acting, false);
});

test('a manual pick says "you"; a finished mission does not open another turn', async () => {
  const { store, controller, calls } = setup({
    commit: async () => ({ turn: 1, command: { action: 'hold_shield', zone: 'MANUAL', manual: true }, events: [], state: {} }),
    getState: async () => ({ over: true, outcome: 'SURVIVED' }),
  });
  controller.onRow(row('turn', { phase: 'open', link: 55 }));
  controller.onRow(ready);
  await controller.act({ choice: 'manual', action: 'hold_shield' });
  assert.match(store.get().message, /^Turn 1: you chose Raise shields\.$/);
  assert.equal(store.get().run.over, true);
  assert.equal(calls.some((c) => c[0] === 'startTurn'), false);
});

test('nothing is sent when no turn is ready, when acting, or when the mission is over', async () => {
  const a = setup();
  await a.controller.act({ choice: 'lodestar' });
  const b = setup();
  b.controller.onRow(ready);
  b.store.set({ acting: true });
  await b.controller.act({ choice: 'lodestar' });
  const c = setup();
  c.controller.onRow(ready);
  c.store.set({ run: { run_id: 'abc123', over: true } });
  await c.controller.act({ choice: 'lodestar' });
  for (const s of [a, b, c]) assert.equal(s.calls.some((x) => x[0] === 'commit'), false);
});

test('a refused commit shows the server message and leaves the turn open', async () => {
  const { store, controller } = setup({
    commit: async () => { throw new ApiError(409, 'Lodestar is locked out in the MANUAL zone'); },
  });
  controller.onRow(row('turn', { phase: 'open', link: 55 }));
  controller.onRow(ready);
  await controller.act({ choice: 'lodestar' });
  assert.equal(store.get().turnError, 'Lodestar is locked out in the MANUAL zone');
  assert.equal(store.get().acting, false);
  assert.equal(store.get().turn.ready, true);
});

test('dismiss calls the server and reports a failure', async () => {
  const ok = setup();
  await ok.controller.dismiss('comms');
  assert.deepEqual(ok.calls, [['dismiss', 'abc123', 'comms']]);
  const bad = setup({ dismiss: async () => { throw new ApiError(409, 'nothing to dismiss'); } });
  await bad.controller.dismiss('comms');
  assert.equal(bad.store.get().turnError, 'nothing to dismiss');
});

test('a dismissal row refreshes the decision', async () => {
  const { controller, calls } = setup();
  controller.onRow(ready);
  calls.length = 0;
  controller.onRow(row('pilot', { op: 'dismiss', agent: 'comms' }));
  await new Promise((r) => setImmediate(r));
  assert.deepEqual(names(calls), ['decision']);
});

test('link changes are debounced into one preview request', async () => {
  const { controller, timers, calls } = setup();
  controller.onRow(ready);
  calls.length = 0;
  controller.onLinkChanged();
  controller.onLinkChanged();
  controller.onLinkChanged();
  assert.equal(timers.length, 3);
  assert.deepEqual(timers.map((t) => t.cancelled === true), [true, true, false]);
  assert.equal(timers[2].ms, 150);
  timers[2].fn();
  await new Promise((r) => setImmediate(r));
  assert.deepEqual(names(calls), ['decision']);
});

test('a 409 on the preview is quiet; other errors are shown', async () => {
  const quiet = setup({ decision: async () => { throw new ApiError(409, 'the turn is collecting'); } });
  quiet.controller.onRow(ready);
  await new Promise((r) => setImmediate(r));
  assert.equal(quiet.store.get().turnError, '');
  const loud = setup({ decision: async () => { throw new ApiError(500, 'boom'); } });
  loud.controller.onRow(ready);
  await new Promise((r) => setImmediate(r));
  assert.equal(loud.store.get().turnError, 'boom');
});

test('answers that arrive after a new run starts are dropped', async () => {
  let release;
  const slow = new Promise((resolve) => { release = resolve; });
  const { store, controller } = setup({ decision: async () => { await slow; return { verdict: 'EXECUTE', eligible: [], held: [] }; } });
  controller.onRow(ready);
  controller.reset();
  release();
  await new Promise((r) => setImmediate(r));
  assert.equal(store.get().decision, null);
});
