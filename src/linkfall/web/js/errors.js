import { ApiError } from './api.js';

// One readable line for any failure. Field problems from the server are appended.
export function describeError(error) {
  if (!(error instanceof ApiError)) return 'Something went wrong. Try again.';
  const fields = error.fields.map((f) => `${f.field}: ${f.problem}`);
  return fields.length ? `${error.message} (${fields.join('; ')})` : error.message;
}
