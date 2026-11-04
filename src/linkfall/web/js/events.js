// The server-sent event stream for one run. EventSource reconnects by itself and sends
// Last-Event-ID, so a dropped connection resumes without a gap.
export const ROW_KINDS = Object.freeze([
  'engine', 'command', 'turn', 'proposal', 'no_proposal', 'decision', 'selector', 'pilot', 'unknown',
]);

// Returns the row, or null when the message is not a log row.
export function parseRow(data) {
  let row;
  try {
    row = JSON.parse(data);
  } catch {
    return null;
  }
  const ok =
    row !== null &&
    typeof row === 'object' &&
    Number.isInteger(row.id) &&
    Number.isInteger(row.turn) &&
    typeof row.kind === 'string' &&
    row.payload !== null &&
    typeof row.payload === 'object';
  return ok ? row : null;
}

export function openEvents(runId, { onRow, onStatus, EventSourceCtor = globalThis.EventSource }) {
  const source = new EventSourceCtor(`/api/runs/${encodeURIComponent(runId)}/events`);
  for (const kind of ROW_KINDS) {
    source.addEventListener(kind, (event) => {
      const row = parseRow(event.data);
      if (row) onRow(row);
    });
  }
  source.addEventListener('open', () => onStatus?.('open'));
  source.addEventListener('error', () => onStatus?.('error'));
  return { close: () => source.close() };
}
