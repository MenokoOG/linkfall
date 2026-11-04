// The Lodestar decision panel and the "Needs your word" tray.
import { AGENTS, REASON_TEXT, VERDICT_COPY, WEAKNESS_TEXT } from './copy.js';
import { byId, clear, h, keepFocus, setText } from './dom.js';
import { heldItems } from './turn-model.js';

const title = (id) => AGENTS.find((a) => a.id === id)?.title ?? id;

// What the panel should say, from facts only. Exported so it can be tested without a DOM.
export function panelModel({ run, turn, decision, acting }) {
  if (!run) return { head: 'No run yet', text: 'Start a run to see the crew.', canAct: false, warn: false };
  if (run.over) return { head: 'Mission over', text: String(run.outcome ?? ''), canAct: false, warn: false };
  if (turn.collecting || !turn.ready || !decision) {
    return { head: 'Crew reporting', text: 'Waiting for every agent to answer.', canAct: false, warn: false };
  }
  const copy = VERDICT_COPY[decision.verdict] ?? { head: String(decision.verdict), text: '' };
  return {
    head: copy.head,
    text: copy.text,
    canAct: !acting && decision.verdict !== 'MANUAL',
    warn: run.mode === 'story' && decision.zone === 'DELEGATED',
    manual: decision.verdict === 'MANUAL',
  };
}

export function renderDecision(ctx, handlers) {
  const model = panelModel(ctx);
  setText(byId('decision-verdict'), model.head);
  setText(byId('decision-text'), model.text);
  byId('decision-empty').hidden = !model.manual;
  const warn = byId('decision-warn');
  warn.hidden = !model.warn;
  setText(byId('decision-warn-text'), WEAKNESS_TEXT);
  const act = byId('lodestar-act');
  act.disabled = !model.canAct;
  act.onclick = handlers.onLodestar;
  setText(byId('decision-note'), model.manual ? 'Raise the link to 30 or more to let Lodestar act.' : '');
  setText(byId('decision-result'), ctx.message ?? '');
  setText(byId('decision-error'), ctx.error ?? '');

  const items = ctx.run && !ctx.run.over ? heldItems(ctx.turn, ctx.decision) : [];
  const tray = byId('tray');
  tray.hidden = items.length === 0;
  const list = byId('tray-items');
  keepFocus(list, () => {
    clear(list);
    for (const item of items) {
      const sign = h('button', { type: 'button', class: 'btn btn-small btn-primary', 'data-key': `sign-${item.agent}` }, item.verb);
      const drop = h('button', { type: 'button', class: 'btn btn-small', 'data-key': `dismiss-${item.agent}` }, 'Dismiss');
      sign.disabled = ctx.acting;
      drop.disabled = ctx.acting;
      sign.addEventListener('click', () => handlers.onSign(item));
      drop.addEventListener('click', () => handlers.onDismiss(item));
      list.append(
        h(
          'div',
          { class: 'tray-item' },
          h('p', {}, h('b', {}, title(item.agent)), ` proposes ${item.summary}. ${item.reasons.map((r) => REASON_TEXT[r] ?? r).join(' ')}`),
          h('div', { class: 'actions' }, sign, drop),
        ),
      );
    }
  }, 'h-decision');
}
