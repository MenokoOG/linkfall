// Wires the page together: health, the link knob, starting a run, and the live state.
import { ApiError, createApi } from './api.js';
import { byId } from './dom.js';
import { openEvents } from './events.js';
import { attachKnob } from './knob.js';
import { createStore } from './store.js';
import { buildKnobTicks, renderBanner, renderForm, renderGauges, renderLink, renderMission } from './view.js';
import { snapLink } from './zones.js';

const SEED_MAX = 4294967295;
const api = createApi();
const store = createStore({
  link: 55, mode: 'story', crew: 'scripted', seed: 4217,
  run: null, health: null, reachable: true, busy: false, error: '',
});
let stream = null;

function describe(error) {
  if (!(error instanceof ApiError)) return 'Something went wrong. Try again.';
  const fields = error.fields.map((f) => `${f.field}: ${f.problem}`);
  return fields.length ? `${error.message} (${fields.join('; ')})` : error.message;
}

function randomSeed() {
  return crypto.getRandomValues(new Uint32Array(1))[0];
}

async function refreshState() {
  const run = store.get().run;
  if (!run) return;
  try {
    store.set({ run: { ...run, ...(await api.getState(run.run_id)) } });
  } catch (error) {
    store.set({ error: describe(error) });
  }
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
    store.set({ run });
    stream = openEvents(run.run_id, {
      onRow: (row) => {
        if (row.kind === 'engine' || row.kind === 'command') refreshState();
      },
      onStatus: () => {},
    });
  } catch (error) {
    store.set({ error: describe(error) });
  } finally {
    store.set({ busy: false });
  }
}

function render(state) {
  renderLink(state.link);
  renderMission(state.run);
  renderGauges(state.run?.state ?? null);
  renderBanner(state.health, state.reachable);
  renderForm(state);
}

async function loadHealth() {
  try {
    const health = await api.health();
    store.set({ health, reachable: true, crew: health.model === 'up' ? 'model' : 'scripted' });
  } catch {
    store.set({ reachable: false });
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
  store.subscribe(render);
  render(store.get());
  loadHealth();
}

init();
