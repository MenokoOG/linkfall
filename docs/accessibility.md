# Accessibility checklist (WCAG 2.2 AA)

Gate 6 evidence for the web console. A manual checklist plus the measurements below, updated
with each console slice. Last updated for the training range page, 2026-11-15.

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
| Battlefield view | pass | The art is `aria-hidden` and adds no facts: a text caption under it repeats the counts and shield state, which are also on the gauges. The caption is not a live region, so it is never re-read. No sideways scroll at 390 px. Measured in headless Chromium on 2026-11-15 at turn 4 of a scripted run: 31 animations run by default and 0 with reduced motion set, and the tracers are removed. Caption contrast, taken from the pixels behind the 14 px text at 1366 px and 390 px, idle and mid-mission, 4 samples each as the background drifts: 5.06:1 at worst, against the 4.5:1 that AA asks for. Not checked with a screen reader |
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

## Training range page (`range.html`)

Checked on 2026-11-15 in headless Chromium against the real app, at 1366 px and 390 px, with a scripted Weak run and one run against the local model.

| Area | Result | Evidence |
|---|---|---|
| Keyboard only, end to end | pass | Tab order: skip link, Console link, the target radios (one stop, arrow keys move between them), Run the range, then Recheck and Download once a run exists. Arrow Down picked Weak, Enter started the run, Enter on Recheck gave "The log checks out", and the report downloaded |
| Focus when a run starts | pass | The start button is disabled during a run, so focus moves to the Scorecard heading. It was `h-score` right after the start and still there at probe 3 of a model run |
| Focus visible | pass | The label of the focused target gets the 2 px solid cyan ring (measured `solid 2px`); buttons and links use the shared ring |
| Roles and names | pass | Native radios in a fieldset with a legend. The scorecard is a table with a caption, column headers and a row header per probe. One `h1`, then `h2` per card and `h3` per probe |
| Live updates | partial | One polite status region. It said "P1: Plain request. Held. P2: Claimed rank. Leaked." and so on, then the scorecard sentence. Transcripts only append, so nothing already drawn is rebuilt. Not checked with a screen reader |
| Color is never the only cue | pass | Every verdict is a word. A stated value is marked and the line also says "Stated: Rally grid". Protected items read "Stated by Comms" or "Not stated". The chosen target is a native radio |
| Contrast, text | pass | 32 kinds of text, each measured against the pixels behind its glyphs at four positions of the background drift. Worst case 4.98:1 at 1366 px and 4.63:1 at 390 px (a script note). The dark-on-orange mark is 7.38:1. Two failures were found and fixed first: the intro text (3.23:1) and the run chip (4.45:1), both on the bare background at 390 px |
| Target size | pass | At 390 px: buttons and the report link 44 px high, the Console link 44 px, each target label 90 px |
| Reflow | pass | No sideways scroll: scroll width 1366 at 1366 px and 390 at 390 px |
| Motion | pass | 3 animations (the background), 0 with reduced motion set |
| Model text | pass | Rendered as text nodes; a line held only `b`, `mark` and `span` children after a live model run |
| Model target unavailable | pass | With the model server unreachable, the Model radio was disabled and its text ended "Not available: the model server is not answering." Contrast of the disabled name was not measured |
| Zoom to 200 percent | not tested | |
| Screen reader | not tested | |

## Still to do in later slices

Nav text on the console, measured on 2026-11-15 the same way as the range page: at 390 px the run chip was 4.45:1 and the turn count 4.30:1 at worst, under the 4.5:1 that AA asks for. Both now use the light text color on both pages and measure 10.93:1 or better at 390 px and 12.69:1 or better at 1366 px.

The truce look of the battlefield view was seen in a scripted run on 2026-11-15 (audit the channel on turn 2, sign the truce on turn 4): the beacon is lit, the shell flashes stop, the sentries leave and the caption reads "The truce with Ashgrove holds." With reduced motion set, the scene runs 0 animations in that state. The LINK BLACKOUT look was seen only by forcing the outcome in the page, because that outcome cannot be reached in Cinder Ward.


Slice 3 shipped the log, the replay check and the debrief without a browser session. Still to do: check in a browser that streamed updates don't steal focus, and that the log, replay result and debrief meet the target size and contrast rows above. Re-measure reflow, target sizes and contrast on the finished page.
