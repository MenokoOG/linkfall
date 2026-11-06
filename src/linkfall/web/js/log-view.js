// The event log, the replay check and the debrief. Every string goes in as text.
import { byId, clear, h, setText } from './dom.js';

// Appends only the lines not yet drawn, so a screen reader hears each new line once.
export function renderLog(lines) {
  const list = byId('log');
  if (lines.length < list.childElementCount) clear(list);
  for (const line of lines.slice(list.childElementCount)) {
    list.append(h('li', { class: 'log-line', 'data-tone': line.tone }, h('span', { class: 'log-turn' }, `T${line.turn}`), ' ', line.text));
  }
  const empty = byId('log-empty');
  empty.hidden = lines.length > 0;
}

// What the replay area says, from the server's answer. Exported for tests.
export function replayModel(replay, busy) {
  if (busy) return { tone: 'busy', head: 'Replaying from the log', detail: '' };
  if (!replay) return { tone: 'none', head: '', detail: '' };
  if (replay.error) return { tone: 'fail', head: 'Replay could not run', detail: replay.error };
  if (!replay.ok) {
    const f = replay.failure;
    return { tone: 'fail', head: 'Replay failed', detail: f ? `First bad row ${f.row_id}: ${f.reason}` : 'The log did not replay.' };
  }
  return { tone: 'ok', head: 'Replay matches', detail: `${replay.turns} turns, no model called.`, fingerprint: replay.fingerprint };
}

export function renderReplay(run, replay, busy) {
  const button = byId('replay-run');
  button.disabled = !run || busy;
  const model = replayModel(replay, busy);
  const box = byId('replay-result');
  box.hidden = model.tone === 'none';
  box.setAttribute('data-tone', model.tone);
  setText(byId('replay-head'), model.head);
  setText(byId('replay-detail'), model.detail);
  const print = byId('replay-print');
  print.hidden = !model.fingerprint;
  setText(print, model.fingerprint ?? '');
}

export function renderDebrief(model) {
  const card = byId('debrief');
  card.hidden = model === null;
  if (!model) return;
  setText(byId('debrief-outcome'), model.outcome);
  setText(byId('debrief-mode'), `${model.mode} mode`);
  const facts = byId('debrief-facts');
  clear(facts);
  for (const f of model.facts) facts.append(h('div', { class: 'fact' }, h('dt', {}, f.label), h('dd', {}, f.value)));
  const notes = byId('debrief-notes');
  clear(notes);
  for (const n of model.notes) notes.append(h('li', {}, n));
}
