# Runbook: the hosted demo on GitHub Pages

The hosted demo is the scripted crew running in the visitor's browser on Pyodide (ADR 0012). GitHub Pages serves static files; there is no server to watch. This runbook covers the first deploy, each later deploy, rollback and a Pyodide upgrade.

Commands are bash, from the repo root, on WSL.

## Who does what

Turning on Pages, creating tags and running the deploy are Lawrence's. An agent can build and check locally and run the browser check against the live URL.

## Before the first deploy

1. The repo is public. A private repo gets no Pages site unless the account's plan includes it, and the plan isn't confirmed.
2. Settings > Pages > Source: **GitHub Actions**.
3. A release tag that contains `scripts/build_pages.py`. `v1.0.0` predates it, so the first deploy needs a new tag, for example `v1.1.0`.
4. After the first deploy, Settings > Pages shows **Enforce HTTPS**. Make sure it's on, then update the 12.x row in `docs/security/asvs-l1.md`.

## Build and check locally

Build the site. Every runtime file is checked against its hash, and the build stops on the first mismatch:

```bash
python scripts/build_pages.py
```

Run the Python suite on Pyodide with exactly the files in `dist/`, the same job CI runs:

```bash
python scripts/fetch_test_wheels.py && node scripts/test_pyodide.mjs
```

Serve it under `/linkfall/`, the path Pages uses:

```bash
mkdir -p /tmp/linkfall-site && ln -sfn "$PWD/dist" /tmp/linkfall-site/linkfall && python3 -m http.server -d /tmp/linkfall-site 8080 --bind 127.0.0.1
```

Then open http://127.0.0.1:8080/linkfall/ and http://127.0.0.1:8080/linkfall/range.html. Port 8000 is the local stack's, so use another.

## Deploy

Actions > pages > Run workflow, then type the tag, for example `v1.1.0`. The workflow:

1. Refuses anything that isn't in `v1.2.3` form.
2. Checks out that tag and builds `dist/` with every hash checked.
3. Runs the Python suite on Pyodide with the files about to ship.
4. Uploads and deploys. The deploy job is the only one that can write to Pages.

## Check the live site

The workflow run prints the URL. Expected: https://menokoog.github.io/linkfall/ and https://menokoog.github.io/linkfall/range.html (not confirmed until the first deploy). On both pages:

- The banner reaches "Running in your browser with the scripted crew."
- A mission plays to an outcome, the log fills, and Replay says "Replay matches".
- A range run finishes, the report downloads, and Recheck says "The log checks out".
- The browser console shows no errors and no policy violations.

If any check fails, roll back.

## Rollback

Run the workflow again with the previous tag. A failed hash check or a failed test stops the build job before the upload, so a broken build never reaches the deploy step.

## Upgrade Pyodide

New pins must be at least 14 days old. Moving to 314.0.8 is allowed from 2026-11-27.

1. Read the release's changelog and check advisories for Pyodide (its repo's Security tab and the GitHub Advisory Database). Dependabot doesn't watch `pages/runtime.json`.
2. Get the new SHA-256 of each file in `pages/runtime.json` from two sources: the npm package (`npm pack pyodide@<version>`) and the jsDelivr copy (`https://cdn.jsdelivr.net/pyodide/v<version>/full/`). Both must agree. The wheel hashes must also match the new `pyodide-lock.json`.
3. Update `version`, `base_url` and `files` in `pages/runtime.json`. If Pyodide's Python or pydantic changes, say so in the PR.
4. Run the build, the Pyodide suite and the browser check above. CI runs the first two on the PR.

The pure-Python wheels need no step here: they follow `requirements.txt`, and Dependabot updates that.

## When something fails

| Symptom | Likely cause | Next check |
|---|---|---|
| Build stops with "expected sha256 ..., got ..." | A file changed upstream, or the download was cut short | Download it again by hand and compare. Never edit the hash to make the build pass without finding out why |
| Build stops with "no single pure wheel" | `requirements.txt` was bumped and PyPI has no pure wheel at that hash | Read the package's files on PyPI |
| Page shows an integrity error while loading | A Pyodide package file is missing or differs from `pyodide-lock.json` | Compare `dist/runtime/pyodide/` with `pages/runtime.json` |
| Banner stays on a start-up step, then the error panel | A file under `runtime/` failed to load, or the download took over 60 s | Network tab in the browser's dev tools |
| `pyodide` CI job fails but `gates` passes | The code depends on something newer than Pyodide's Python or pydantic | Run `node scripts/test_pyodide.mjs` locally and read the failing test |
