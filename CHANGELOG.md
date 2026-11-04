# Changelog

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning will follow Semantic Versioning once there is a release.

## [Unreleased]

### Added
- ADRs 0001 to 0006, all Accepted (`docs/adr/`).
- README, SECURITY policy and Dependabot config for GitHub Actions and pip.
- Validator (`src/linkfall/validator/`): strict reply model, schema check, identity, allowlist and rule-precondition stages. Rejects with a reason and never repairs.
- Event log (`src/linkfall/eventlog/`): append-only SQLite store, atomic write batches, recorder, model-free replay that reports the first bad row, JSON export and import, and two golden logs replayed in CI (`tests/golden/`, `scripts/refresh_golden.py`).
- Engine (`src/linkfall/engine/`): pure state, rules, effects, zone table, seeded RNG, scenario beats, fingerprint. Parity tests reproduce the prototype turn by turn on 4 recorded traces.
- Project scaffold: pinned and hashed dependencies, ruff, mypy strict, pytest with an 80% coverage floor, CI with SHA-pinned actions, ASVS level 1 checklist (`docs/security/asvs-l1.md`).
- M1 plan (`docs/plans/`) and Proposed ADRs 0007 (replay and evals), 0008 (SSE streaming UI) and 0010 (model pick).
