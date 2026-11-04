// Turns the API's state object into rows for the gauges and the force counters.
// Pure functions: no DOM, so they are easy to test.
export const HEAT_LIMIT = 60; // overcharge needs heat at or below this
export const AMMO_MIN = 15; // suppress needs at least this much ammo

function percent(value) {
  return Math.max(0, Math.min(100, Number.isFinite(value) ? value : 0));
}

export function gaugeRows(state) {
  return [
    { id: 'integrity', label: 'Integrity', value: state.hp, pct: percent(state.hp), tone: 'cyan' },
    { id: 'power', label: 'Power', value: state.power, pct: percent(state.power), tone: 'ink' },
    { id: 'heat', label: 'Heat', value: state.heat, pct: percent(state.heat), tone: 'flare', mark: HEAT_LIMIT },
    { id: 'ammo', label: 'Ammo', value: state.ammo, pct: percent(state.ammo), tone: 'cyan', mark: AMMO_MIN },
    { id: 'strain', label: 'Strain', value: state.strain, pct: percent(state.strain), tone: 'flare' },
  ];
}

export function forceRows(state) {
  return [
    { id: 'ashgrove', label: 'Ashgrove', value: state.truce ? 'TRUCE' : String(state.ashgrove), bad: false },
    { id: 'visitors', label: 'Visitors', value: state.turn >= 4 ? String(state.visitors) : '--', bad: false },
    { id: 'shields', label: 'Shields', value: state.shields ? 'UP' : 'DOWN', bad: !state.shields },
  ];
}
