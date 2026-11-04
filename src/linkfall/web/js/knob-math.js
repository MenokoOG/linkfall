// The geometry of the link knob: 270 degrees of sweep, 17 ticks, one per step.
import { LINK_MAX, LINK_MIN, LINK_STEP, snapLink } from './zones.js';

export const SWEEP = 270;
export const START_ANGLE = -135;
export const TICK_COUNT = (LINK_MAX - LINK_MIN) / LINK_STEP + 1;

export function linkToAngle(link) {
  return START_ANGLE + ((link - LINK_MIN) / (LINK_MAX - LINK_MIN)) * SWEEP;
}

// Degrees clockwise from straight up, in -180 to 180, for a pointer at (x, y) around (cx, cy).
export function pointerAngle(cx, cy, x, y) {
  return (Math.atan2(x - cx, -(y - cy)) * 180) / Math.PI;
}

// The bottom gap (outside -135 to 135) sticks to the nearer end.
export function angleToLink(angle) {
  const clamped = Math.max(START_ANGLE, Math.min(-START_ANGLE, angle));
  return snapLink(((clamped - START_ANGLE) / SWEEP) * (LINK_MAX - LINK_MIN) + LINK_MIN);
}

export function tickStates(link) {
  return Array.from({ length: TICK_COUNT }, (_, i) => ({
    angle: START_ANGLE + (i * SWEEP) / (TICK_COUNT - 1),
    on: LINK_MIN + i * LINK_STEP <= link,
  }));
}

// The new link for a key press, or null when the key is not for the knob.
export function linkAfterKey(link, key) {
  switch (key) {
    case 'ArrowRight':
    case 'ArrowUp':
      return snapLink(link + LINK_STEP);
    case 'ArrowLeft':
    case 'ArrowDown':
      return snapLink(link - LINK_STEP);
    case 'PageUp':
      return snapLink(link + 4 * LINK_STEP);
    case 'PageDown':
      return snapLink(link - 4 * LINK_STEP);
    case 'Home':
      return LINK_MIN;
    case 'End':
      return LINK_MAX;
    default:
      return null;
  }
}
