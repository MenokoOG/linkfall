// Draws the page from state. Every string goes in as text.
import { byId, clear, h, setText } from './dom.js';
import { forceRows, gaugeRows } from './gauges-model.js';
import { linkToAngle, tickStates } from './knob-math.js';
import { MODE_HELP, ZONE_INFO, zoneFor } from './zones.js';

export function buildKnobTicks() {
  const stage = byId('knob-stage');
  const knob = byId('knob');
  for (const tick of tickStates(10)) {
    const element = h('div', { class: 'tick', 'data-on': 'false' });
    element.style.setProperty('--angle', `${tick.angle}deg`);
    stage.insertBefore(element, knob);
  }
}

export function renderLink(link) {
  const zone = zoneFor(link);
  const info = ZONE_INFO[zone];
  document.body.dataset.zone = zone;
  setText(byId('knob-readout'), String(link));
  const knob = byId('knob');
  knob.setAttribute('aria-valuenow', String(link));
  knob.setAttribute('aria-valuetext', `${link}, ${info.name}`);
  byId('knob').querySelector('.knob-dot').style.setProperty('--knob-angle', `${linkToAngle(link)}deg`);
  byId('link-range').value = String(link);
  byId('zone-icon').setAttribute('src', info.icon);
  setText(byId('zone-name'), info.name);
  setText(byId('zone-help'), info.help);
  const ticks = byId('knob-stage').querySelectorAll('.tick');
  tickStates(link).forEach((tick, i) => ticks[i].setAttribute('data-on', String(tick.on)));
}

export function renderMission(run) {
  if (!run) {
    setText(byId('run-chip'), 'No run yet');
    setText(byId('turn-chip'), 'Turn - of -');
    return;
  }
  const maxTurns = run.max_turns ?? '-';
  setText(byId('run-chip'), `Run ${run.run_id.slice(0, 6)} · seed ${run.seed} · ${run.mode}`);
  setText(byId('turn-chip'), run.over ? `Mission over: ${run.outcome}` : `Turn ${run.turn} of ${maxTurns}`);
}

export function renderGauges(state) {
  const gauges = byId('gauges');
  const forces = byId('forces');
  clear(gauges);
  clear(forces);
  if (!state) {
    gauges.append(h('p', { class: 'muted' }, 'Start a run to see the armor.'));
    return;
  }
  for (const row of gaugeRows(state)) {
    const element = h(
      'div',
      { class: 'gauge', 'data-tone': row.tone },
      h('div', { class: 'gauge-top' }, h('span', {}, row.label), h('b', {}, String(row.value))),
      h('div', { class: 'gauge-track' }, h('div', { class: 'gauge-fill' })),
    );
    element.style.setProperty('--pct', `${row.pct}%`);
    if (row.mark !== undefined) {
      const mark = h('div', { class: 'gauge-mark', 'aria-hidden': 'true' });
      mark.style.setProperty('--mark', `${row.mark}%`);
      element.querySelector('.gauge-track').append(mark);
    }
    gauges.append(element);
  }
  for (const row of forceRows(state)) {
    forces.append(h('div', { class: 'force', 'data-bad': String(row.bad) }, h('span', {}, row.label), h('b', {}, row.value)));
  }
}

export function renderBanner(health, reachable) {
  const banner = byId('banner');
  let text = '';
  let tone = 'warn';
  if (!reachable) text = 'The server cannot be reached. Check that it is running.';
  else if (health?.model === 'down') text = 'The model server is offline. The scripted crew still works.';
  else if (health?.model === 'not_configured') {
    text = 'No model is set up. Runs use the scripted crew.';
    tone = 'ok';
  }
  banner.hidden = text === '';
  banner.setAttribute('data-tone', tone);
  setText(byId('banner-text'), text);
}

export function renderForm(state) {
  const modelUp = state.health?.model === 'up';
  setText(byId('mode-help'), MODE_HELP[state.mode]);
  setText(byId('crew-help'), modelUp ? 'The model crew runs Tactical, Comms and Lodestar on a local model.' : 'The model crew needs a running model server.');
  document.querySelector('input[name="crew"][value="model"]').disabled = !modelUp;
  for (const radio of document.querySelectorAll('input[name="mode"]')) radio.checked = radio.value === state.mode;
  for (const radio of document.querySelectorAll('input[name="crew"]')) radio.checked = radio.value === state.crew;
  const seed = byId('seed');
  if (document.activeElement !== seed) seed.value = String(state.seed);
  const start = byId('start-run');
  start.disabled = state.busy;
  setText(start, state.run ? 'Start a new run' : 'Start run');
  setText(byId('form-error'), state.error);
}
