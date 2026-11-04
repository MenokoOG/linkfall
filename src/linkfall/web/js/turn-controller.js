// Runs the turn loop for the page: open a turn, fold the log rows into cards, ask the server
// what the policy would decide, and send the pilot's choice. No DOM here, so it can be tested.
import { actionLabel } from './copy.js';
import { describeError } from './errors.js';
import { emptyTurn, reduceRow } from './turn-model.js';

export const PREVIEW_DELAY_MS = 150;

export function createTurnController({
  api,
  store,
  announce = () => {},
  schedule = (fn, ms) => setTimeout(fn, ms),
  cancel = (id) => clearTimeout(id),
}) {
  let timer = null;
  let generation = 0; // bumps when a new run starts, so late answers for an old run are dropped

  const current = () => store.get();
  const stale = (g) => g !== generation;

  async function refreshState() {
    const { run } = current();
    if (!run) return;
    const g = generation;
    try {
      const state = await api.getState(run.run_id);
      if (!stale(g)) store.set({ run: { ...current().run, ...state } });
    } catch (error) {
      if (!stale(g)) store.set({ turnError: describeError(error) });
    }
  }

  async function refreshPreview() {
    const { run, turn, link } = current();
    if (!run || run.over || !turn.ready) return;
    const g = generation;
    try {
      const decision = await api.decision(run.run_id, link);
      if (!stale(g)) store.set({ decision });
    } catch (error) {
      if (!stale(g) && error.status !== 409) store.set({ turnError: describeError(error) });
    }
  }

  function describeRow(row) {
    const who = row.payload.agent;
    if (row.kind === 'proposal') return `${who}: ${row.payload.reply?.action ?? 'advice'}`;
    return `${who}: no proposal`;
  }

  function onRow(row) {
    store.set({ turn: reduceRow(current().turn, row) });
    if (row.kind === 'proposal' || row.kind === 'no_proposal') announce(describeRow(row));
    if (row.kind === 'engine' || row.kind === 'command') refreshState();
    if ((row.kind === 'turn' && row.payload.phase === 'ready') || (row.kind === 'pilot' && row.payload.op === 'dismiss')) {
      refreshPreview();
    }
  }

  async function startTurn() {
    const { run, link } = current();
    if (!run || run.over) return;
    const g = generation;
    store.set({ turn: { ...emptyTurn(), collecting: true }, decision: null });
    try {
      await api.startTurn(run.run_id, link);
    } catch (error) {
      if (!stale(g)) store.set({ turnError: describeError(error) });
    }
  }

  function summary(result) {
    const who = result.command.manual ? 'you' : 'Lodestar';
    const outcome = result.events.find((e) => e.kind === 'valid' || e.kind === 'rejected');
    return `Turn ${result.turn}: ${who} chose ${actionLabel(result.command.action)}. ${outcome ? outcome.message : ''}`.trim();
  }

  async function act(choice) {
    const { run, turn, link, acting } = current();
    if (!run || run.over || acting || turn.turn === null || !turn.ready) return;
    const g = generation;
    store.set({ acting: true, turnError: '' });
    try {
      const result = await api.commit(run.run_id, { turn: turn.turn, link, ...choice });
      if (stale(g)) return;
      store.set({ decision: null, message: summary(result) });
      await refreshState();
      if (!stale(g) && !current().run.over) await startTurn();
    } catch (error) {
      if (!stale(g)) store.set({ turnError: describeError(error) });
    } finally {
      if (!stale(g)) store.set({ acting: false });
    }
  }

  async function dismiss(agent) {
    const { run, acting } = current();
    if (!run || acting) return;
    try {
      await api.dismiss(run.run_id, agent);
    } catch (error) {
      store.set({ turnError: describeError(error) });
    }
  }

  function onLinkChanged() {
    if (timer !== null) cancel(timer);
    timer = schedule(() => {
      timer = null;
      refreshPreview();
    }, PREVIEW_DELAY_MS);
  }

  function reset() {
    generation += 1;
    store.set({ turn: emptyTurn(), decision: null, message: '', turnError: '', acting: false });
  }

  return { onRow, startTurn, act, dismiss, onLinkChanged, refreshPreview, reset };
}
