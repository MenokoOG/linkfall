import hashlib
import importlib.util
import json
import re
import sys
import zipfile
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "build_pages", ROOT / "scripts" / "build_pages.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bp = _load()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


FILES = {"pyodide.mjs": b"export const loadPyodide = 1;", "pydantic-2-py3-none-any.whl": b"pyd"}
WHEEL = b"fastapi wheel bytes"


@pytest.fixture
def fake(tmp_path: Path) -> dict[str, object]:
    runtime = {
        "note": "test",
        "pyodide": {
            "version": "0",
            "base_url": "https://cdn.test/full/",
            "packages": ["pydantic"],
            "files": {name: sha(data) for name, data in FILES.items()},
        },
        "wheels": ["FastAPI"],
    }
    runtime_path = tmp_path / "runtime.json"
    runtime_path.write_text(json.dumps(runtime))
    requirements = tmp_path / "requirements.txt"
    requirements.write_text(
        f"fastapi==1.0 \\\n    --hash=sha256:{'0' * 64} \\\n    --hash=sha256:{sha(WHEEL)}\n"
        "    # via -r requirements.in\nidna==3.0 \\\n    --hash=sha256:" + "1" * 64 + "\n"
    )
    listing = {
        "urls": [
            {
                "filename": "fastapi-1.0.tar.gz",
                "url": "https://files.test/fastapi.tgz",
                "digests": {"sha256": sha(WHEEL)},
            },
            {
                "filename": "fastapi-1.0-py3-none-any.whl",
                "url": "https://files.test/fastapi.whl",
                "digests": {"sha256": sha(WHEEL)},
            },
        ]
    }
    served = {
        "https://pypi.org/pypi/fastapi/1.0/json": json.dumps(listing).encode(),
        "https://files.test/fastapi.whl": WHEEL,
        **{f"https://cdn.test/full/{name}": data for name, data in FILES.items()},
    }
    calls: list[str] = []

    def fetch(url: str) -> bytes:
        calls.append(url)
        return served[url]

    return {
        "fetch": fetch,
        "served": served,
        "calls": calls,
        "kwargs": {
            "cache": tmp_path / "cache",
            "runtime_path": runtime_path,
            "requirements_path": requirements,
        },
    }


def run_build(fake: dict[str, object], out: Path) -> list[object]:
    kwargs = fake["kwargs"]
    assert isinstance(kwargs, dict)
    pinned: list[object] = bp.build(out, fetch=fake["fetch"], **kwargs)
    return pinned


def test_the_build_lays_out_what_local_backend_reads(
    fake: dict[str, object], tmp_path: Path
) -> None:
    out = tmp_path / "dist"
    run_build(fake, out)
    runtime = out / "runtime"
    assert (runtime / "pyodide" / "pyodide.mjs").read_bytes() == FILES["pyodide.mjs"]
    assert (runtime / "pyodide" / "pydantic-2-py3-none-any.whl").is_file()
    assert (runtime / "fastapi-1.0-py3-none-any.whl").read_bytes() == WHEEL
    manifest = json.loads((runtime / "manifest.json").read_text())
    assert manifest == {
        "packages": ["pydantic"],
        "wheels": ["fastapi-1.0-py3-none-any.whl"],
        "app": "linkfall.zip",
    }
    # The same rules as checkManifest() in local-backend.js: file names only.
    for name in [manifest["app"], *manifest["wheels"], *manifest["packages"]]:
        assert re.fullmatch(r"[A-Za-z0-9_.+-]+", name)
    assert (out / ".nojekyll").is_file()
    assert not (out / "js" / "package.json").exists()


def test_pages_get_relative_paths_the_policy_and_the_switch(
    fake: dict[str, object], tmp_path: Path
) -> None:
    out = tmp_path / "dist"
    run_build(fake, out)
    for page in ("index.html", "range.html"):
        text = (out / page).read_text()
        assert '<meta name="linkfall-backend" content="browser">' in text
        assert f'content="{bp.meta_policy()}"' in text
        assert not re.search(r"""\s(?:src|href)=["']/""", text)
    assert 'href="./"' in (out / "range.html").read_text()
    assert "url(assets/" in (out / "scene.css").read_text()
    assert "`assets/avatar-" in (out / "js" / "cards-view.js").read_text()
    assert (
        "'/api/" in (out / "js" / "api.js").read_text()
        or "`/api/" in (out / "js" / "api.js").read_text()
    )  # API paths are virtual in the browser build; they stay as they are


def test_the_meta_policy_is_the_server_policy_fitted_to_a_meta_tag() -> None:
    policy = bp.meta_policy()
    assert "frame-ancestors" not in policy
    assert "script-src 'self' 'wasm-unsafe-eval'" in policy
    assert "default-src 'self'" in policy
    assert "object-src 'none'" in policy


def test_the_app_zip_has_the_package_without_web_or_caches(
    fake: dict[str, object], tmp_path: Path
) -> None:
    run_build(fake, tmp_path / "a")
    run_build(fake, tmp_path / "b")
    first = (tmp_path / "a" / "runtime" / "linkfall.zip").read_bytes()
    assert first == (tmp_path / "b" / "runtime" / "linkfall.zip").read_bytes()  # repeatable
    names = zipfile.ZipFile(tmp_path / "a" / "runtime" / "linkfall.zip").namelist()
    assert "linkfall/browser/bridge.py" in names
    assert "linkfall/py.typed" in names
    assert not [n for n in names if "/web/" in n or "__pycache__" in n or "/." in n]


def test_a_hash_mismatch_stops_the_build_before_anything_is_written(
    fake: dict[str, object], tmp_path: Path
) -> None:
    served = fake["served"]
    assert isinstance(served, dict)
    served["https://cdn.test/full/pyodide.mjs"] = b"tampered"
    out = tmp_path / "dist"
    with pytest.raises(bp.BuildError, match=r"runtime/pyodide/pyodide\.mjs: expected sha256"):
        run_build(fake, out)
    assert not out.exists()


def test_a_wheel_must_match_a_pinned_hash(fake: dict[str, object], tmp_path: Path) -> None:
    kwargs = fake["kwargs"]
    assert isinstance(kwargs, dict)
    kwargs["requirements_path"].write_text("fastapi==1.0 \\\n    --hash=sha256:" + "2" * 64 + "\n")
    with pytest.raises(bp.BuildError, match="no single pure wheel"):
        run_build(fake, tmp_path / "dist")
    kwargs["requirements_path"].write_text("idna==3.0\n")
    with pytest.raises(bp.BuildError, match="not pinned"):
        run_build(fake, tmp_path / "dist")


def test_the_cache_is_used_and_checked(fake: dict[str, object], tmp_path: Path) -> None:
    run_build(fake, tmp_path / "a")
    calls = fake["calls"]
    assert isinstance(calls, list)
    calls.clear()
    run_build(fake, tmp_path / "b")
    assert calls == ["https://pypi.org/pypi/fastapi/1.0/json"]  # files came from the cache
    kwargs = fake["kwargs"]
    assert isinstance(kwargs, dict)
    (kwargs["cache"] / sha(WHEEL)).write_bytes(b"rotten")
    run_build(fake, tmp_path / "c")
    assert "https://files.test/fastapi.whl" in calls  # a bad cache entry is fetched again


def test_the_output_folder_is_guarded(fake: dict[str, object], tmp_path: Path) -> None:
    for unsafe in (ROOT, ROOT.parent, ROOT / "src" / "x"):
        with pytest.raises(bp.BuildError, match="refusing"):
            run_build(fake, unsafe)
    someone_elses = tmp_path / "mine"
    someone_elses.mkdir()
    (someone_elses / "notes.txt").write_text("keep")
    with pytest.raises(bp.BuildError, match="didn't make"):
        run_build(fake, someone_elses)
    assert (someone_elses / "notes.txt").read_text() == "keep"
    out = tmp_path / "dist"
    run_build(fake, out)
    (out / "stale.txt").write_text("old")
    run_build(fake, out)  # a folder it made is replaced
    assert not (out / "stale.txt").exists()


def test_check_dist_catches_an_absolute_path_and_a_changed_file(
    fake: dict[str, object], tmp_path: Path
) -> None:
    out = tmp_path / "dist"
    pinned = run_build(fake, out)
    js = out / "js" / "zones.js"
    original = js.read_text()
    js.write_text(original + "\nconst x = '/assets/x.svg';\n")
    with pytest.raises(bp.BuildError, match=r"absolute path left in js/zones\.js"):
        bp.check_dist(out, pinned)
    js.write_text(original)
    (out / "runtime" / "fastapi-1.0-py3-none-any.whl").write_bytes(b"swapped")
    with pytest.raises(bp.BuildError, match="does not match its hash"):
        bp.check_dist(out, pinned)


def test_only_https_downloads() -> None:
    with pytest.raises(bp.BuildError, match="non-https"):
        bp.https_fetch("http://example.test/x")


def test_the_committed_runtime_list_is_well_formed_and_pinned() -> None:
    runtime = bp.load_runtime(ROOT / "pages" / "runtime.json")
    assert runtime.base_url.startswith("https://")
    assert {"pyodide.mjs", "pyodide.asm.mjs", "pyodide.asm.wasm", "python_stdlib.zip"} <= set(
        runtime.files
    )
    assert "pyodide-lock.json" in runtime.files  # Pyodide checks its packages against it
    pins = bp.requirement_pins((ROOT / "requirements.txt").read_text())
    for name in runtime.wheels:
        version, hashes = pins[bp.normalize(name)]
        assert version
        assert hashes, name
    assert bp.normalize("pydantic") not in {bp.normalize(n) for n in runtime.wheels}


def test_requirement_pins_reads_a_hashed_file() -> None:
    text = "a-b==1.2 \\\n    --hash=sha256:" + "a" * 64 + " \\\n    --hash=sha256:" + "b" * 64
    text += "\n    # via x\nc==3\n"
    pins = bp.requirement_pins(text)
    assert pins["a-b"] == ("1.2", frozenset({"a" * 64, "b" * 64}))
    assert pins["c"] == ("3", frozenset())


def test_the_pyodide_test_wheels_are_hash_pinned_in_the_dev_lockfile() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        spec = importlib.util.spec_from_file_location(
            "fetch_test_wheels", ROOT / "scripts" / "fetch_test_wheels.py"
        )
        assert spec is not None
        assert spec.loader is not None
        ftw = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ftw)
    finally:
        sys.path.remove(str(ROOT / "scripts"))
    pins = bp.requirement_pins((ROOT / "requirements-dev.txt").read_text())
    for name in ftw.TEST_WHEELS:
        assert pins[bp.normalize(name)][1], name
