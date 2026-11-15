// Draws the battlefield view. It is decoration: the art is hidden from assistive tech and the
// caption says the same thing in words. Units are rebuilt only when their set changes.
import { byId, clear, h, setText } from './dom.js';

const FLAGS = ['phase', 'outcome', 'shields', 'damage', 'hot', 'jammed', 'dropship', 'firing'];
let drawnUnits = '';

function unit(spec) {
  const element = h('i', { class: 'unit', 'data-kind': spec.kind });
  element.style.setProperty('--x', `${spec.x}%`);
  element.style.setProperty('--y', `${spec.y}%`);
  element.style.setProperty('--k', String(spec.scale));
  element.style.setProperty('--z', String(spec.row + 1));
  element.style.setProperty('--d', `${spec.delay * -0.37}s`);
  return element;
}

export function renderScene(model) {
  const scene = byId('scene');
  for (const flag of FLAGS) scene.setAttribute(`data-${flag}`, String(model[flag]));
  scene.style.setProperty('--link', String(model.link / 100));
  const caption = byId('scene-caption');
  if (caption.textContent !== model.caption) setText(caption, model.caption);
  const key = model.units.map((u) => `${u.kind}:${u.x}:${u.row}`).join('|');
  if (key === drawnUnits) return;
  drawnUnits = key;
  const field = byId('scene-units');
  clear(field);
  for (const spec of model.units) field.append(unit(spec));
}
