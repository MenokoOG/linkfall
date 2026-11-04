// Wires the knob element to the link value: drag with a pointer, or use the keyboard.
import { angleToLink, linkAfterKey, pointerAngle } from './knob-math.js';

export function attachKnob(element, { getLink, onChange }) {
  let dragging = false;

  function fromPointer(event) {
    const rect = element.getBoundingClientRect();
    const angle = pointerAngle(rect.left + rect.width / 2, rect.top + rect.height / 2, event.clientX, event.clientY);
    onChange(angleToLink(angle));
  }

  element.addEventListener('pointerdown', (event) => {
    dragging = true;
    element.setPointerCapture(event.pointerId);
    fromPointer(event);
  });
  element.addEventListener('pointermove', (event) => {
    if (dragging) fromPointer(event);
  });
  const stop = () => {
    dragging = false;
  };
  element.addEventListener('pointerup', stop);
  element.addEventListener('pointercancel', stop);
  element.addEventListener('keydown', (event) => {
    const next = linkAfterKey(getLink(), event.key);
    if (next === null) return;
    event.preventDefault();
    onChange(next);
  });
}
