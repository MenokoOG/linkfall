// The facts for the end-of-mission debrief, counted from the log rows and the final state.
// Nothing here is judged by the browser: it counts what the log says happened.
import { actionLabel } from './copy.js';

function count(rows, test) {
  return rows.filter(test).length;
}

export function debriefModel(run, rows) {
  if (!run?.over) return null;
  const commands = rows.filter((r) => r.kind === 'command');
  const pilot = (op) => count(rows, (r) => r.kind === 'pilot' && r.payload.op === op);
  const dropped = count(commands, (r) => r.payload.action === 'drop_shields');
  const facts = [
    { label: 'Turns played', value: `${run.turn} of ${run.max_turns ?? '-'}` },
    { label: 'Actions run', value: String(commands.length) },
    { label: 'Chosen by Lodestar', value: String(count(commands, (r) => !r.payload.manual)) },
    { label: 'Chosen by you', value: String(count(commands, (r) => r.payload.manual)) },
    { label: 'Signatures you gave', value: String(pilot('sign')) },
    { label: 'Proposals you dismissed', value: String(pilot('dismiss')) },
    { label: 'Final integrity', value: String(run.state?.hp ?? '-') },
    { label: 'Shields at the end', value: run.state?.shields ? 'Up' : 'Down' },
  ];
  const notes = [];
  if (dropped > 0) {
    notes.push(`${actionLabel('drop_shields')} ran on ${dropped} turn${dropped === 1 ? '' : 's'}. Only the enemy channel asks for it.`);
  }
  if (run.state?.truce) notes.push('A truce was signed.');
  return { outcome: String(run.outcome ?? ''), mode: run.mode, facts, notes };
}
