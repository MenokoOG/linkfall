// Where the API lives: the server (the default), or this tab when the page carries
// <meta name="linkfall-backend" content="browser"> (the hosted build, ADR 0012).
// Returns { fetchFn, EventSourceCtor, local } for api.js and events.js.
export function wantsBrowser(doc = globalThis.document) {
  return doc?.querySelector('meta[name="linkfall-backend"]')?.getAttribute('content') === 'browser';
}

export function serverBackend() {
  return { fetchFn: (...args) => globalThis.fetch(...args), EventSourceCtor: globalThis.EventSource, local: false };
}

async function loadBrowserBackend() {
  // Loaded only in the hosted build, so the server's pages never fetch these files.
  const [{ startLocalBackend, STEPS }, { createRuntimeStatus }] = await Promise.all([
    import('./local-backend.js'),
    import('./runtime-view.js'),
  ]);
  const status = createRuntimeStatus();
  try {
    const backend = await startLocalBackend({ onProgress: (step, label) => status.progress(step, STEPS, label) });
    status.ready();
    return backend;
  } catch (error) {
    status.failed(error.message, () => globalThis.location.reload());
    throw error; // the page stops here; the message is in the console too
  }
}

export async function pickBackend({ doc = globalThis.document, loadBrowser = loadBrowserBackend } = {}) {
  return wantsBrowser(doc) ? loadBrowser() : serverBackend();
}
