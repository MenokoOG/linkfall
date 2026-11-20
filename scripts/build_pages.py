"""Build the hosted demo site (ADR 0012): the web pages plus the Python app on Pyodide.

Run from the repo root:  python scripts/build_pages.py [--out dist] [--cache .cache/pages]

Every downloaded file is checked against a committed SHA-256 before it is used: Pyodide's files
against pages/runtime.json, the pure-Python wheels against requirements.txt. The output is the
layout web/js/local-backend.js reads. Nothing under src/ changes.
"""

import argparse
import hashlib
import io
import json
import re
import shutil
import sys
import urllib.request
import zipfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from linkfall.api.security import SECURITY_HEADERS  # noqa: E402 - needs the src path above

WEB = ROOT / "src" / "linkfall" / "web"
PACKAGE = ROOT / "src" / "linkfall"
RUNTIME = ROOT / "pages" / "runtime.json"
REQUIREMENTS = ROOT / "requirements.txt"
MARKER = ".linkfall-pages"  # marks a folder this script made, so it may replace it
PAGES = ("index.html", "range.html")
BACKEND_META = '<meta name="linkfall-backend" content="browser">'
_SHA = re.compile(r"[0-9a-f]{64}")
_PIN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s\\;]+)")
_HASH = re.compile(r"--hash=sha256:([0-9a-f]{64})")
_ABSOLUTE = {
    ".html": re.compile(r"""\s(?:src|href)=["']/"""),
    ".css": re.compile(r"""url\(\s*["']?/"""),
    ".js": re.compile(r"""["'`]/assets/"""),
}

Fetch = Callable[[str], bytes]


class BuildError(Exception):
    """The site can't be built as pinned. Nothing is published from a failed build."""


@dataclass(frozen=True)
class Pinned:
    url: str
    sha256: str
    dest: str  # path inside the output folder


def meta_policy() -> str:
    """The server's policy, fitted to a <meta> tag: frame-ancestors can't be set there, and
    Pyodide needs 'wasm-unsafe-eval' to compile its WebAssembly."""
    header = dict(SECURITY_HEADERS)[b"content-security-policy"].decode()
    parts = [p.strip() for p in header.split(";") if p.strip()]
    kept = [p for p in parts if not p.startswith("frame-ancestors")]
    return "; ".join(
        "script-src 'self' 'wasm-unsafe-eval'" if p == "script-src 'self'" else p for p in kept
    )


def normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def requirement_pins(text: str) -> dict[str, tuple[str, frozenset[str]]]:
    """name -> (version, allowed hashes) from a hashed requirements file."""
    pins: dict[str, tuple[str, frozenset[str]]] = {}
    current: str | None = None
    for line in text.splitlines():
        if match := _PIN.match(line):
            current = normalize(match.group(1))
            pins[current] = (match.group(2), frozenset())
        if current is not None and (hashes := _HASH.findall(line)):
            version, known = pins[current]
            pins[current] = (version, known | frozenset(hashes))
        if not line.rstrip().endswith("\\"):
            current = None
    return pins


@dataclass(frozen=True)
class Runtime:
    base_url: str
    packages: list[str]
    files: dict[str, str]  # file name -> sha256
    wheels: list[str]  # pure-Python packages, pinned in requirements.txt


def load_runtime(path: Path) -> Runtime:
    raw = json.loads(path.read_text())
    runtime = Runtime(
        base_url=str(raw["pyodide"]["base_url"]),
        packages=[str(n) for n in raw["pyodide"]["packages"]],
        files={str(k): str(v) for k, v in raw["pyodide"]["files"].items()},
        wheels=[str(n) for n in raw["wheels"]],
    )
    if not runtime.base_url.startswith("https://"):
        raise BuildError("the Pyodide base URL must be https")
    for name, sha in runtime.files.items():
        if not _SHA.fullmatch(sha) or "/" in name:
            raise BuildError(f"bad entry in {path.name}: {name}")
    return runtime


def pyodide_files(runtime: Runtime) -> list[Pinned]:
    return [
        Pinned(runtime.base_url + name, sha, f"runtime/pyodide/{name}")
        for name, sha in sorted(runtime.files.items())
    ]


def wheel_files(
    names: Iterable[str], pins: dict[str, tuple[str, frozenset[str]]], fetch: Fetch
) -> list[Pinned]:
    """Find each pure wheel on PyPI at the pinned version, by a hash requirements.txt allows."""
    found = []
    for raw in names:
        name = normalize(raw)
        if name not in pins:
            raise BuildError(f"{name} is not pinned in requirements.txt")
        version, allowed = pins[name]
        listing = json.loads(fetch(f"https://pypi.org/pypi/{name}/{version}/json"))
        matches = [
            entry
            for entry in listing["urls"]
            if entry["filename"].endswith("-py3-none-any.whl")
            and entry["digests"]["sha256"] in allowed
        ]
        if len(matches) != 1:
            raise BuildError(f"no single pure wheel for {name}=={version} with a pinned hash")
        entry = matches[0]
        found.append(
            Pinned(entry["url"], entry["digests"]["sha256"], f"runtime/{entry['filename']}")
        )
    return found


def fetch_verified(item: Pinned, fetch: Fetch, cache: Path) -> bytes:
    cached = cache / item.sha256
    if cached.is_file():
        data = cached.read_bytes()
        if hashlib.sha256(data).hexdigest() == item.sha256:
            return data
    data = fetch(item.url)
    got = hashlib.sha256(data).hexdigest()
    if got != item.sha256:
        raise BuildError(f"{item.dest}: expected sha256 {item.sha256}, got {got}")
    cache.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(data)
    return data


def https_fetch(url: str) -> bytes:
    if not url.startswith("https://"):
        raise BuildError(f"refusing a non-https download: {url}")
    with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310 - https checked above
        data: bytes = response.read()
    return data


def rewrite_page(text: str, policy: str) -> str:
    """Relative asset paths (the site lives under /linkfall/), the policy and the switch."""
    text = text.replace('href="/"', 'href="./"')
    text = re.sub(r'(\s(?:src|href))="/(?!/)', r'\1="', text)
    charset = '<meta charset="utf-8">'
    if text.count(charset) != 1:
        raise BuildError("a page lacks its charset meta tag")
    policy_tag = f'<meta http-equiv="Content-Security-Policy" content="{policy}">'
    tags = f"{charset}\n  {policy_tag}\n  {BACKEND_META}"
    return text.replace(charset, tags)


def rewrite_css(text: str) -> str:
    return re.sub(r"""url\(\s*(["']?)/(?!/)""", r"url(\1", text)


def rewrite_js(text: str) -> str:
    return re.sub(r"""(["'`])/assets/""", r"\1assets/", text)


def zip_package(package: Path) -> bytes:
    """The linkfall package without the web files, with fixed timestamps so the bytes repeat."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(package.rglob("*")):
            rel = path.relative_to(package.parent)
            skip = rel.parts[1:2] == ("web",) or any(
                p == "__pycache__" or p.startswith(".") for p in rel.parts
            )
            if path.is_file() and not skip and (path.suffix == ".py" or path.name == "py.typed"):
                info = zipfile.ZipInfo(rel.as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, path.read_bytes())
    return buffer.getvalue()


def prepare_out(out: Path) -> None:
    """Replace only a folder this script made, and never the repo or anything above it."""
    resolved = out.resolve()
    if resolved == ROOT or resolved in ROOT.parents or resolved.is_relative_to(ROOT / "src"):
        raise BuildError(f"refusing to build into {out}")
    if resolved.exists():
        if any(resolved.iterdir()) and not (resolved / MARKER).is_file():
            raise BuildError(f"{out} has files this script didn't make; pick an empty folder")
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True)
    (resolved / MARKER).write_text("made by scripts/build_pages.py\n")


def check_dist(out: Path, pinned: Iterable[Pinned]) -> None:
    """What the build test and the deploy both rely on."""
    for path in out.rglob("*"):
        pattern = _ABSOLUTE.get(path.suffix)
        ours = path.is_file() and not path.is_relative_to(out / "runtime")
        if pattern and ours and (hit := pattern.search(path.read_text())):
            raise BuildError(f"absolute path left in {path.relative_to(out)}: {hit.group(0)}")
    for page in PAGES:
        text = (out / page).read_text()
        if BACKEND_META not in text or 'http-equiv="Content-Security-Policy"' not in text:
            raise BuildError(f"{page} lacks the policy or the backend switch")
    for item in pinned:
        if hashlib.sha256((out / item.dest).read_bytes()).hexdigest() != item.sha256:
            raise BuildError(f"{item.dest} does not match its hash")
    manifest = json.loads((out / "runtime" / "manifest.json").read_text())
    for name in [manifest["app"], *manifest["wheels"]]:
        if not (out / "runtime" / name).is_file():
            raise BuildError(f"the manifest names a missing file: {name}")


def build(
    out: Path,
    *,
    fetch: Fetch = https_fetch,
    cache: Path = ROOT / ".cache" / "pages",
    runtime_path: Path = RUNTIME,
    requirements_path: Path = REQUIREMENTS,
) -> list[Pinned]:
    runtime = load_runtime(runtime_path)
    pins = requirement_pins(requirements_path.read_text())
    pure = wheel_files(runtime.wheels, pins, fetch)
    pinned = pyodide_files(runtime) + pure
    payload = {item.dest: fetch_verified(item, fetch, cache) for item in pinned}  # all, then write

    prepare_out(out)
    shutil.copytree(WEB, out, dirs_exist_ok=True, ignore=shutil.ignore_patterns("package.json"))
    policy = meta_policy()
    for page in PAGES:
        (out / page).write_text(rewrite_page((out / page).read_text(), policy))
    for css in out.glob("*.css"):
        css.write_text(rewrite_css(css.read_text()))
    for js in (out / "js").glob("*.js"):
        js.write_text(rewrite_js(js.read_text()))
    (out / ".nojekyll").write_text("")
    for dest, data in payload.items():
        (out / dest).parent.mkdir(parents=True, exist_ok=True)
        (out / dest).write_bytes(data)
    (out / "runtime" / "linkfall.zip").write_bytes(zip_package(PACKAGE))
    manifest = {
        "packages": runtime.packages,
        "wheels": sorted(Path(item.dest).name for item in pure),
        "app": "linkfall.zip",
    }
    (out / "runtime" / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    check_dist(out, pinned)
    return pinned


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--out", type=Path, default=ROOT / "dist")
    parser.add_argument("--cache", type=Path, default=ROOT / ".cache" / "pages")
    args = parser.parse_args(argv)
    try:
        pinned = build(args.out, cache=args.cache)
    except BuildError as exc:
        sys.stderr.write(f"build_pages: {exc}\n")
        return 1
    sys.stdout.write(f"built {args.out} with {len(pinned)} pinned files\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
