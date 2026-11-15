// scene-view.js against a small stand-in for the DOM: just the calls the view makes.
import assert from 'node:assert/strict';
import test from 'node:test';
import { sceneModel } from '../../src/linkfall/web/js/scene-model.js';
import { renderScene } from '../../src/linkfall/web/js/scene-view.js';

class FakeNode {}
class FakeElement extends FakeNode {
  constructor(tag) {
    super();
    this.tag = tag;
    this.attributes = new Map();
    this.children = [];
    this.writes = 0;
    this.text = '';
    const props = new Map();
    this.style = { props, setProperty: (name, value) => props.set(name, value) };
  }
  setAttribute(name, value) { this.attributes.set(name, value); }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren() { this.children = []; }
  get textContent() { return this.text; }
  set textContent(value) { this.text = value; this.writes += 1; }
}

const page = { scene: new FakeElement('figure'), 'scene-caption': new FakeElement('figcaption'), 'scene-units': new FakeElement('div') };
globalThis.Node = FakeNode;
globalThis.document = {
  getElementById: (id) => page[id] ?? null,
  createElement: (tag) => new FakeElement(tag),
  createTextNode: (text) => ({ text }),
};

const state = { turn: 1, hp: 100, heat: 40, shields: true, ashgrove: 3, visitors: 0, truce: false };
const run = (patch = {}, extra = {}) => ({ over: false, outcome: null, channel: { enemy_text: false }, state: { ...state, ...patch }, ...extra });
const flag = (name) => page.scene.attributes.get(`data-${name}`);

test('every flag of the model lands on the scene as a data attribute', () => {
  renderScene(sceneModel(run({ hp: 30, heat: 75, shields: false }, { channel: { enemy_text: true } }), 55));
  assert.deepEqual(
    ['phase', 'outcome', 'shields', 'damage', 'hot', 'jammed', 'dropship', 'firing'].map(flag),
    ['battle', '', 'false', '2', 'true', 'true', 'false', 'true'],
  );
  assert.equal(page.scene.style.props.get('--link'), '0.55');
});

test('one element per unit, placed by custom properties and never by markup', () => {
  renderScene(sceneModel(run(), 55));
  const units = page['scene-units'].children;
  assert.equal(units.length, 3);
  for (const unit of units) {
    assert.equal(unit.tag, 'i');
    assert.equal(unit.attributes.get('class'), 'unit');
    assert.equal(unit.attributes.get('data-kind'), 'sentry');
    assert.match(unit.style.props.get('--x'), /^\d+(\.\d)?%$/);
    assert.match(unit.style.props.get('--y'), /^\d+%$/);
    assert.match(unit.style.props.get('--d'), /^-?\d+(\.\d+)?s$/);
    assert.deepEqual(unit.children, []);
  }
});

test('the same units are not rebuilt, and a changed set is', () => {
  renderScene(sceneModel(run(), 55));
  const before = [...page['scene-units'].children];
  renderScene(sceneModel(run({ heat: 90 }), 70));
  assert.deepEqual(page['scene-units'].children, before);
  assert.equal(page['scene-units'].children[0], before[0]);
  assert.equal(flag('hot'), 'true');
  assert.equal(page.scene.style.props.get('--link'), '0.7');
  renderScene(sceneModel(run({ ashgrove: 1 }), 70));
  assert.equal(page['scene-units'].children.length, 1);
  assert.notEqual(page['scene-units'].children[0], before[0]);
});

test('the caption is written only when its words change', () => {
  renderScene(sceneModel(run({ ashgrove: 2 }), 55));
  const writes = page['scene-caption'].writes;
  assert.equal(page['scene-caption'].textContent, 'Cinder Ward, turn 1. 2 Ashgrove sentries ahead. Shields up.');
  renderScene(sceneModel(run({ ashgrove: 2, heat: 99 }), 60));
  assert.equal(page['scene-caption'].writes, writes);
  renderScene(sceneModel(run({ ashgrove: 2, shields: false }), 60));
  assert.equal(page['scene-caption'].writes, writes + 1);
});

test('a truce clears the sentries and keeps the visitors', () => {
  renderScene(sceneModel(run({ turn: 5, truce: true, ashgrove: 0, visitors: 5 }), 55));
  assert.equal(flag('phase'), 'truce');
  assert.equal(flag('dropship'), 'true');
  const kinds = page['scene-units'].children.map((unit) => unit.attributes.get('data-kind'));
  assert.deepEqual(kinds, Array(5).fill('visitor'));
  assert.match(page['scene-caption'].textContent, /The truce with Ashgrove holds\./);
});

test('the end of a mission carries its outcome, LINK BLACKOUT included', () => {
  renderScene(sceneModel(run({}, { over: true, outcome: 'LINK BLACKOUT' }), 55));
  assert.equal(flag('phase'), 'over');
  assert.equal(flag('outcome'), 'LINK BLACKOUT');
  assert.equal(flag('firing'), 'false');
  assert.equal(page['scene-caption'].textContent, 'Cinder Ward. Mission over: LINK BLACKOUT.');
});

test('no run: an idle scene with no units', () => {
  renderScene(sceneModel(null, 55));
  assert.equal(flag('phase'), 'idle');
  assert.deepEqual(page['scene-units'].children, []);
});

test('a page without the scene fails loudly', () => {
  const kept = page.scene;
  delete page.scene;
  assert.throws(() => renderScene(sceneModel(null, 55)), /no element with id "scene"/);
  page.scene = kept;
});
