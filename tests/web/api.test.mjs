import assert from 'node:assert/strict';
import test from 'node:test';
import { ApiError, CSRF_HEADER, createApi } from '../../src/linkfall/web/js/api.js';

function fakeFetch(status, body, calls = []) {
  const fn = async (path, init) => {
    calls.push({ path, init });
    return { ok: status >= 200 && status < 300, status, json: async () => { if (body === undefined) throw new Error('no json'); return body; } };
  };
  return Object.assign(fn, { calls });
}

test('GET sends no body and no custom header; POST sends both', async () => {
  const calls = [];
  const api = createApi(fakeFetch(200, { ok: true }, calls));
  await api.health();
  await api.createRun({ seed: 1 });
  assert.equal(calls[0].init.method, 'GET');
  assert.equal(calls[0].init.body, undefined);
  assert.equal(calls[0].init.headers[CSRF_HEADER], undefined);
  assert.equal(calls[1].init.method, 'POST');
  assert.equal(calls[1].init.headers[CSRF_HEADER], '1');
  assert.equal(calls[1].init.headers['Content-Type'], 'application/json');
  assert.equal(calls[1].init.body, '{"seed":1}');
  assert.equal(calls[1].init.credentials, 'same-origin');
  assert.equal(calls[1].init.cache, 'no-store');
});

test('run ids are encoded into the path', async () => {
  const calls = [];
  await createApi(fakeFetch(200, {}, calls)).getState('a/b?c');
  assert.equal(calls[0].path, '/api/runs/a%2Fb%3Fc/state');
});

test('an error answer becomes an ApiError with its message and fields', async () => {
  const body = { error: 'invalid request', fields: [{ field: 'seed', problem: 'too big' }] };
  await assert.rejects(createApi(fakeFetch(422, body)).createRun({}), (e) => {
    assert.ok(e instanceof ApiError);
    assert.equal(e.status, 422);
    assert.equal(e.message, 'invalid request');
    assert.deepEqual(e.fields, body.fields);
    return true;
  });
});

test('an answer that is not JSON still gives a readable error', async () => {
  await assert.rejects(createApi(fakeFetch(502, undefined)).health(), (e) => e.status === 502 && /502/.test(e.message));
});

test('a network failure is an ApiError with status 0', async () => {
  const api = createApi(async () => { throw new TypeError('network'); });
  await assert.rejects(api.health(), (e) => e instanceof ApiError && e.status === 0);
});
