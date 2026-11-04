// The one place the browser talks to the server. Same origin only; every POST carries the
// custom header the server requires (ASVS 3.5.1). Responses are data, never HTML.
export const CSRF_HEADER = 'X-Linkfall-Request';

export class ApiError extends Error {
  constructor(status, message, fields = []) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.fields = fields;
  }
}

async function call(fetchFn, method, path, body) {
  if (!path.startsWith('/api/')) throw new Error('API paths must start with /api/');
  const headers = { Accept: 'application/json' };
  const init = { method, headers, credentials: 'same-origin', cache: 'no-store' };
  if (method === 'POST') {
    headers[CSRF_HEADER] = '1';
    headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(body ?? {});
  }
  let response;
  try {
    response = await fetchFn(path, init);
  } catch {
    throw new ApiError(0, 'The server could not be reached.');
  }
  let data = null;
  try {
    data = await response.json();
  } catch {
    data = null;
  }
  if (!response.ok) {
    const message = data && typeof data.error === 'string' ? data.error : `The server answered ${response.status}.`;
    throw new ApiError(response.status, message, Array.isArray(data?.fields) ? data.fields : []);
  }
  return data;
}

export function createApi(fetchFn = (...args) => globalThis.fetch(...args)) {
  return {
    health: () => call(fetchFn, 'GET', '/api/health'),
    createRun: (body) => call(fetchFn, 'POST', '/api/runs', body),
    getState: (runId) => call(fetchFn, 'GET', `/api/runs/${encodeURIComponent(runId)}/state`),
  };
}
