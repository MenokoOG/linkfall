// The four crew cards and the squad channel card.
import { AGENTS, SIGNATURE_NORMAL, describeAction } from './copy.js';
import { byId, clear, h, keepFocus, setText } from './dom.js';
import { cardStatus, manualOptions } from './turn-model.js';

function waiting() {
  return h(
    'div',
    { class: 'loading' },
    h('img', { src: '/assets/state-loading.svg', alt: '', width: 44, height: 44 }),
    h('span', {}, 'Waiting for the link to sync'),
  );
}

function body(data) {
  if (data.status === 'waiting') return waiting();
  if (data.status === 'none') return h('p', { class: 'muted' }, data.reason ?? 'No reply.');
  return h(
    'div',
    {},
    h('div', { class: 'mono-well' }, describeAction(data.action, data.order)),
    h('p', { class: 'say' }, `“${data.say}”`),
  );
}

function card(agent, data, decision, option, onManual, canAct) {
  const status = cardStatus(data, agent.id, decision);
  const head = h(
    'div',
    { class: 'agent-head' },
    h('img', { src: `/assets/avatar-${agent.id}.svg`, alt: '', width: 44, height: 44 }),
    h('h3', { id: `agent-${agent.id}` }, agent.title),
  );
  if (data.kind) head.append(h('span', { class: 'chip-sm' }, data.kind));
  if (data.provenance) {
    head.append(h('img', { class: 'badge', src: `/assets/badge-${data.provenance}.svg`, alt: data.provenance, width: 100, height: 26 }));
  }
  head.append(h('span', { class: 'spacer' }), h('b', { class: 'status' }, status));
  const article = h(
    'article',
    { class: 'agent-card well', 'data-status': data.dismissed ? 'dismissed' : data.status, 'aria-labelledby': `agent-${agent.id}` },
    head,
    body(data),
  );
  if (option && canAct) {
    const button = h('button', { type: 'button', class: 'btn btn-small', 'data-key': `run-${agent.id}` }, `Run: ${option.label}`);
    button.setAttribute('aria-label', `Run ${option.label} as proposed by ${agent.title}`);
    button.addEventListener('click', () => onManual(option));
    article.append(button);
  }
  return article;
}

export function renderCards(turn, decision, onManual, canAct) {
  const root = byId('cards');
  const options = new Map(manualOptions(turn, decision).map((o) => [o.agent, o]));
  keepFocus(root, () => {
    clear(root);
    for (const agent of AGENTS) root.append(card(agent, turn.cards[agent.id], decision, options.get(agent.id), onManual, canAct));
  }, 'h-decision');
}

export function renderChannel(run, onAudit, canAct) {
  const channel = run?.channel;
  const label = byId('channel-label');
  const card = byId('channel');
  const audit = byId('audit-comms');
  if (!channel) {
    setText(label, 'Squad channel');
    setText(byId('channel-text'), 'No run yet.');
    setText(byId('channel-sig'), '');
    card.setAttribute('data-hostile', 'false');
    audit.hidden = true;
    return;
  }
  setText(label, channel.enemy_text ? 'Enemy channel · untrusted' : 'Squad channel');
  setText(byId('channel-text'), `“${channel.text}”`);
  const low = channel.signature < SIGNATURE_NORMAL;
  setText(byId('channel-sig'), `Signature ${channel.signature.toFixed(2)}${low ? `, below the normal ${SIGNATURE_NORMAL}` : ''}`);
  card.setAttribute('data-hostile', String(channel.enemy_text));
  card.setAttribute('data-low', String(low));
  audit.hidden = !run.state?.compromised;
  audit.disabled = !canAct;
  audit.onclick = onAudit;
}
