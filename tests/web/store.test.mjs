import assert from 'node:assert/strict';
import test from 'node:test';
import { createStore } from '../../src/linkfall/web/js/store.js';

test('set merges and notifies; unsubscribe stops notifications', () => {
  const store = createStore({ a: 1, b: 2 });
  const seen = [];
  const off = store.subscribe((s) => seen.push(s));
  store.set({ b: 3 });
  assert.deepEqual(store.get(), { a: 1, b: 3 });
  off();
  store.set({ a: 9 });
  assert.deepEqual(seen, [{ a: 1, b: 3 }]);
});

test('get returns a snapshot that later sets do not change', () => {
  const store = createStore({ a: 1 });
  const before = store.get();
  store.set({ a: 2 });
  assert.equal(before.a, 1);
});
