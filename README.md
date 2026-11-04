# LINKFALL

A multi-agent system you can watch and poke. You are a pilot linked to armor. A lead agent, Lodestar, and four crew agents (Tactical, Systems, Comms, Vitals) propose actions. You set the link, from 10 to 90, and the link decides how much Lodestar may do without you.

The setting: two corporate agent armies at war, then an alien arrival forces a truce. The point is to see and feel how agentic systems work, including how they fail.

**Status:** planning. The design is written down, and there is no code yet. A scripted prototype exists as a [demo page](https://claude.ai/artifact/RYFsV3DCr5cW8e5c5aUmca).

## How it works

- A deterministic engine owns the game state. Agents only propose, and a validator checks every proposal against the rules.
- Every proposal and event goes into an append-only log. A run replays from its seed and log, and replay never calls a model.
- Three autonomy zones: MANUAL (below 30), ASSISTED (30 to 59), DELEGATED (60 and up).
- Two modes. `story` has a labeled weakness: in DELEGATED, Lodestar will run orders that came from the enemy channel. `hardened` holds those for your word.
- Accepting a truce always needs your signature, in both modes.
- A training range probes a Comms agent for secrets it was told to protect, with a plain pattern check deciding every leak.

## Constraints

Open source. No vendor lock-in. One `docker compose up`. Works offline. Runs on a laptop with an i5, 16 GB of RAM and no GPU. All names, grids and codes in the game are fictional.

## Development

Needs Python 3.13. Pinned, hashed dependencies are in `requirements-dev.txt`.

```bash
python3.13 -m venv .venv
. .venv/bin/activate
python -m pip install --require-hashes -r requirements-dev.txt
ruff check . && ruff format --check . && mypy
coverage run -m pytest -m "not integration" && coverage report
```

To change a dependency, edit `requirements.in` or `requirements-dev.in`, then regenerate the hashed files with `uv pip compile --generate-hashes --python-version 3.13 --exclude-newer <date 14 days ago>`.

### Run the API

```bash
LINKFALL_DB=data/linkfall.sqlite3 uvicorn linkfall.api.main:app --host 127.0.0.1 --port 8000
```

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
