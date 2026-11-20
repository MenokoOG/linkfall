// Wires the range page: load the targets, start a run, poll it once a second, recheck it.
// A poll of one small JSON object stands in for a stream here (plan 2026-11-15, section 5).
import { ApiError, createApi } from './api.js';
import { pickBackend } from './backend.js';
import { byId, setText } from './dom.js';
import { saveText } from './download.js';
import { describeError } from './errors.js';
import { announcements, isLive, progress, reportFileName, reportPath } from './range-model.js';
import { renderRange } from './range-view.js';
import { createStore } from './store.js';

const POLL_MS = 1000;
const RETRY_MS = 3000;
const backend = await pickBackend();
const api = createApi(backend.fetchFn);
const store = createStore({
  catalog: null, reachable: true, target: 'reference', run: null,
  starting: false, error: '', check: null, checking: false,
});
let timer = null;

const unreachable = (error) => error instanceof ApiError && error.status === 0;

async function loadCatalog() {
  try {
    store.set({ catalog: await api.range(), reachable: true });
  } catch (error) {
    store.set({ reachable: !unreachable(error), error: describeError(error) });
  }
}

async function poll(runId) {
  timer = null;
  let run;
  try {
    run = await api.getRange(runId);
  } catch (error) {
    store.set({ reachable: !unreachable(error), error: describeError(error) });
    if (unreachable(error)) timer = setTimeout(() => poll(runId), RETRY_MS);
    return;
  }
  const { catalog } = store.get();
  const said = announcements(catalog, run, store.get().run?.probes.length ?? 0);
  if (!isLive(run)) said.push(progress(catalog, run));
  store.set({ run, reachable: true, error: '' });
  if (said.length > 0) setText(byId('range-announce'), said.join(' '));
  if (isLive(run)) timer = setTimeout(() => poll(runId), POLL_MS);
  else await loadCatalog(); // the model's health may have changed while the run was going
}

async function start(event) {
  event.preventDefault();
  if (timer !== null) clearTimeout(timer);
  store.set({ starting: true, error: '', check: null, run: null });
  try {
    const { run_id: runId } = await api.startRange(store.get().target);
    byId('h-score').focus(); // the start button is about to be disabled; keep the keyboard on the page
    await poll(runId);
  } catch (error) {
    store.set({ error: describeError(error) });
  } finally {
    store.set({ starting: false });
  }
}

async function runRecheck() {
  const { run } = store.get();
  if (!run) return;
  store.set({ checking: true, check: null });
  try {
    store.set({ check: await api.recheckRange(run.run_id) });
  } catch (error) {
    store.set({ check: { error: describeError(error) } });
  } finally {
    store.set({ checking: false });
  }
}

// The hosted copy has no server route to link to, so the report is fetched from the in-tab app
// and saved as a file made in the page.
async function downloadReport(event) {
  event.preventDefault();
  const { run } = store.get();
  if (!run) return;
  try {
    const response = await backend.fetchFn(reportPath(run.run_id), { method: 'GET', headers: { Accept: 'text/markdown' } });
    if (!response.ok) throw new ApiError(response.status, `The server answered ${response.status}.`);
    saveText(await response.text(), reportFileName(run.run_id), 'text/markdown');
  } catch (error) {
    store.set({ error: describeError(error) });
  }
}

function init() {
  const onPick = (target) => store.set({ target });
  byId('range-form').addEventListener('submit', start);
  byId('recheck-range').addEventListener('click', runRecheck);
  if (backend.local) byId('range-report').addEventListener('click', downloadReport);
  store.subscribe((state) => renderRange(state, onPick));
  renderRange(store.get(), onPick);
  loadCatalog();
}

init();
