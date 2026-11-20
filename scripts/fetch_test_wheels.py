"""Fetch pytest and its dependencies, hash-checked, for the suite run on Pyodide.

Run from the repo root:  python scripts/fetch_test_wheels.py [--out .cache/pyodide-test-wheels]

The versions and hashes come from requirements-dev.txt. These wheels are for CI only; the site
never ships them.
"""

import argparse
import sys
from pathlib import Path

from build_pages import (
    ROOT,
    BuildError,
    Fetch,
    fetch_verified,
    https_fetch,
    prepare_out,
    requirement_pins,
    wheel_files,
)

TEST_WHEELS = ("iniconfig", "packaging", "pluggy", "pygments", "pytest")


def fetch_test_wheels(
    out: Path,
    *,
    fetch: Fetch = https_fetch,
    cache: Path = ROOT / ".cache" / "pages",
    requirements_path: Path = ROOT / "requirements-dev.txt",
) -> list[str]:
    pins = requirement_pins(requirements_path.read_text())
    pinned = wheel_files(TEST_WHEELS, pins, fetch)
    payload = {Path(item.dest).name: fetch_verified(item, fetch, cache) for item in pinned}
    prepare_out(out)  # the same guard as the site build
    for name, data in payload.items():
        (out / name).write_bytes(data)
    return sorted(payload)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch the pytest wheels for the Pyodide run.")
    parser.add_argument("--out", type=Path, default=ROOT / ".cache" / "pyodide-test-wheels")
    args = parser.parse_args(argv)
    try:
        names = fetch_test_wheels(args.out)
    except BuildError as exc:
        sys.stderr.write(f"fetch_test_wheels: {exc}\n")
        return 1
    sys.stdout.write(f"fetched {len(names)} wheels into {args.out}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
