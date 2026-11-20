import assert from 'node:assert/strict';
import test from 'node:test';

import { ApiError, createApi } from '../../src/linkfall/web/js/api.js';
import { pickBackend, serverBackend, wantsBrowser } from '../../src/linkfall/web/js/backend.js';
import { openEvents } from '../../src/linkfall/web/js/events.js';
import {
  LocalBackendError,
  checkManifest,
  createEventSourceClass,
  createFetchFn,
  createSseParser,
  startLocalBackend,
} from '../../src/linkfall/web/js/local-backend.js';
import { reportFileName } from '../../src/linkfall/web/js/range-model.js';

const tick = () => new Promise((resolve) => setImmediate(resolve));
const row = (id, kind = 'engine') => `id: ${id}\nevent: ${kind}\ndata: ${JSON.stringify({ id, turn: 1, kind, payload: {} })}\n\n`;

// A bridge that answers the way PageBridge does: JSON text from request, callbacks from openEvents,
// always after the call returns.
function fakeBridge(reply = { status: 200, headers: { 'content-type': 'application/json' }, body: '{"ok":true}' }) {
  const calls = [];
  const streams = [];
  return {
    calls,
    streams,
    request: async (...args) => {
      calls.push(args);
      if (reply instanceof Error) throw reply;
      return JSON.stringify(reply);
    },
    openEvents(path, lastId, onStart, onChunk, onEnd) {
      const stream = { path, lastId, onStart, onChunk, onEnd, closed: false, destroyed: false };
      stream.close = async () => {
        stream.closed = true;
        onEnd();
      };
      stream.destroy = () => {
        stream.destroyed = true;
      };
      streams.push(stream);
      return stream;
    },
  };
}

test('fetchFn sends what api.js sends and answers with a real Response', async () => {
  const bridge = fakeBridge({ status: 201, headers: { 'content-type': 'application/json' }, body: '{"run_id":"r1"}' });
  const api = createApi(createFetchFn(bridge));
  assert.deepEqual(await api.createRun({ seed: 1 }), { run_id: 'r1' });
  const [method, path, body, headers] = bridge.calls[0];
  assert.equal(method, 'POST');
  assert.equal(path, '/api/runs');
  assert.deepEqual(JSON.parse(body), { seed: 1 });
  assert.equal(JSON.parse(headers)['x-linkfall-request'], '1');
  await api.health();
  assert.equal(bridge.calls[1][2], null); // a GET has no body
});

test('error answers keep their status and message through api.js', async () => {
  const api = createApi(createFetchFn(fakeBridge({ status: 404, headers: {}, body: '{"error":"no such run"}' })));
  await assert.rejects(api.getState('x'), (error) => error instanceof ApiError && error.status === 404 && error.message === 'no such run');
});

test('a bridge that throws is unreachable, never an empty success', async () => {
  const api = createApi(createFetchFn(fakeBridge(new Error('boom'))));
  await assert.rejects(api.health(), (error) => error instanceof ApiError && error.status === 0);
});

test('a 204 answer has no body', async () => {
  const response = await createFetchFn(fakeBridge({ status: 204, headers: {}, body: '' }))('/api/x');
  assert.equal(response.status, 204);
  assert.equal(await response.text(), '');
});

test('the SSE parser splits blocks across chunks, skips comments and keeps the last id', () => {
  const got = [];
  const parser = createSseParser((m) => got.push(m), '3');
  parser.push(': keep-alive\n\nid: 4\nevent: tu');
  assert.equal(got.length, 0);
  parser.push('rn\ndata: {"a":1}\n\ndata: one\r\ndata: two\n\nid: 9\n\n');
  assert.deepEqual(got, [
    { type: 'turn', data: '{"a":1}', lastEventId: '4' },
    { type: 'message', data: 'one\ntwo', lastEventId: '4' },
  ]);
});

test('the event class works with events.js: open, rows, then close', async () => {
  const bridge = fakeBridge();
  const rows = [];
  const status = [];
  const handle = openEvents('r1', { onRow: (r) => rows.push(r.id), onStatus: (s) => status.push(s), EventSourceCtor: createEventSourceClass(bridge) });
  const stream = bridge.streams[0];
  assert.equal(stream.path, '/api/runs/r1/events');
  assert.equal(stream.lastId, null);
  stream.onStart(200);
  stream.onChunk(row(1) + row(2, 'proposal'));
  assert.deepEqual(status, ['open']);
  assert.deepEqual(rows, [1, 2]);
  handle.close();
  await tick();
  assert.equal(stream.closed, true);
  assert.deepEqual(status, ['open']); // closing by hand is not an error
  stream.onChunk(row(3));
  assert.deepEqual(rows, [1, 2]);
});

test('a stream that ends reconnects with the last id', async () => {
  const bridge = fakeBridge();
  const timers = [];
  const Source = createEventSourceClass(bridge, { setTimer: (fn, ms) => timers.push({ fn, ms }), clearTimer: () => {} });
  const source = new Source('/api/runs/r1/events');
  const errors = [];
  source.addEventListener('error', () => errors.push(source.readyState));
  const first = bridge.streams[0];
  first.onStart(200);
  first.onChunk(row(5));
  first.onEnd();
  assert.deepEqual(errors, [Source.CONNECTING]);
  const reconnect = timers.find((t) => t.ms === 3000);
  assert.ok(reconnect);
  timers.forEach((t) => t.fn());
  assert.equal(first.destroyed, true);
  assert.equal(bridge.streams.length, 2);
  assert.equal(bridge.streams[1].lastId, '5');
});

test('a non-200 stream closes for good', () => {
  const bridge = fakeBridge();
  const timers = [];
  const Source = createEventSourceClass(bridge, { setTimer: (fn, ms) => timers.push(ms), clearTimer: () => {} });
  const source = new Source('/api/runs/nope/events');
  let errors = 0;
  source.addEventListener('error', () => errors++);
  bridge.streams[0].onStart(404);
  bridge.streams[0].onChunk('{"error":"no such run"}');
  bridge.streams[0].onEnd();
  assert.equal(errors, 1);
  assert.equal(source.readyState, Source.CLOSED);
  assert.ok(!timers.includes(3000));
});

test('the manifest takes file names only', () => {
  const good = { packages: ['pydantic'], wheels: ['fastapi-1-py3-none-any.whl'], app: 'linkfall.zip' };
  assert.deepEqual(checkManifest(good), good);
  for (const bad of [null, { ...good, app: '../x.zip' }, { ...good, wheels: ['a/b.whl'] }, { ...good, wheels: ['x.tar'] }, { ...good, packages: 'pydantic' }]) {
    assert.throws(() => checkManifest(bad), LocalBackendError);
  }
});

function fakeRuntime({ manifest = { packages: ['pydantic'], wheels: ['a-1-py3-none-any.whl'], app: 'linkfall.zip' }, packageErrors = [], failImport = false } = {}) {
  const log = [];
  const page = {
    request: async (...args) => (log.push(['request', args]), JSON.stringify({ status: 200, headers: {}, body: '{}' })),
    open_events: (...args) => (log.push(['events', args]), { close: async () => {} }),
  };
  const py = {
    loadPackage: async (names, { errorCallback }) => {
      log.push(['packages', names]);
      packageErrors.forEach(errorCallback);
    },
    runPython: (code) => {
      log.push(['python', code]);
      return '/site';
    },
    unpackArchive: (_buffer, format, { extractDir }) => log.push(['unpack', format, extractDir]),
    FS: { mkdirTree: (dir) => log.push(['mkdir', dir]) },
    pyimport: (name) => {
      log.push(['import', name]);
      return { start_page: () => page };
    },
  };
  const fetchFn = async (url) => {
    log.push(['fetch', url.pathname]);
    if (url.pathname.endsWith('manifest.json')) return new Response(JSON.stringify(manifest));
    return new Response(new ArrayBuffer(4));
  };
  const importModule = async (url) => {
    log.push(['module', url]);
    if (failImport) throw new Error('module failed');
    return { loadPyodide: async ({ indexURL }) => (log.push(['pyodide', indexURL]), py) };
  };
  return { log, fetchFn, importModule, base: new URL('https://demo.test/linkfall/runtime/') };
}

test('start-up loads the runtime from beside the page and answers through the bridge', async () => {
  const runtime = fakeRuntime();
  const steps = [];
  const backend = await startLocalBackend({ ...runtime, onProgress: (step, label) => steps.push([step, label]) });
  assert.equal(backend.local, true);
  assert.deepEqual(steps.map(([s]) => s), [1, 2, 3]);
  const paths = runtime.log.filter(([k]) => k === 'fetch').map(([, p]) => p);
  assert.deepEqual(paths.sort(), ['/linkfall/runtime/a-1-py3-none-any.whl', '/linkfall/runtime/linkfall.zip', '/linkfall/runtime/manifest.json']);
  assert.ok(runtime.log.some(([k, v]) => k === 'module' && v === 'https://demo.test/linkfall/runtime/pyodide/pyodide.mjs'));
  assert.deepEqual(runtime.log.filter(([k]) => k === 'unpack').map(([, , d]) => d), ['/site', '/app']);
  assert.ok(runtime.log.some(([k, v]) => k === 'import' && v === 'linkfall.browser.bridge'));
  await backend.fetchFn('/api/health');
  const [, sent] = runtime.log.find(([k]) => k === 'request');
  assert.deepEqual(sent, ['GET', '/api/health', undefined, '{}']); // undefined becomes None; null would be JsNull
  new backend.EventSourceCtor('/api/runs/r1/events');
  const [, opened] = runtime.log.find(([k]) => k === 'events');
  assert.equal(opened[0], '/api/runs/r1/events');
  assert.equal(opened[1], undefined);
});

test('every start-up failure is an error, never a backend', async () => {
  await assert.rejects(startLocalBackend({ ...fakeRuntime(), hasWasm: false }), { code: 'no_wasm' });
  await assert.rejects(startLocalBackend(fakeRuntime({ manifest: { app: 'x' } })), { code: 'manifest' });
  await assert.rejects(startLocalBackend(fakeRuntime({ packageErrors: ['integrity check failed'] })), { code: 'packages', message: 'integrity check failed' });
  await assert.rejects(startLocalBackend(fakeRuntime({ failImport: true })), (e) => e.code === 'start' && e.cause.message === 'module failed');
  const missing = { ...fakeRuntime(), fetchFn: async () => new Response('', { status: 404 }) };
  await assert.rejects(startLocalBackend(missing), { code: 'download' });
  const slow = { ...fakeRuntime(), importModule: () => new Promise(() => {}), timeoutMs: 20 };
  await assert.rejects(startLocalBackend(slow), { code: 'timeout' });
});

test('backend.js picks the browser only when the page asks for it', async () => {
  const page = (content) => ({ querySelector: () => (content ? { getAttribute: () => content } : null) });
  assert.equal(wantsBrowser(page('browser')), true);
  assert.equal(wantsBrowser(page('server')), false);
  assert.equal(wantsBrowser(page(null)), false);
  assert.equal(wantsBrowser(undefined), false);
  const local = { local: true };
  assert.equal(await pickBackend({ doc: page('browser'), loadBrowser: async () => local }), local);
  assert.equal((await pickBackend({ doc: page(null), loadBrowser: async () => local })).local, false);
  assert.equal(serverBackend().local, false);
});

test('the browser build saves the report under the server name', () => {
  assert.equal(reportFileName('abc123'), 'linkfall-range-abc123.md');
});
