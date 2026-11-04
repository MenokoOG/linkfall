# 0008: Stream agent cards over SSE

Date: 2026-11-04 · Status: Proposed

## Context

A turn has up to three model calls. At 6 threads one Qwen call took a median of 8.8 s in our spike (8 calls; the first took 21 s), so a turn is near 27 s. At 12 threads the same call took over 100 s. A page that waits for the whole turn feels broken. The pilot should see rules agents answer at once and see each model agent land as it finishes.

The UI is static files served by the `api` container (ADR 0004). The design spec (Deep Space) fixes the look: three columns, the knob, five agent cards, the decision panel and a `aria-live="polite"` log.

## Decision

We will push the event log to the browser over server-sent events and keep the browser free of game logic.

- **One stream per run:** `GET /api/runs/{id}/events`. The server tails the event log table and sends each new row as an SSE message. The row id is the SSE `id`, so a reconnect with `Last-Event-ID` resumes with no gap.
- **Pilot actions** go by `POST /api/runs/{id}/commit` with allowlisted fields: link (10 to 90, step 5), an action enum, a run-mode enum. The response is an acknowledgement. State comes back only through the stream.
- **Card states:** `pending` (shows `state-loading.svg`, labeled "link sync"), `ready` (shows the proposal), `no proposal` (shows the reason from the log). Rules agents move to `ready` in the same tick as the turn start. Model agents move as each call finishes.
- **Model lag is shown, not hidden.** The loading state reads as link sync, with elapsed seconds. A slow call that times out becomes a "no proposal: timeout" card.
- **Plain browser code:** ES modules, no framework, no build step, no CDN, system fonts. All model and enemy text is set with `textContent`. The CSP forbids inline script.
- **Replay view** uses the same renderer. It feeds logged events through the same code path and shows the fingerprint result.
- **Accessibility:** WCAG 2.2 AA, keyboard knob with arrow keys and a range-input fallback, focus ring from the spec, `prefers-reduced-motion` honored, checked by a manual checklist at 360, 768 and 1366 px (plan, open question 6).

## Alternatives considered

- **WebSocket.** Considered for two-way traffic. Rejected because the pilot's inputs are rare and fit a POST, and SSE reconnects with less code. Revisit if we add live multi-user control.
- **Polling.** Considered because it is the simplest. Rejected because it adds delay and load for no gain. Revisit never.
- **A front-end framework with a build step.** Considered for component structure. Rejected: the design is one console, the repo must stay small and offline, and a toolchain adds supply-chain surface. Revisit if the UI grows past about 10 screens.
- **Wait for the full turn, then render.** Considered because it is easy. Rejected because a 27 s blank wait kills the demo.

## Consequences

- Pro: fast cards feel instant and slow ones explain themselves.
- Pro: one render path serves live play and replay.
- Con: SSE needs a long-lived connection. Mitigation: one stream per run, so the browser's per-host connection limit isn't a problem.
- Con: tailing a SQLite table means polling the table on the server. Mitigation: a short interval check on the row id, or an in-process notify when the supervisor appends. We pick the in-process notify first and keep polling as the fallback.
- Undo: moderate. The event schema is shared with ADR 0007.

OWASP Top 10 for LLM Applications 2025: LLM05 is addressed by `textContent` and the CSP. ASVS level 1 requirement IDs for output encoding and headers are listed in the scaffold PR.

## Related

0002 (log), 0004 (containers and bind), 0005 (proposals), 0006 (decisions), 0007 (replay).
