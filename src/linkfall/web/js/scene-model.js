// Turns a run and the link into what the battlefield view shows. Pure: no DOM.
// The view adds no facts of its own. Every figure here is already on the gauges or the force row.
export const MAX_SENTRIES = 18;
export const MAX_VISITORS = 12;
export const VISITORS_FROM_TURN = 4; // same rule as the force row: no count before the dropship lands

const GOLDEN = 0.618034;
const ROWS = [
  { y: 20, scale: 0.7 }, // far
  { y: 13, scale: 0.85 },
  { y: 6, scale: 1 }, // near
];

function spot(index, from, span) {
  const row = index % ROWS.length;
  const x = from + ((index * GOLDEN + 0.13) % 1) * span;
  return { x: Math.round(x * 10) / 10, y: ROWS[row].y, scale: ROWS[row].scale, row, delay: (index * 7) % 10 };
}

function count(value, max) {
  return Number.isFinite(value) ? Math.max(0, Math.min(max, Math.trunc(value))) : 0;
}

function damageBand(hp) {
  if (hp <= 0) return 3;
  if (hp < 40) return 2;
  return hp < 70 ? 1 : 0;
}

function caption(run, state, sentries, visitors) {
  if (run.over) return `Cinder Ward. Mission over: ${run.outcome}.`;
  const parts = [`Cinder Ward, turn ${state.turn}.`];
  if (state.truce) parts.push('The truce with Ashgrove holds.');
  else parts.push(sentries === 1 ? '1 Ashgrove sentry ahead.' : `${sentries} Ashgrove sentries ahead.`);
  if (visitors > 0) parts.push(visitors === 1 ? '1 visitor on the ground.' : `${visitors} visitors on the ground.`);
  parts.push(state.shields ? 'Shields up.' : 'Shields down.');
  return parts.join(' ');
}

export function sceneModel(run, link) {
  const state = run?.state;
  const base = { link, phase: 'idle', outcome: '', shields: true, damage: 0, hot: false, jammed: false, dropship: false, firing: false, units: [], caption: 'Cinder Ward. Standing by for a run.' };
  if (!state) return base;
  const sentries = state.truce ? 0 : count(state.ashgrove, MAX_SENTRIES);
  const landed = state.turn >= VISITORS_FROM_TURN;
  const visitors = landed ? count(state.visitors, MAX_VISITORS) : 0;
  const units = [
    ...Array.from({ length: sentries }, (_, i) => ({ kind: 'sentry', ...spot(i, 46, 50) })),
    ...Array.from({ length: visitors }, (_, i) => ({ kind: 'visitor', ...spot(i + 1, 62, 30) })),
  ];
  const phase = run.over ? 'over' : state.truce ? 'truce' : 'battle';
  return {
    link,
    phase,
    outcome: run.over ? String(run.outcome ?? '') : '',
    shields: Boolean(state.shields),
    damage: damageBand(state.hp),
    hot: state.heat > 60,
    jammed: Boolean(run.channel?.enemy_text),
    dropship: landed && visitors > 0,
    firing: phase !== 'over' && units.length > 0,
    units,
    caption: caption(run, state, sentries, visitors),
  };
}
