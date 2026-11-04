# Accessibility checklist (WCAG 2.2 AA)

Gate 6 evidence for the web console. A manual checklist plus the measurements below, updated
with each console slice. Last updated for slice 1 (shell and knob), 2026-11-04.

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
| Live updates | partial | The banner has `role="status"` and form errors `role="alert"`. The event log live region comes with slice 3 |
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

## Still to do in later slices

Crew cards and the decision panel (slice 2): provenance badges need text alternatives, and held
proposals need clear status words. Event log and replay (slice 3): an `aria-live="polite"` log,
and a check that streamed updates don't steal focus.
