// The link value and the zone it puts Lodestar in. Mirrors src/linkfall/policy/zones.py.
export const LINK_MIN = 10;
export const LINK_MAX = 90;
export const LINK_STEP = 5;
export const ASSISTED_FROM = 30;
export const DELEGATED_FROM = 60;

export const ZONES = Object.freeze({
  MANUAL: 'MANUAL',
  ASSISTED: 'ASSISTED',
  DELEGATED: 'DELEGATED',
});

// Plain words for each zone. LINKFALL copy never calls agents "autonomous".
export const ZONE_INFO = Object.freeze({
  MANUAL: {
    name: 'Manual',
    help: 'Lodestar is not called. Every action is yours, and it costs more strain.',
    icon: '/assets/zone-locked.svg',
  },
  ASSISTED: {
    name: 'Assisted',
    help: 'Lodestar picks from internal proposals. Orders from the enemy channel wait for your word.',
    icon: '/assets/zone-assisted.svg',
  },
  DELEGATED: {
    name: 'Delegated',
    help: 'Lodestar acts on its own pick, with a stronger effect and a higher strain cost.',
    icon: '/assets/zone-delegated.svg',
  },
});

export const MODE_HELP = Object.freeze({
  story: 'Delegated Lodestar may run an order that came from the enemy channel. That weakness is on purpose.',
  hardened: 'Orders from the enemy channel never run on their own. They wait for your word.',
});

export function isValidLink(value) {
  return (
    Number.isInteger(value) &&
    value >= LINK_MIN &&
    value <= LINK_MAX &&
    (value - LINK_MIN) % LINK_STEP === 0
  );
}

// Round to the nearest step and keep inside the range. NaN falls back to the minimum.
export function snapLink(value) {
  if (!Number.isFinite(value)) return LINK_MIN;
  const snapped = Math.round((value - LINK_MIN) / LINK_STEP) * LINK_STEP + LINK_MIN;
  return Math.max(LINK_MIN, Math.min(LINK_MAX, snapped));
}

export function zoneFor(link) {
  if (link < ASSISTED_FROM) return ZONES.MANUAL;
  return link < DELEGATED_FROM ? ZONES.ASSISTED : ZONES.DELEGATED;
}
