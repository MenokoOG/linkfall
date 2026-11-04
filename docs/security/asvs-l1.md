# ASVS level 1 checklist

Standard: OWASP ASVS 5.0.0, level 1 (no accounts, no user data; ruling Q1). IDs and wording come from the project's `v5.0.0_release` CSV, read on 2026-11-04. The CSV lists 70 level 1 requirements.

Status is **planned** until a step ships the control with a test. Update this file in the same PR that does.

## Applies

| ID | Requirement in short | Control | Step | Status |
|---|---|---|---|---|
| v5.0.0-1.2.1 | Output encoding fits the context (HTTP, HTML) | Server sends JSON and static files only; UI sets text with `textContent` | 9, 10 | planned |
| v5.0.0-1.2.3 | Encode when building JavaScript or JSON content | No server-built script; JSON from a serializer only | 9 | planned |
| v5.0.0-1.2.4 | Parameterized database queries | Event log uses `?` placeholders, never string-built SQL; test stores SQL metacharacters as data | 3 | **done** (`tests/test_eventlog_store.py`) |
| v5.0.0-1.3.2 | No `eval()` or dynamic code execution | Lint rule `S` (bandit set) in CI; no `eval` in the web code | 1, 10 | enforced for Python (lint) |
| v5.0.0-2.1.1 | Documentation defines input validation rules | API input table in the API docs (link 10 to 90 step 5, action enum, mode enum) | 9 | planned |
| v5.0.0-2.2.1 | Positive validation against allowlists | Pydantic models with enums and ranges | 9 | planned |
| v5.0.0-2.2.2 | Validation at a trusted service layer | Server validates; browser checks are convenience only | 9 | planned |
| v5.0.0-2.3.1 | Business flows in the expected order | Turn state machine; idempotency key per run and turn | 7 | planned |
| v5.0.0-3.2.1 | Browsers don't render content in the wrong context | `X-Content-Type-Options: nosniff`, CSP, API responses are JSON | 9 | planned |
| v5.0.0-3.2.2 | Text shown as text, via safe functions | `textContent` for all model and enemy text | 10 | planned |
| v5.0.0-3.4.2 | CORS allow-origin is fixed or allowlisted | No CORS headers; same origin only | 9 | planned |
| v5.0.0-3.5.1 | Cross-origin requests to sensitive functions are validated | Origin header check plus a custom request header on every POST | 9 | planned |
| v5.0.0-3.5.3 | Sensitive functions use POST, not GET or HEAD | State changes are POST only | 9 | planned |
| v5.0.0-4.1.1 | Content-Type matches content, with charset | Test over every route | 9 | planned |
| v5.0.0-11.4.1 | Only approved hash functions | SHA-256 for the replay fingerprint (`engine/fingerprint.py`) | 2 | **done** |
| v5.0.0-13.4.1 | No `.git` metadata in the deployed app | `.dockerignore` excludes `.git`; test checks the image | 11 | planned |
| v5.0.0-14.2.1 | No sensitive data in URLs | Run ids are random and carry no secret; no keys exist | 9 | planned |
| v5.0.0-15.1.1 | Documented remediation time frames for vulnerable components | Section below | 1 | **done** |
| v5.0.0-15.2.1 | No component past those time frames | Dependabot weekly; advisory check at each pin | 1 | **done** at pin time |
| v5.0.0-15.3.1 | Return only the required fields | Response models list fields explicitly | 9 | planned |

## Not applicable

| IDs | Reason |
|---|---|
| 6.x, 7.x, 9.x, 10.x | No accounts, sessions, tokens or OAuth |
| 8.1.1, 8.2.1, 8.3.1 | One local pilot, no roles. Any local process can call the API on 127.0.0.1; accepted for a localhost demo, and the bind is tested |
| 5.x | No file uploads. The model path comes from deployment config, not from a request |
| 12.1.1, 12.2.1, 12.2.2 | The `api` binds to 127.0.0.1 over HTTP and is not external facing. Revisit before any hosted release |
| 3.3.1, 3.4.1 | No cookies; no TLS, so no HSTS |
| 1.2.2, 1.2.5, 1.3.1, 1.5.1 | No dynamic URLs from untrusted data, no OS command built from input, no WYSIWYG, no XML |
| 11.3.1, 11.3.2 | No encryption in the application |
| 14.3.1 | No authenticated client data |
| 4.4.1 | No WebSocket (ADR 0008 uses SSE) |

## Vulnerable component time frames (v5.0.0-15.1.1)

Proposed for Lawrence's ruling. Clock starts when an advisory is published for a version we ship.

| Severity (CVSS v4.0) | Fix or mitigate within |
|---|---|
| Critical | 7 days |
| High | 14 days |
| Medium | 30 days |
| Low | next regular update |

Library updates in general: Dependabot opens weekly PRs; patch and minor updates merge after the gates pass. New pins, direct and transitive, use releases at least 14 days old (`--exclude-newer`).
