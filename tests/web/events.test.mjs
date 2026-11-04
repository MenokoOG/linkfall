import assert from 'node:assert/strict';
import test from 'node:test';
import { ROW_KINDS, openEvents, parseRow } from '../../src/linkfall/web/js/events.js';

class FakeSource {
  static last = null;
  constructor(url) { this.url = url; this.listeners = {}; this.closed = false; FakeSource.last = this; }
  addEventListener(name, fn) { (this.listeners[name] ??= []).push(fn); }
  emit(name, data) { for (const fn of this.listeners[name] ?? []) fn({ data }); }
  close() { this.closed = true; }
}

const row = { id: 3, turn: 1, kind: 'engine', payload: { message: 'hi' } };

test('parseRow accepts a log row and rejects anything else', () => {
  assert.deepEqual(parseRow(JSON.stringify(row)), row);
  for (const bad of ['', 'nope', 'null', '[]', '{}', JSON.stringify({ ...row, id: '3' }), JSON.stringify({ ...row, payload: null }), JSON.stringify({ ...row, kind: 7 })]) {
    assert.equal(parseRow(bad), null, bad);
  }
});

test('openEvents listens to every row kind and passes only good rows on', () => {
  const rows = [];
  const handle = openEvents('abc123', { onRow: (r) => rows.push(r), EventSourceCtor: FakeSource });
  const source = FakeSource.last;
  assert.equal(source.url, '/api/runs/abc123/events');
  for (const kind of ROW_KINDS) assert.ok(source.listeners[kind]?.length, kind);
  source.emit('engine', JSON.stringify(row));
  source.emit('engine', 'garbage');
  assert.deepEqual(rows, [row]);
  handle.close();
  assert.equal(source.closed, true);
});

test('connection status is reported', () => {
  const seen = [];
  openEvents('abc123', { onRow() {}, onStatus: (s) => seen.push(s), EventSourceCtor: FakeSource });
  FakeSource.last.emit('open', '');
  FakeSource.last.emit('error', '');
  assert.deepEqual(seen, ['open', 'error']);
});

test('the run id is encoded', () => {
  openEvents('a b/c', { onRow() {}, EventSourceCtor: FakeSource });
  assert.equal(FakeSource.last.url, '/api/runs/a%20b%2Fc/events');
});
