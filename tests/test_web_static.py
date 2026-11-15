"""The console files, served by the API app: right types, headers, and no way out of the folder."""

from pathlib import Path

from api_support import make_app, run
from asgi import Client

WEB = Path(__file__).resolve().parent.parent / "src" / "linkfall" / "web"
SECURITY = (
    "content-security-policy",
    "x-content-type-options",
    "referrer-policy",
    "x-frame-options",
)


def test_the_console_page_is_served_at_the_root() -> None:
    async def go() -> None:
        response = await Client(make_app()).get("/")
        assert response.status == 200
        assert response.headers["content-type"] == "text/html; charset=utf-8"
        assert "<title>LINKFALL console</title>" in response.text
        for name in SECURITY:
            assert name in response.headers

    run(go)


def test_files_have_the_right_content_type_with_a_charset_for_text() -> None:
    async def go() -> None:
        client = Client(make_app())
        expected = {
            "/styles.css": "text/css; charset=utf-8",
            "/scene.css": "text/css; charset=utf-8",
            "/assets/scene-cinder-ward.svg": "image/svg+xml",
            "/js/main.js": "text/javascript; charset=utf-8",
            "/assets/mark.svg": "image/svg+xml",
        }
        for path, content_type in expected.items():
            response = await client.get(path)
            assert response.status == 200, path
            assert response.headers["content-type"] == content_type, path

    run(go)


def test_every_shipped_file_is_served() -> None:
    async def go() -> None:
        client = Client(make_app())
        for file in WEB.rglob("*"):
            if file.is_file():
                response = await client.get("/" + file.relative_to(WEB).as_posix())
                assert response.status == 200, file
                assert response.body == file.read_bytes(), file

    run(go)


def test_only_one_non_script_file_sits_in_the_js_folder() -> None:
    others = [p.name for p in (WEB / "js").iterdir() if p.suffix != ".js"]
    assert others == ["package.json"]  # it only tells Node's test runner these are ES modules


def test_paths_cannot_climb_out_of_the_web_folder() -> None:
    async def go() -> None:
        client = Client(make_app())
        for path in (
            "/../../pyproject.toml",
            "/js/../../../../pyproject.toml",
            "/%2e%2e/%2e%2e/pyproject.toml",
            "/js/%2e%2e%2f%2e%2e%2fpyproject.toml",
            "/..%2f..%2fpyproject.toml",
        ):
            response = await client.get(path)
            assert response.status in {400, 404}, (path, response.status)
            assert "linkfall" not in response.text.lower() or response.status == 404

    run(go)


def test_the_api_still_wins_over_the_static_files() -> None:
    async def go() -> None:
        client = Client(make_app())
        assert (await client.get("/api/health")).json()["status"] == "ok"
        assert (await client.get("/api/missing")).status == 404
        assert (await client.post("/", {})).status in {403, 405}

    run(go)
