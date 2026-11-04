# 0004: Two containers on an internal network

Date: 2026-11-04 · Status: Proposed

## Context

LINKFALL must run from one `docker compose up`, work offline, and avoid vendor lock-in. The development machine is an Asus Vivobook (i5, 16 GB RAM, integrated graphics) running Windows with WSL Ubuntu. The repo lives on the WSL side.

Two paths carry untrusted input: enemy signal text that reaches the Comms agent, and model output that reaches the validator. The model server has no reason to reach the internet.

## Decision

We will ship a `compose.yaml` with two services.

- **`api`** runs the engine, supervisor, validator and event log. It also serves the static web UI, so no third container is needed. It publishes one port, bound to `127.0.0.1`.
- **`model`** runs an OpenAI-compatible model server (llama.cpp's server). It publishes no port.

Two networks:

- `backend` has `internal: true` and holds `api` and `model`. The model container has no route to the internet.
- `edge` is a normal bridge attached to `api` only, so the host can reach the published port.

Hardening for both containers: non-root user, read-only root filesystem, all capabilities dropped. Model weights live in a read-only bind mount (`./models:/models:ro`) and are downloaded by hand. They are never baked into an image.

Smoke tests: the `model` container must fail to reach the internet, and `api` must answer on `127.0.0.1` only. Both run at scaffold time. The first claim is unverified until then.

Threats at each trust boundary (STRIDE, only where a real threat exists):

- **Enemy channel text to the Comms prompt.** Tampering and elevation of privilege through prompt injection. Controls: the output is a proposal only, the validator and the engine rules still apply, and Lodestar's autonomy gate sits between a proposal and its execution.
- **`api` to `model`.** Denial of service and information disclosure. Controls: no published port, internal network, per-call timeout and token budget.
- **Browser to `api`.** Spoofing and tampering. Controls: bind to localhost, allowlist validation of every input (link value 10 to 90 in steps of 5, actions from a fixed enum). There are no accounts, so ASVS level 1 applies (ruling Q1). The checked requirement IDs get listed in the scaffold PR.

Dependencies added by this decision (versions and advisories get filled in and checked at scaffold):

| Package | Version | Pinned | Advisory status | Action |
|---|---|---|---|---|
| Python base image | TBD | no | unknown | pin by digest |
| FastAPI | TBD | no | unknown | pin, check advisories |
| Uvicorn | TBD | no | unknown | pin, check advisories |
| Pydantic | TBD | no | unknown | pin, check advisories |
| llama.cpp server | TBD | no | unknown | pin release, check advisories |
| SQLite | stdlib | n/a | n/a | none |

## Alternatives considered

- **Three containers, with a separate web server for the UI.** Considered for a clean split. Rejected because static files don't justify another container and another port. Revisit if the UI gets its own build pipeline.
- **Ollama as the model server.** Considered for easy model management. Rejected as the default because llama.cpp's server is lighter and any OpenAI-compatible server fits behind `ModelClient`. Revisit if model management becomes a pain.
- **FastAPI replaced by Flask or Starlette.** Considered for fewer parts. Rejected because FastAPI gives schema-checked input and SSE support with little code. Revisit if the dependency tree causes advisories.
- **Everything on the host with no containers.** Rejected because the requirement is one command and a self-contained setup.

## Consequences

- Pro: runs offline, one published port, and the model server can be swapped by config.
- Pro: a compromised model container has no route out.
- Con: `api` keeps normal outbound access, because Docker can't publish a port from an internal-only network. Mitigation: the code makes no outbound calls, the dependency table gets reviewed for phone-home behavior, and the container is non-root with a read-only filesystem. The residual risk stays on record. Revisit with an egress-blocking firewall rule if the project is ever hosted.
- Con: weights are large and downloaded by hand. Mitigation: the README documents the exact steps and a checksum.
- Undo: easy. The compose file and two Dockerfiles.

## Related

0002 (engine and agents), 0003 (supervisor).
