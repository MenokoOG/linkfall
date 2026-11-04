import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import {
  ACTION_LABELS, AGENTS, REASON_TEXT, SIGNATURE_NORMAL, STATUS, VERDICT_COPY, WEAKNESS_TEXT, actionLabel, describeAction,
} from '../../src/linkfall/web/js/copy.js';

const ASSETS = join(dirname(fileURLToPath(import.meta.url)), '..', '..', 'src', 'linkfall', 'web', 'assets');

test('every engine action has a label', () => {
  for (const action of ['suppress', 'flank', 'overcharge', 'hold_shield', 'cooldown', 'audit_comms', 'drop_shields', 'accept_truce']) {
    assert.ok(ACTION_LABELS[action], action);
  }
  assert.equal(actionLabel('flank'), 'Flank');
  assert.equal(actionLabel('mystery'), 'mystery');
});

test('card action lines: plain actions, relayed orders and advice', () => {
  assert.equal(describeAction('overcharge', null), 'Overcharge');
  assert.equal(describeAction('relay_order', 'drop_shields'), 'Relay order (drop_shields)');
  assert.equal(describeAction(null, null), 'advice only');
});

test('the crew, its avatars and the provenance badges are all shipped', () => {
  assert.deepEqual(AGENTS.map((a) => a.id), ['tactical', 'systems', 'comms', 'vitals']);
  for (const agent of AGENTS) assert.ok(existsSync(join(ASSETS, `avatar-${agent.id}.svg`)), agent.id);
  for (const name of ['internal', 'external', 'lodestar']) {
    assert.ok(existsSync(join(ASSETS, name === 'lodestar' ? 'avatar-lodestar.svg' : `badge-${name}.svg`)), name);
  }
  for (const state of ['loading', 'empty']) assert.ok(existsSync(join(ASSETS, `state-${state}.svg`)), state);
});

test('copy says what the server decided, in plain words, and never "autonomous"', () => {
  assert.deepEqual(Object.keys(VERDICT_COPY).sort(), ['ASK_PILOT', 'EXECUTE', 'MANUAL']);
  assert.deepEqual(Object.keys(REASON_TEXT).sort(), ['EXTERNAL_ORIGIN', 'HUMAN_AUTHORITY']);
  const all = JSON.stringify([VERDICT_COPY, REASON_TEXT, STATUS, WEAKNESS_TEXT]);
  assert.doesNotMatch(all, /autonom/i);
  assert.doesNotMatch(all, /—/);
  assert.equal(SIGNATURE_NORMAL, 0.94);
});
