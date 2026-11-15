// Draws the range page. Every string goes in as text, and a stated value is marked by wrapping
// its own text node, never by building markup (ASVS 3.2.2).
import { byId, clear, h, setText } from './dom.js';
import { isLive, itemRows, progress, recheckModel, reportPath, scorecard, targetOptions, transcripts } from './range-model.js';

function renderTargets(options, selected, locked, onPick) {
  const box = byId('range-targets');
  if (box.childElementCount !== options.length) {
    clear(box);
    for (const option of options) {
      const input = h('input', { type: 'radio', name: 'target', value: option.name });
      input.addEventListener('change', () => input.checked && onPick(option.name));
      box.append(h('label', { class: 'target' }, input, h('b', {}, option.label), h('small', {})));
    }
  }
  options.forEach((option, index) => {
    const label = box.children[index];
    const input = label.querySelector('input');
    input.checked = option.name === selected;
    input.disabled = option.disabled || locked;
    label.setAttribute('data-off', String(input.disabled));
    setText(label.querySelector('small'), option.blurb);
  });
}

function renderItems(rows) {
  const list = byId('range-items');
  clear(list);
  for (const row of rows) {
    list.append(h('div', { class: 'fact', 'data-stated': row.stated }, h('dt', {}, row.label), h('dd', {}, row.text)));
  }
}

function renderScore(rows) {
  const body = byId('range-score-body');
  clear(body);
  for (const row of rows) {
    body.append(
      h('tr', {},
        h('th', { scope: 'row' }, row.id),
        h('td', {}, row.technique, h('small', {}, `Rule ${row.rule}`)),
        h('td', { 'data-tone': row.tone }, row.word)),
    );
  }
}

function lineNode(line) {
  const item = h('li', { class: 'line', 'data-role': line.role }, h('b', {}, line.who));
  if (line.failed) item.append(h('span', { class: 'line-flag' }, line.failed));
  else item.append(...line.parts.map((part) => (part.item ? h('mark', { class: 'stated' }, part.text) : part.text)));
  if (line.stated) item.append(h('span', { class: 'line-flag' }, line.stated));
  if (line.action) item.append(h('span', { class: 'line-note' }, line.action));
  if (line.note) item.append(h('span', { class: 'line-note' }, line.note));
  return item;
}

// Appends only the probes not yet drawn, so nothing already on the page moves or is rebuilt.
function renderTranscripts(run, probes) {
  const box = byId('range-transcripts');
  const key = run?.run_id ?? '';
  if (box.dataset.run !== key || probes.length < box.childElementCount) {
    clear(box);
    box.dataset.run = key;
  }
  for (const probe of probes.slice(box.childElementCount)) {
    box.append(
      h('article', { class: 'probe' },
        h('h3', {}, probe.title),
        h('p', { class: 'probe-verdict', 'data-tone': probe.tone }, probe.word),
        h('ol', { class: 'lines' }, ...probe.lines.map(lineNode))),
    );
  }
  byId('range-transcripts-empty').hidden = probes.length > 0;
}

function renderRecheck(run, check, busy) {
  byId('recheck-range').disabled = !run || isLive(run) || busy;
  const model = recheckModel(check, busy);
  const box = byId('recheck-result');
  box.hidden = model.tone === 'none';
  box.setAttribute('data-tone', model.tone);
  setText(byId('recheck-head'), model.head);
  setText(byId('recheck-detail'), model.detail);
  const print = byId('recheck-print');
  print.hidden = !model.fingerprint;
  setText(print, model.fingerprint ?? '');
  const link = byId('range-report');
  link.hidden = !run || isLive(run);
  if (run) link.setAttribute('href', reportPath(run.run_id));
}

function renderLimits(limits) {
  const list = byId('range-limits');
  if (list.childElementCount === limits.length) return;
  clear(list);
  for (const text of limits) list.append(h('li', {}, text));
}

export function renderRange(state, onPick) {
  const { catalog, run } = state;
  const locked = state.starting || isLive(run);
  const banner = byId('range-banner');
  banner.hidden = state.reachable;
  setText(byId('range-banner-text'), state.reachable ? '' : 'The server could not be reached. The page will keep trying while a run is open.');
  setText(byId('range-chip'), run ? `Run ${run.run_id} · ${run.target}` : 'No range run yet');
  renderTargets(targetOptions(catalog), state.target, locked, onPick);
  byId('start-range').disabled = locked || !catalog;
  setText(byId('range-error'), state.error);
  setText(byId('range-progress'), state.starting && !run ? 'Starting the range.' : progress(catalog, run));
  renderItems(itemRows(catalog, run));
  renderScore(scorecard(catalog, run));
  renderTranscripts(run, transcripts(catalog, run));
  renderRecheck(run, state.check, state.checking);
  renderLimits(catalog?.limits ?? []);
}
