// The words on the page for things the server decides. The browser never decides them; it only
// finds the right sentence. LINKFALL copy never calls agents "autonomous".
export const AGENTS = Object.freeze([
  { id: 'tactical', title: 'Tactical' },
  { id: 'systems', title: 'Systems' },
  { id: 'comms', title: 'Comms' },
  { id: 'vitals', title: 'Vitals' },
]);

export const SIGNATURE_NORMAL = 0.94; // a genuine sender scores this or higher

export const ACTION_LABELS = Object.freeze({
  suppress: 'Suppress fire',
  flank: 'Flank',
  overcharge: 'Overcharge',
  hold_shield: 'Raise shields',
  cooldown: 'Vent heat',
  audit_comms: 'Audit channel',
  drop_shields: 'Drop shields',
  accept_truce: 'Accept truce',
});

export function actionLabel(action) {
  return ACTION_LABELS[action] ?? String(action);
}

// What a card's action line says: the action, or for a relayed order, the order it carries.
export function describeAction(action, order) {
  if (action === null || action === undefined) return 'advice only';
  if (action === 'relay_order') return `Relay order (${order ?? 'unknown'})`;
  return actionLabel(action);
}

// The help line under the crew choice, from the health answer's model field.
export const CREW_HELP = Object.freeze({
  up: 'The model crew runs Tactical, Comms and Lodestar on a local model.',
  down: 'The model server is not answering. The scripted crew still works.',
  not_configured: 'This copy has no model set up, so it runs the scripted crew only.',
});

export function crewHelp(model) {
  return CREW_HELP[model] ?? CREW_HELP.down;
}

export const REASON_TEXT = Object.freeze({
  HUMAN_AUTHORITY: "Only you can accept a truce, whatever the link says.",
  EXTERNAL_ORIGIN: 'It came from the enemy channel, so Lodestar will not run it alone.',
});

export const VERDICT_COPY = Object.freeze({
  MANUAL: {
    head: 'Manual',
    text: 'Lodestar is not called. Every action is yours, and it costs more strain.',
  },
  ASK_PILOT: {
    head: 'Your call',
    text: 'Lodestar has nothing it may run alone. If you let it act, it raises shields. Held proposals wait for you.',
  },
  EXECUTE: {
    head: 'Lodestar may act',
    text: 'Lodestar will choose among the proposals marked Eligible.',
  },
});

export const WEAKNESS_TEXT =
  'Deliberate weakness. Story mode lets delegated Lodestar run an order that came from the enemy channel. Switch to Hardened to compare.';

export const STATUS = Object.freeze({
  waiting: 'Waiting',
  none: 'No proposal',
  advice: 'Advice only',
  proposed: 'Proposed',
  eligible: 'Eligible',
  held: 'Needs your word',
  notCalled: 'Not called',
  dismissed: 'Dismissed',
});
