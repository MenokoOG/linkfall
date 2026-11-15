// Wires the page together: health, the link knob, starting a run, and the turn loop.
import { ApiError, createApi } from './api.js';
import { renderCards, renderChannel } from './cards-view.js';
import { renderDecision } from './decision-view.js';
import { byId, setText } from './dom.js';
import { describeError } from './errors.js';
import { debriefModel } from './debrief-model.js';
import { openEvents } from './events.js';
import { attachKnob } from './knob.js';
import { addRow } from './log-model.js';
import { renderDebrief, renderLog, renderReplay } from './log-view.js';
import { sceneModel } from './scene-model.js';
import { renderScene } from './scene-view.js';
import { createStore } from './store.js';
import { createTurnController } from './turn-controller.js';
import { emptyTurn } from './turn-model.js';
import { buildKnobTicks, renderBanner, renderForm, renderGauges, renderLink, renderMission } from './view.js';
import { snapLink } from './zones.js';

const SEED_MAX = 4294967295;
const api = createApi();
const store = createStore({
  link: 55, mode: 'story', crew: 'scripted', seed: 4217,
  run: null, health: null, reachable: true, busy: false, error: '',
  turn: emptyTurn(), decision: null, acting: false, message: '', turnError: '',
  rows: [], lines: [], replay: null, replayBusy: false,
});
const controller = createTurnController({
  api,
  store,
  announce: (text) => setText(byId('announce'), text),
});
let stream = null;
let lastLink = store.get().link;

function randomSeed() {
  return crypto.getRandomValues(new Uint32Array(1))[0];
}

async function startRun(event) {
  event.preventDefault();
  const { seed, mode, crew } = store.get();
  if (!Number.isInteger(seed) || seed < 0 || seed > SEED_MAX) {
    store.set({ error: `The seed must be a whole number from 0 to ${SEED_MAX}.` });
    return;
  }
  store.set({ busy: true, error: '' });
  try {
    const run = await api.createRun({ seed, mode, scenario: 'cinder-ward', crew });
    stream?.close();
    controller.reset();
    store.set({ run, rows: [], lines: [], replay: null, replayBusy: false });
    stream = openEvents(run.run_id, { onRow, onStatus: () => {} });
    await controller.startTurn();
  } catch (error) {
    store.set({ error: describeError(error) });
  } finally {
    store.set({ busy: false });
  }
}

function onRow(row) {
  const { rows, lines } = store.get();
  if (rows.length > 0 && row.id <= rows[rows.length - 1].id) return; // a resumed stream repeats nothing
  store.set({ rows: [...rows, row], lines: addRow(lines, row) });
  controller.onRow(row);
}

async function runReplay() {
  const { run } = store.get();
  if (!run) return;
  store.set({ replayBusy: true, replay: null });
  try {
    store.set({ replay: await api.replay(run.run_id) });
  } catch (error) {
    store.set({ replay: { error: describeError(error) } });
  } finally {
    store.set({ replayBusy: false });
  }
}

function render(state) {
  const canAct = Boolean(state.run) && !state.run.over && state.turn.ready && !state.acting;
  renderLink(state.link);
  renderMission(state.run);
  renderGauges(state.run?.state ?? null);
  renderScene(sceneModel(state.run, state.link));
  renderBanner(state.health, state.reachable);
  renderForm(state);
  renderLog(state.lines);
  renderReplay(state.run, state.replay, state.replayBusy);
  renderDebrief(debriefModel(state.run, state.rows));
  renderCards(state.turn, state.decision, (option) => controller.act({ choice: 'manual', action: option.action }), canAct);
  renderChannel(state.run, () => controller.act({ choice: 'manual', action: 'audit_comms' }), canAct);
  renderDecision(
    { run: state.run, turn: state.turn, decision: state.decision, acting: state.acting, message: state.message, error: state.turnError },
    {
      onLodestar: () => controller.act({ choice: 'lodestar' }),
      onSign: (item) => controller.act({ choice: 'sign', agent: item.agent }),
      onDismiss: (item) => controller.dismiss(item.agent),
    },
  );
}

async function loadHealth() {
  try {
    const health = await api.health();
    store.set({ health, reachable: true, crew: health.model === 'up' ? 'model' : 'scripted' });
  } catch (error) {
    store.set({ reachable: !(error instanceof ApiError && error.status === 0) });
  }
}

function init() {
  buildKnobTicks();
  attachKnob(byId('knob'), { getLink: () => store.get().link, onChange: (link) => store.set({ link }) });
  byId('link-range').addEventListener('input', (e) => store.set({ link: snapLink(Number(e.target.value)) }));
  for (const radio of document.querySelectorAll('input[name="mode"]')) {
    radio.addEventListener('change', () => radio.checked && store.set({ mode: radio.value }));
  }
  for (const radio of document.querySelectorAll('input[name="crew"]')) {
    radio.addEventListener('change', () => radio.checked && store.set({ crew: radio.value }));
  }
  byId('seed').addEventListener('input', (e) => store.set({ seed: e.target.value === '' ? NaN : Number(e.target.value) }));
  byId('new-seed').addEventListener('click', () => store.set({ seed: randomSeed() }));
  byId('run-form').addEventListener('submit', startRun);
  byId('replay-run').addEventListener('click', runReplay);
  store.subscribe((state) => {
    if (state.link !== lastLink) {
      lastLink = state.link;
      controller.onLinkChanged();
    }
    render(state);
  });
  render(store.get());
  loadHealth();
}

init();
