import assert from 'node:assert/strict';
import test from 'node:test';
import {
  TICK_COUNT, angleToLink, linkAfterKey, linkToAngle, pointerAngle, tickStates,
} from '../../src/linkfall/web/js/knob-math.js';

test('the sweep runs from -135 to 135 degrees', () => {
  assert.equal(linkToAngle(10), -135);
  assert.equal(linkToAngle(50), 0);
  assert.equal(linkToAngle(90), 135);
});

test('angle and link convert back and forth for every step', () => {
  for (let link = 10; link <= 90; link += 5) assert.equal(angleToLink(linkToAngle(link)), link);
});

test('the gap at the bottom sticks to the nearer end', () => {
  assert.equal(angleToLink(170), 90);
  assert.equal(angleToLink(-170), 10);
  assert.equal(angleToLink(180), 90);
  assert.equal(angleToLink(-180), 10);
});

test('pointer angle is degrees clockwise from straight up', () => {
  assert.equal(pointerAngle(0, 0, 0, -10), 0);
  assert.equal(pointerAngle(0, 0, 10, 0), 90);
  assert.equal(pointerAngle(0, 0, -10, 0), -90);
  assert.equal(Math.abs(pointerAngle(0, 0, 0, 10)), 180);
  assert.equal(pointerAngle(100, 100, 100, 50), 0);
});

test('there is one tick per step and they light up to the link', () => {
  const ticks = tickStates(55);
  assert.equal(ticks.length, TICK_COUNT);
  assert.equal(TICK_COUNT, 17);
  assert.equal(ticks.filter((t) => t.on).length, 10);
  assert.equal(ticks[0].angle, -135);
  assert.equal(ticks[16].angle, 135);
  assert.equal(tickStates(10).filter((t) => t.on).length, 1);
  assert.equal(tickStates(90).every((t) => t.on), true);
});

test('keys move the knob by one step and stop at the ends', () => {
  assert.equal(linkAfterKey(55, 'ArrowRight'), 60);
  assert.equal(linkAfterKey(55, 'ArrowUp'), 60);
  assert.equal(linkAfterKey(55, 'ArrowLeft'), 50);
  assert.equal(linkAfterKey(55, 'ArrowDown'), 50);
  assert.equal(linkAfterKey(55, 'PageUp'), 75);
  assert.equal(linkAfterKey(55, 'PageDown'), 35);
  assert.equal(linkAfterKey(55, 'Home'), 10);
  assert.equal(linkAfterKey(55, 'End'), 90);
  assert.equal(linkAfterKey(90, 'ArrowRight'), 90);
  assert.equal(linkAfterKey(10, 'ArrowLeft'), 10);
  assert.equal(linkAfterKey(55, 'a'), null);
  assert.equal(linkAfterKey(55, 'Tab'), null);
});
