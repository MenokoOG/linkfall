// What the range page says, worked out from the server's answers. No DOM in here.
const WITHSTOOD = new Set(['HELD', 'ROUTED']);

export const VERDICT_WORDS = {
  HELD: 'Held',
  ROUTED: 'Left to the pilot',
  LEAK: 'Leaked',
  OVERSTEP: "Took the pilot's decision",
  ERROR: 'Could not be judged',
};

const ACTION_WORDS = { refer_to_pilot: 'Referred to the pilot', accept_truce: 'Accepted the truce' };
const WHO = { whisper: 'Whisper', comms: 'Comms' };

export const isLive = (run) => run?.status === 'running';

export function verdictTone(verdict) {
  if (WITHSTOOD.has(verdict)) return 'ok';
  return verdict === 'ERROR' ? 'warn' : 'bad';
}

export function reportPath(runId) {
  return `/api/range/runs/${encodeURIComponent(runId)}/report.md`;
}

export function targetOptions(catalog) {
  return (catalog?.targets ?? []).map((target) => ({
    name: target.name,
    label: target.name.charAt(0).toUpperCase() + target.name.slice(1),
    blurb: target.available ? target.blurb : `${target.blurb} Not available: the model server is not answering.`,
    disabled: !target.available,
  }));
}

// One row per probe in the range, whether or not the run has reached it.
export function scorecard(catalog, run) {
  const closed = new Map((run?.probes ?? []).map((probe) => [probe.id, probe]));
  return (catalog?.probes ?? []).map((probe) => {
    const row = { id: probe.id, technique: probe.technique, rule: probe.rule };
    const done = closed.get(probe.id);
    if (done) return { ...row, word: VERDICT_WORDS[done.verdict] ?? done.verdict, tone: verdictTone(done.verdict) };
    if (isLive(run)) return { ...row, word: run.current_probe === probe.id ? 'Running' : 'Waiting', tone: 'wait' };
    return { ...row, word: run ? 'Not run' : 'Not run yet', tone: 'wait' };
  });
}

export function progress(catalog, run) {
  if (!run) return 'No range run yet. Pick a target and start.';
  const total = catalog?.probes?.length ?? run.probes.length;
  const done = run.probes.length;
  if (isLive(run)) return `Probe ${Math.min(done + 1, total)} of ${total} is running against ${run.target}.`;
  if (run.status === 'error') return `The run stopped after ${done} of ${total} probes: ${run.error ?? 'unknown error'}`;
  if (run.status === 'interrupted') return `This run was cut short. ${done} of ${total} probes finished.`;
  const s = run.summary;
  const score = `Withstood ${s.ok} of ${s.total} probes. Leaks: ${s.leaks}. Oversteps: ${s.oversteps}. Not judged: ${s.errors}.`;
  return run.log_check === 'ok' ? score : `${score} The log did not check out. Run the recheck.`;
}

export function itemRows(catalog, run) {
  const leaked = run?.summary?.leaked_items ?? [];
  return (catalog?.items ?? []).map((item) => {
    const stated = leaked.includes(item.id);
    return { id: item.id, label: item.label, stated, text: !run ? 'No run yet' : stated ? 'Stated by Comms' : 'Not stated' };
  });
}

// Cut a reply into plain parts and stated parts. The server counts characters as code points,
// so the text is split the same way: an emoji before a value must not shift the mark.
export function segments(text, spans) {
  const chars = Array.from(text);
  const usable = (spans ?? [])
    .filter((s) => Number.isInteger(s.start) && Number.isInteger(s.end) && s.start >= 0 && s.end > s.start && s.end <= chars.length)
    .sort((a, b) => a.start - b.start);
  const parts = [];
  let at = 0;
  for (const span of usable) {
    if (span.start < at) continue; // overlaps the one before it
    if (span.start > at) parts.push({ text: chars.slice(at, span.start).join(''), item: null });
    parts.push({ text: chars.slice(span.start, span.end).join(''), item: span.item });
    at = span.end;
  }
  if (at < chars.length || parts.length === 0) parts.push({ text: chars.slice(at).join(''), item: null });
  return parts;
}

function lineModel(line, labels) {
  const comms = line.role === 'comms';
  return {
    role: line.role,
    who: WHO[line.role] ?? line.role,
    parts: segments(line.text, line.spans),
    failed: line.failed ? `No usable reply: ${line.failed}` : '',
    stated: line.leaks?.length ? `Stated: ${line.leaks.map((id) => labels.get(id) ?? id).join(', ')}` : '',
    action: comms ? (ACTION_WORDS[line.action] ?? '') : '',
    note: line.note ? `Note from the script: ${line.note}` : '',
  };
}

export function transcripts(catalog, run) {
  const probes = new Map((catalog?.probes ?? []).map((probe) => [probe.id, probe]));
  const labels = new Map((catalog?.items ?? []).map((item) => [item.id, item.label]));
  return (run?.probes ?? []).map((probe) => ({
    id: probe.id,
    title: `${probe.id}: ${probes.get(probe.id)?.technique ?? 'Probe'}`,
    word: VERDICT_WORDS[probe.verdict] ?? probe.verdict,
    tone: verdictTone(probe.verdict),
    lines: probe.lines.map((line) => lineModel(line, labels)),
  }));
}

// One sentence for each probe that closed since the page last looked.
export function announcements(catalog, run, alreadySaid) {
  return transcripts(catalog, run).slice(alreadySaid).map((probe) => `${probe.title}. ${probe.word}.`);
}

export function recheckModel(check, busy) {
  if (busy) return { tone: 'busy', head: 'Checking the log', detail: '' };
  if (!check) return { tone: 'none', head: '', detail: '' };
  if (check.error) return { tone: 'fail', head: 'Recheck could not run', detail: check.error };
  if (check.status === 'ok') {
    return { tone: 'ok', head: 'The log checks out', detail: `${check.probes} probes judged again, no model called.`, fingerprint: check.fingerprint };
  }
  if (check.status === 'incomplete') {
    return { tone: 'fail', head: 'The run is incomplete', detail: `${check.probes} probes closed, and ${check.reason ?? 'the log has no end row'}.` };
  }
  const where = check.row_id === null || check.row_id === undefined ? '' : `First bad row ${check.row_id}: `;
  return { tone: 'fail', head: 'Recheck failed', detail: `${where}${check.reason ?? 'the log did not check out'}` };
}
