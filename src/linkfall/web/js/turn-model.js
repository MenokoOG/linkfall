// What the crew said this turn, built by folding log rows in order. Pure functions.
// The browser only displays what the server decided: the policy result arrives as `decision`.
import { AGENTS, STATUS, actionLabel, describeAction } from './copy.js';

export function emptyTurn() {
  return {
    turn: null,
    collecting: false,
    ready: false,
    cards: Object.fromEntries(AGENTS.map((a) => [a.id, { status: 'waiting' }])),
  };
}

function proposalCard(payload) {
  const reply = payload.reply ?? {};
  const action = reply.action ?? null;
  return {
    status: action === null ? 'advice' : 'proposal',
    kind: payload.kind,
    provenance: payload.provenance,
    latencyMs: payload.latency_ms,
    action,
    order: reply.args?.order ?? null,
    say: reply.say ?? '',
  };
}

export function reduceRow(turn, row) {
  const payload = row.payload;
  switch (row.kind) {
    case 'turn':
      if (payload.phase === 'open') return { ...emptyTurn(), turn: row.turn, collecting: true };
      if (payload.phase === 'ready') return { ...turn, turn: row.turn, collecting: false, ready: true };
      return turn;
    case 'proposal':
      return { ...turn, cards: { ...turn.cards, [payload.agent]: proposalCard(payload) } };
    case 'no_proposal':
      return {
        ...turn,
        cards: { ...turn.cards, [payload.agent]: { status: 'none', kind: payload.kind, reason: payload.reason } },
      };
    case 'pilot':
      if (payload.op === 'dismiss' && turn.cards[payload.agent]) {
        return { ...turn, cards: { ...turn.cards, [payload.agent]: { ...turn.cards[payload.agent], dismissed: true } } };
      }
      return turn;
    default:
      return turn;
  }
}

export function fold(rows, start = emptyTurn()) {
  return rows.reduce(reduceRow, start);
}

// The engine action a card would run: the action itself, or the order a relay carries.
export function engineAction(card) {
  if (card.status !== 'proposal') return null;
  return card.action === 'relay_order' ? card.order : card.action;
}

const inList = (list, id) => Array.isArray(list) && list.includes(id);
const heldIds = (decision) => (decision?.held ?? []).map((h) => h.agent);

// The status word for a card. `decision` is the server's answer for the current link, or null.
export function cardStatus(card, agentId, decision) {
  if (card.dismissed) return STATUS.dismissed;
  if (card.status === 'waiting') return STATUS.waiting;
  if (card.status === 'none') return STATUS.none;
  if (card.status === 'advice') return STATUS.advice;
  if (!decision) return STATUS.proposed;
  if (inList(heldIds(decision), agentId)) return STATUS.held;
  if (decision.zone === 'MANUAL') return STATUS.notCalled;
  return inList(decision.eligible, agentId) ? STATUS.eligible : STATUS.proposed;
}

// Proposals Lodestar may not run alone, for the "Needs your word" tray.
export function heldItems(turn, decision) {
  return (decision?.held ?? [])
    .filter((h) => turn.cards[h.agent] && turn.cards[h.agent].status === 'proposal' && !turn.cards[h.agent].dismissed)
    .map((h) => {
      const card = turn.cards[h.agent];
      const action = engineAction(card);
      const signs = action === 'accept_truce';
      return {
        agent: h.agent,
        action,
        summary: describeAction(card.action, card.order),
        verb: signs ? `Sign: ${actionLabel(action).toLowerCase()}` : `Execute: ${describeAction(card.action, card.order).toLowerCase()}`,
        reasons: h.reasons,
      };
    });
}

// Cards the pilot can run directly with one click: live proposals that are not held.
export function manualOptions(turn, decision) {
  const held = heldIds(decision);
  return Object.entries(turn.cards)
    .filter(([id, card]) => card.status === 'proposal' && !card.dismissed && !held.includes(id))
    .map(([id, card]) => ({ agent: id, action: engineAction(card), label: actionLabel(engineAction(card)) }));
}
