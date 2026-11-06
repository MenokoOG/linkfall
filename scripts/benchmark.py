"""Time a full mission against the running compose stack (gate 7, ADR 0010).

Run from the repo root after `docker compose up -d`:
    python scripts/benchmark.py --missions 2

It plays the Cinder Ward mission with the model crew, Lodestar choosing at link 85, and reports
the time from opening a turn to its commit, the model container's thread count and peak memory.
The 40 s p95 turn budget is proposed, not ruled; the exit code is 1 when it is missed.
"""

import argparse
import json
import statistics
import subprocess
import sys
import time
import urllib.request
from collections.abc import Callable
from typing import Any, TextIO

CSRF = {"X-Linkfall-Request": "1", "Content-Type": "application/json"}
LINK = 85
POLL_S = 0.5


def call(base: str, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(  # noqa: S310 - base is a user-supplied http URL
        base + path, data=data, method=method, headers=CSRF if method == "POST" else {}
    )
    with urllib.request.urlopen(request, timeout=300) as response:  # noqa: S310
        result: dict[str, Any] = json.load(response)
    return result


def wait_for(base: str, run_id: str, phase: str, timeout_s: float) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if call(base, "GET", f"/api/runs/{run_id}/state")["phase"] == phase:
            return
        time.sleep(POLL_S)
    raise TimeoutError(f"run {run_id} did not reach {phase} in {timeout_s:.0f} s")


def shell(*args: str) -> str:
    done = subprocess.run(args, capture_output=True, text=True, check=False)  # noqa: S603
    return done.stdout.strip()


def model_threads() -> str:
    container = shell("docker", "compose", "ps", "-q", "model")
    if not container:
        return "unknown"
    args = json.loads(shell("docker", "inspect", container, "--format", "{{json .Args}}"))
    return args[args.index("--threads") + 1] if "--threads" in args else "default"


def model_mem_mib() -> float:
    usage = shell("docker", "stats", "--no-stream", "--format", "{{.MemUsage}}", "linkfall-model-1")
    used = usage.split("/")[0].strip()
    for suffix, scale in (("GiB", 1024.0), ("MiB", 1.0), ("KiB", 1 / 1024)):
        if used.endswith(suffix):
            return float(used.removesuffix(suffix)) * scale
    return 0.0


def play(base: str, seed: int, timeout_s: float, sample_mem: Callable[[], None]) -> list[float]:
    run = call(
        base,
        "POST",
        "/api/runs",
        {"seed": seed, "mode": "story", "scenario": "cinder-ward", "crew": "model"},
    )
    run_id = str(run["run_id"])
    times: list[float] = []
    for turn in range(1, int(run["max_turns"]) + 1):
        started = time.monotonic()
        call(base, "POST", f"/api/runs/{run_id}/turns", {"link": LINK})
        wait_for(base, run_id, "awaiting_pilot", timeout_s)
        result = call(
            base,
            "POST",
            f"/api/runs/{run_id}/commit",
            {"turn": turn, "link": LINK, "choice": "lodestar"},
        )
        times.append(time.monotonic() - started)
        say(f"  seed {seed} turn {turn}: {times[-1]:.1f} s", sys.stderr)
        sample_mem()
        if result.get("state", {}).get("over"):
            break
        if call(base, "GET", f"/api/runs/{run_id}/state")["over"]:
            break
    return times


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(q * (len(ordered) - 1)))]


def say(text: str, stream: TextIO = sys.stdout) -> None:
    stream.write(text + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--missions", type=int, default=1)
    parser.add_argument("--seed", type=int, default=4217)
    parser.add_argument("--budget-s", type=float, default=40.0)
    parser.add_argument("--timeout-s", type=float, default=240.0)
    args = parser.parse_args()

    health = call(args.base, "GET", "/api/health")
    if health.get("model") != "up":
        say(f"model is {health.get('model')}; start the stack and wait", sys.stderr)
        return 2

    peak = [0.0]

    def sample() -> None:
        peak[0] = max(peak[0], model_mem_mib())

    turns: list[float] = []
    for i in range(args.missions):
        turns += play(args.base, args.seed + i, args.timeout_s, sample)

    p95 = percentile(turns, 0.95)
    say(f"threads={model_threads()} missions={args.missions} turns={len(turns)}")
    say(f"turn seconds: median={statistics.median(turns):.1f} p95={p95:.1f} max={max(turns):.1f}")
    say(f"model container memory peak: {peak[0]:.0f} MiB (limit 6144 MiB)")
    verdict = "within" if p95 <= args.budget_s else "over"
    say(f"p95 {p95:.1f} s is {verdict} the proposed {args.budget_s:.0f} s budget")
    return 0 if p95 <= args.budget_s else 1


if __name__ == "__main__":
    raise SystemExit(main())
