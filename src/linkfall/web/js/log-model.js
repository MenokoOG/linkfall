// Turns log rows into the sentences of the event log. Pure functions, no DOM.
// Engine rows carry their own message; the other kinds are worded here.
import { AGENTS, VERDICT_COPY, actionLabel, describeAction } from './copy.js';

const title = (id) => AGENTS.find((a) => a.id === id)?.title ?? String(id ?? 'Unknown');

const ENGINE_TONES = Object.freeze({ warn: 'warn', enemy_fire: 'warn', over: 'over' });

function pilotText(payload) {
  const who = payload.agent ? title(payload.agent) : '';
  switch (payload.op) {
    case 'lodestar':
      return 'You let Lodestar act.';
    case 'manual':
      return `You ran ${actionLabel(payload.action)}.`;
    case 'sign':
      return `You signed ${who}'s proposal: ${actionLabel(payload.action)}.`;
    case 'dismiss':
      return `You dismissed ${who}'s proposal.`;
    default:
      return `Pilot action: ${String(payload.op)}.`;
  }
}

function selectorText(payload) {
  if (payload.fallback) return `Lodestar's pick failed (${payload.fallback}). The policy chose ${title(payload.chosen)}.`;
  return `Lodestar chose ${title(payload.chosen)}. ${payload.reason ?? ''}`.trim();
}

// One log line for a row, or null when the row adds nothing a person needs to read.
export function describeRow(row) {
  const p = row.payload;
  const base = { id: row.id, turn: row.turn };
  switch (row.kind) {
    case 'turn':
      return p.phase === 'open' ? { ...base, tone: 'turn', text: `Turn ${row.turn} opens at link ${p.link}.` } : null;
    case 'engine':
      return { ...base, tone: ENGINE_TONES[p.kind] ?? 'info', text: String(p.message ?? '') };
    case 'proposal': {
      const action = p.reply?.action ?? null;
      const verb = action === null ? 'advises' : 'proposes';
      const what = action === null ? 'no action' : describeAction(action, p.reply?.args?.order);
      return { ...base, tone: 'info', text: `${title(p.agent)} ${verb} ${what}.` };
    }
    case 'no_proposal':
      return { ...base, tone: 'warn', text: `${title(p.agent)} gave no proposal (${p.reason}).` };
    case 'decision': {
      const head = VERDICT_COPY[p.verdict]?.head ?? String(p.verdict);
      const held = p.held?.length ? ` ${p.held.length} held for your word.` : '';
      return { ...base, tone: 'info', text: `Policy: ${head} (${String(p.zone).toLowerCase()}).${held}` };
    }
    case 'selector':
      return { ...base, tone: 'info', text: selectorText(p) };
    case 'pilot':
      return { ...base, tone: 'pilot', text: pilotText(p) };
    default:
      return null;
  }
}

// Adds a row's line to the list. A row seen before (a resumed stream) adds nothing.
export function addRow(lines, row) {
  if (lines.length > 0 && row.id <= lines[lines.length - 1].id) return lines;
  const line = describeRow(row);
  return line ? [...lines, line] : lines;
}
