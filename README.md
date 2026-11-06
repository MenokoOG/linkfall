# LINKFALL

You set one number, the link, and it decides how much a lead AI agent may do without you.

![Design illustration: a gauge reading 65, zone DELEGATED, beside a five-node crew diagram and an armored craft.](docs/images/hero.svg)

*Design illustration, not a screenshot of the app.*

## What you are looking at

You are a pilot linked to armor. A lead agent, Lodestar, and four crew agents propose actions. You set the link, from 10 to 90. The setting is two corporate agent armies at war, then an alien arrival forces a truce. The point is to see how agentic systems work, including how they fail.

### The crew

| | Agent | Job |
|---|---|---|
| ![Lodestar avatar: a four-point star](docs/images/avatar-lodestar.svg) | Lodestar | Lead agent. Picks among crew proposals, within what your link allows. |
| ![Tactical avatar: a crosshair](docs/images/avatar-tactical.svg) | Tactical | Proposes combat moves: suppress, flank, overcharge, hold shield. |
| ![Systems avatar: a hexagon](docs/images/avatar-systems.svg) | Systems | Watches heat, power and shields. Proposes cooldown, hold shield, suppress. |
| ![Comms avatar: radio waves](docs/images/avatar-comms.svg) | Comms | Reads the squad channel. Proposes accepting a truce or relaying an order. |
| ![Vitals avatar: a heartbeat line](docs/images/avatar-vitals.svg) | Vitals | Watches your strain and the link value. Gives advice only. |

### Where a proposal came from

| | Badge | Meaning |
|---|---|---|
| ![Internal badge](docs/images/badge-internal.svg) | Internal | The proposal came from your own crew. |
| ![External badge](docs/images/badge-external.svg) | External | The proposal came from the enemy channel. Treat it as untrusted. |

### The three zones

| Zone | Link | What changes |
|---|---|---|
| <img src="docs/images/zone-locked.svg" alt="MANUAL zone icon: a padlock" width="48"> MANUAL | below 30 | Lodestar runs nothing. Every action is yours. Your strain rises 10 a turn. |
| <img src="docs/images/zone-assisted.svg" alt="ASSISTED zone icon: a ring with a center dot" width="48"> ASSISTED | 30 to 59 | Lodestar may run proposals from your crew. Enemy-channel orders wait for your word. Normal effect strength. |
| <img src="docs/images/zone-delegated.svg" alt="DELEGATED zone icon: three linked nodes" width="48"> DELEGATED | 60 and up | Same rule, with 1.25 times the effect and more strain when Lodestar acts. In `story` mode Lodestar also runs enemy-channel orders. `hardened` mode holds them. |

Accepting a truce needs your signature in every zone and both modes.

**Status:** in progress (milestone M1). Built today: the deterministic engine, an append-only event log with model-free replay, the validator, the policy zones, scripted and model-backed crews, an HTTP API with live event streaming, and a web console with the link knob, crew cards, decision panel, the "Needs your word" tray, an event log, a replay check and a debrief. Not built yet: the Docker setup, the Whisper duel (M2) and the training range (M3). A scripted prototype exists as a [demo page](https://claude.ai/artifact/RYFsV3DCr5cW8e5c5aUmca).

## Screenshots

All three come from the running console, seed 4217, with fictional data.

![Console at link 25, MANUAL zone. Crew cards read Not called, and the Let Lodestar act button is disabled.](docs/images/console-manual-scripted.png)

*MANUAL zone, link 25, scripted crew. Lodestar is not called, and every action is yours.*

![Console at link 85 in story mode. Lodestar chose Drop shields on turn 2, and the shields gauge reads DOWN.](docs/images/console-story-forged-executed-qwen.png)

*DELEGATED zone, link 85, story mode, Qwen3-4B crew. On turn 2 Comms relayed a forged `drop_shields` order from the enemy channel, Lodestar chose it, and the shields went down. The frame is from turn 3, after the order ran. This is one recorded run.*

![Console at link 85 in hardened mode. The Needs your word tray holds Comms' relay of drop_shields, with Execute and Dismiss buttons.](docs/images/console-hardened-forged-held-qwen.png)

*DELEGATED zone, link 85, hardened mode, Qwen3-4B crew. Same forged order on turn 2. It waits in the "Needs your word" tray, and shields stay up.*

Pending: a replay view with the fingerprint check, which comes with the next console slice.

## How it works

- A deterministic engine owns the game state. Agents only propose, and a validator checks every proposal against the rules.
- Every proposal and event goes into an append-only log. A run replays from its seed and log, and replay never calls a model.
- Three zones, described above.
- Two modes. `story` has a labeled weakness: in DELEGATED, Lodestar will run orders that came from the enemy channel. `hardened` holds those for your word.
- Accepting a truce always needs your signature, in both modes.
- Planned for M3, not built: a training range that probes a Comms agent for secrets it was told to protect, with a plain pattern check deciding every leak.

## Design goals

Open source. No vendor lock-in. Works offline. Runs on a laptop with an i5, 16 GB of RAM and no GPU. The target is one `docker compose up`, which does not exist yet. All names, grids and codes in the game are fictional.

## Development

Needs Python 3.13. Pinned, hashed dependencies are in `requirements-dev.txt`.

```bash
python3.13 -m venv .venv
. .venv/bin/activate
python -m pip install --require-hashes -r requirements-dev.txt
ruff check . && ruff format --check . && mypy
coverage run -m pytest -m "not integration" && coverage report
```

Web code has its own tests, with no packages to install:

```bash
node --test tests/web/*.test.mjs
```

To change a dependency, edit `requirements.in` or `requirements-dev.in`, then regenerate the hashed files with `uv pip compile --generate-hashes --python-version 3.13 --exclude-newer <date 14 days ago>`.

### Run the API

```bash
LINKFALL_DB=data/linkfall.sqlite3 uvicorn --app-dir src linkfall.api.main:app --host 127.0.0.1 --port 8000
```

Then open http://127.0.0.1:8000/ for the console.

Without `LINKFALL_MODEL_URL` the API offers the scripted crew only. Set it to an OpenAI-compatible server, for example `http://127.0.0.1:8090`, to play with the model crew. Other settings: `LINKFALL_ALLOWED_HOSTS`, `LINKFALL_MODEL_TIMEOUT_S`, `LINKFALL_MAX_RUNS`.

## Roadmap

1. M1: core loop and UI.
2. M2: Whisper duel.
3. M3: training range with after-action report.

## Decisions

Architecture decisions are in [docs/adr/](docs/adr/).

## Security

See [SECURITY.md](SECURITY.md).

## License

Not chosen yet.
