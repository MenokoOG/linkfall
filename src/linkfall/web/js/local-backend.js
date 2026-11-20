// The browser backend for the hosted copy: the API app runs in this tab on Pyodide (ADR 0012).
// The only file that knows about Pyodide. It gives api.js a fetchFn and events.js an
// EventSource-shaped class, both backed by linkfall.browser.bridge.PageBridge.
export const LOAD_TIMEOUT_MS = 60_000;
export const RECONNECT_MS = 3000;
export const STEPS = 3;
const NAME = /^[A-Za-z0-9_.+-]+$/; // a file name in runtime/, never a path
const NO_BODY = new Set([204, 205, 304]);

export class LocalBackendError extends Error {
  constructor(code, message, options) {
    super(message, options);
    this.name = 'LocalBackendError';
    this.code = code;
  }
}

// runtime/manifest.json, written by the build: Pyodide packages to load, wheels to unpack into
// site-packages, and the zip of the linkfall package.
export function checkManifest(manifest) {
  const names = (list) => Array.isArray(list) && list.every((n) => typeof n === 'string' && NAME.test(n));
  const ok =
    manifest !== null &&
    typeof manifest === 'object' &&
    names(manifest.packages) &&
    names(manifest.wheels) &&
    manifest.wheels.every((n) => n.endsWith('.whl')) &&
    typeof manifest.app === 'string' &&
    NAME.test(manifest.app) &&
    manifest.app.endsWith('.zip');
  if (!ok) throw new LocalBackendError('manifest', 'The runtime manifest is not valid.');
  return { packages: manifest.packages, wheels: manifest.wheels, app: manifest.app };
}

// fetch() in shape: takes (path, init), resolves to a Response, rejects when the bridge throws.
export function createFetchFn(bridge) {
  return async (path, init = {}) => {
    const method = String(init.method ?? 'GET').toUpperCase();
    const headers = Object.fromEntries(new Headers(init.headers ?? {}));
    const body = typeof init.body === 'string' ? init.body : null;
    const reply = JSON.parse(await bridge.request(method, String(path), body, JSON.stringify(headers)));
    return new Response(NO_BODY.has(reply.status) ? null : reply.body, {
      status: reply.status,
      headers: reply.headers,
    });
  };
}

// Server-sent event text in, one message out per block. Comment lines are skipped; the last id
// carries over, as in the EventSource spec.
export function createSseParser(onMessage, lastEventId = null) {
  let buffer = '';
  let lastId = lastEventId;
  const dispatch = (block) => {
    let type = 'message';
    const data = [];
    for (const line of block.split('\n')) {
      if (line === '' || line.startsWith(':')) continue;
      const colon = line.indexOf(':');
      const field = colon < 0 ? line : line.slice(0, colon);
      let value = colon < 0 ? '' : line.slice(colon + 1);
      if (value.startsWith(' ')) value = value.slice(1);
      if (field === 'event') type = value;
      else if (field === 'data') data.push(value);
      else if (field === 'id' && !value.includes('\0')) lastId = value;
    }
    if (data.length > 0) onMessage({ type, data: data.join('\n'), lastEventId: lastId });
  };
  return {
    push(text) {
      buffer += text.replace(/\r\n?/g, '\n');
      let end;
      while ((end = buffer.indexOf('\n\n')) >= 0) {
        dispatch(buffer.slice(0, end));
        buffer = buffer.slice(end + 2);
      }
    },
  };
}

// An EventSource for the in-tab app. A stream that ends reconnects after RECONNECT_MS with the
// last id, as a browser does with the server; a non-200 answer closes it for good.
export function createEventSourceClass(bridge, { reconnectMs = RECONNECT_MS, setTimer = setTimeout, clearTimer = clearTimeout } = {}) {
  return class LocalEventSource {
    static CONNECTING = 0;
    static OPEN = 1;
    static CLOSED = 2;

    constructor(url) {
      this.url = String(url);
      this.readyState = LocalEventSource.CONNECTING;
      this.listeners = new Map();
      this.lastEventId = null;
      this.stream = null;
      this.timer = null;
      this.connect();
    }

    addEventListener(type, listener) {
      if (!this.listeners.has(type)) this.listeners.set(type, new Set());
      this.listeners.get(type).add(listener);
    }

    removeEventListener(type, listener) {
      this.listeners.get(type)?.delete(listener);
    }

    emit(type, event = {}) {
      for (const listener of this.listeners.get(type) ?? []) listener({ type, ...event });
    }

    connect() {
      this.timer = null;
      this.readyState = LocalEventSource.CONNECTING;
      const parser = createSseParser((message) => {
        if (this.readyState !== LocalEventSource.OPEN) return;
        this.lastEventId = message.lastEventId;
        this.emit(message.type, message);
      }, this.lastEventId);
      const onStart = (status) => {
        if (this.readyState === LocalEventSource.CLOSED) return;
        if (status === 200) {
          this.readyState = LocalEventSource.OPEN;
          this.emit('open');
        } else {
          this.readyState = LocalEventSource.CLOSED;
          this.emit('error');
        }
      };
      const onEnd = () => {
        if (this.stream === handle) this.stream = null;
        setTimer(() => handle.destroy?.(), 0); // free the Python proxy once its call has returned
        if (this.readyState === LocalEventSource.CLOSED) return;
        this.readyState = LocalEventSource.CONNECTING;
        this.emit('error');
        this.timer = setTimer(() => this.connect(), reconnectMs);
      };
      const handle = bridge.openEvents(this.url, this.lastEventId, onStart, (text) => parser.push(text), onEnd);
      this.stream = handle;
    }

    close() {
      this.readyState = LocalEventSource.CLOSED;
      if (this.timer !== null) clearTimer(this.timer);
      this.timer = null;
      const stream = this.stream;
      this.stream = null;
      if (stream) Promise.resolve(stream.close()).catch((error) => console.error(error));
    }
  };
}

async function download(fetchFn, url, read) {
  const response = await fetchFn(url, { cache: 'no-store' });
  if (!response.ok) throw new LocalBackendError('download', `Could not download ${url.pathname} (${response.status}).`);
  return read(response);
}

function withTimeout(promise, ms) {
  let timer;
  const late = new Promise((_, reject) => {
    timer = setTimeout(() => reject(new LocalBackendError('timeout', `The demo took longer than ${ms / 1000} seconds to start.`)), ms);
  });
  return Promise.race([promise, late]).finally(() => clearTimeout(timer));
}

async function boot({ base, onProgress, fetchFn, importModule }) {
  onProgress(1, 'loading the Python runtime');
  const manifest = checkManifest(await download(fetchFn, new URL('manifest.json', base), (r) => r.json()));
  const { loadPyodide } = await importModule(new URL('pyodide/pyodide.mjs', base).href);
  const py = await loadPyodide({ indexURL: new URL('pyodide/', base).href });

  onProgress(2, 'loading the packages');
  const failures = [];
  await py.loadPackage(manifest.packages, { messageCallback: () => {}, errorCallback: (m) => failures.push(m) });
  if (failures.length > 0) throw new LocalBackendError('packages', failures.join(' '));
  const [app, ...wheels] = await Promise.all(
    [manifest.app, ...manifest.wheels].map((name) => download(fetchFn, new URL(name, base), (r) => r.arrayBuffer())),
  );
  const site = py.runPython('import site; site.getsitepackages()[0]');
  for (const wheel of wheels) py.unpackArchive(wheel, 'zip', { extractDir: site });
  py.FS.mkdirTree('/app');
  py.unpackArchive(app, 'zip', { extractDir: '/app' });

  onProgress(3, 'starting the app');
  py.runPython("import importlib, sys; sys.path.insert(0, '/app'); importlib.invalidate_caches()");
  const page = py.pyimport('linkfall.browser.bridge').start_page();
  // Pyodide turns null into JsNull and only undefined into None, so absent values go as undefined.
  return {
    request: (method, path, body, headers) => page.request(method, path, body ?? undefined, headers),
    openEvents: (path, lastId, onStart, onChunk, onEnd) => page.open_events(path, lastId ?? undefined, onStart, onChunk, onEnd),
  };
}

// Loads Pyodide and the app from runtime/ beside the page. Any failure rejects with a
// LocalBackendError; it never resolves to a backend that does not work.
export async function startLocalBackend({
  base = new URL('../runtime/', import.meta.url),
  onProgress = () => {},
  fetchFn = (...args) => globalThis.fetch(...args),
  importModule = (url) => import(url),
  timeoutMs = LOAD_TIMEOUT_MS,
  hasWasm = typeof globalThis.WebAssembly === 'object',
} = {}) {
  if (!hasWasm) throw new LocalBackendError('no_wasm', "This browser can't run WebAssembly, so the demo can't start here.");
  let bridge;
  try {
    bridge = await withTimeout(boot({ base, onProgress, fetchFn, importModule }), timeoutMs);
  } catch (error) {
    if (error instanceof LocalBackendError) throw error;
    throw new LocalBackendError('start', "The demo couldn't start.", { cause: error });
  }
  return { fetchFn: createFetchFn(bridge), EventSourceCtor: createEventSourceClass(bridge), local: true };
}
