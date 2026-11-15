# Accessibility checklist (WCAG 2.2 AA)

Gate 6 evidence for the web console. A manual checklist plus the measurements below, updated
with each console slice. Last updated for slice 2 (crew cards, decision panel, tray), 2026-11-04.

How it was checked: headless Chromium (Playwright 1.64.1, run from a scratch folder, not a
repo dependency) against the real app at 1366, 768 and 360 pixels wide, driven by script. No
screen reader was used. The checks marked "not tested" need a person with assistive technology.

## Slice 1: shell, link knob, mission form, engine state

| Area | Result | Evidence |
|---|---|---|
| Keyboard reach | pass | Tab order: skip link, knob, range input, mode, crew, seed, start, new seed |
| Knob by keyboard | pass | Arrow keys move one step, Home and End jump; 3 presses took 55 to 70 |
| Knob by pointer | pass | Dragging to the lower left gave 15, Manual |
| Range input fallback | pass | Native range input in the tab order; setting 85 moved the knob and the zone |
| Roles and names | pass | `role="slider"` with a label, `aria-valuenow` and `aria-valuetext` ("70, Delegated"); radios are native inputs in a fieldset with a legend |
| Battlefield view | pass | The art is `aria-hidden` and adds no facts: a text caption under it repeats the counts and shield state, which are also on the gauges. The caption is not a live region, so it is never re-read. Every animation stops under reduced motion. No sideways scroll at 390 px (headless Chromium, 2026-11-15). Caption contrast not measured |
| Live updates | partial | The banner has `role="status"` and form errors `role="alert"`. The event log is `role="log"` (polite) and only appends new lines, so nothing is re-read. Built in slice 3; not yet checked in a browser or with a screen reader |
| Focus visible | pass | 2 px cyan ring with a 3 px offset on every control |
| Target size | pass | Every button, radio label and field measured 44 px high or more; the knob is 178 px |
| Reflow | pass | No horizontal scroll at 1366, 768 and 360 pixels |
| Contrast, text | pass | 37 rendered text nodes with backgrounds sampled from a screenshot: body text 11.0 to 1 at worst, secondary text 4.98 to 1 at worst. Button labels (dark on a cyan to warm-white gradient) were not sampled; computed from the colors they are 11.0 to 1 or better |
| Contrast, non-text | partial | Focus ring cyan on space is 11.0 to 1. Unlit knob ticks (1.7 to 1) are decoration; the number and the zone name carry the value |
| Color is never the only cue | pass | The zone is a word and an icon as well as a color; shield state is the word UP or DOWN |
| Motion | pass | `prefers-reduced-motion` stops the aurora and the transitions |
| Language, title, landmarks | pass | `lang="en"`, a page title, `main`, `header`, a skip link |
| Zoom to 200 percent | not tested | |
| Screen reader | not tested | |

## Slice 2: crew cards, enemy channel, decision panel, "Needs your word" tray

| Area | Result | Evidence |
|---|---|---|
| Keyboard only, end to end | pass | Tab reached "Run: Tactical", Enter committed the turn, the next turn opened; the tray's Dismiss worked from the keyboard |
| Focus after a live update | pass | The control that had focus is rebuilt on each update. Focus returns to the same control if it still exists, and otherwise moves to the decision panel heading (it was `h-decision` in both runs), never to the top of the page |
| Streamed answers announced | pass | A polite status region says "systems: cooldown" or "tactical: no proposal" as each answer arrives; whole cards are not live regions, so the page is not chatty |
| Names | pass | Cards are `article` elements named by their heading. Card buttons carry the agent ("Run Flank as proposed by Tactical"). Provenance badges have `alt` text "internal" or "external" |
| Status is a word | pass | Eligible, Needs your word, Advice only, No proposal, Dismissed, Not called. The orange tray border and the enemy-channel dot are extra cues, not the only ones |
| Signature warning | pass | A low score is written out ("Signature 0.70, below the normal 0.94") as well as colored |
| Model and enemy text | pass | Rendered only as text nodes (static test); a forged `[PRIORITY / ASHGROVE-CMD]` message showed as plain text |
| Motion | partial | The loading image (`state-loading.svg`) is animated and carries no reduced-motion rule of its own, so the page hides it under `prefers-reduced-motion` and keeps the words "Waiting for the link to sync". Not tested with the OS setting on |
| Reflow and targets | not re-measured | Slice 1 measurements stand; the new buttons use the same 44 px minimum |
| Screen reader | not tested | |

## Still to do in later slices

Slice 3 shipped the log, the replay check and the debrief without a browser session. Still to do: check in a browser that streamed updates don't steal focus, and that the log, replay result and debrief meet the target size and contrast rows above. Re-measure reflow, target sizes and contrast on the finished page.
