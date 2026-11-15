"""Build the FastAPI app: routes, middleware, error shapes, static files."""

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.staticfiles import StaticFiles

from linkfall.api import routes_pilot, routes_range, routes_run
from linkfall.api.config import ApiConfig
from linkfall.api.registry import HealthyModelClient, Registry
from linkfall.api.requestlog import ErrorBoundaryMiddleware, RequestContextMiddleware
from linkfall.api.security import BodyLimitMiddleware, SecurityHeadersMiddleware
from linkfall.eventlog.store import EventStore, RunNotFoundError
from linkfall.policy.zones import PolicyError
from linkfall.range.runner import RangeService
from linkfall.range.store import RangeStore
from linkfall.supervisor.http_client import HttpModelClient
from linkfall.supervisor.run import SupervisorError

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
_MAX_FIELD_NAME = 40  # field names in an error come from the sender, so they are cut


def _error(status: int, message: str, **extra: object) -> JSONResponse:
    return JSONResponse({"error": message, **extra}, status_code=status)


async def _http_error(_request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, StarletteHTTPException):
        raise exc
    return _error(exc.status_code, str(exc.detail))


async def _invalid(_request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        raise exc
    fields = [
        {
            "field": ".".join(str(p) for p in e["loc"] if p != "body")[:_MAX_FIELD_NAME],
            "problem": e["msg"],
        }
        for e in exc.errors()
    ]
    return _error(422, "invalid request", fields=fields)


def create_app(
    config: ApiConfig,
    *,
    store: EventStore | None = None,
    model_client: HealthyModelClient | None = None,
    range_store: RangeStore | None = None,
) -> FastAPI:
    app = FastAPI(
        title="LINKFALL", docs_url=None, redoc_url=None, openapi_url=None
    )  # no interactive docs: less surface
    event_store = store or EventStore(config.db_path)
    range_log = range_store or RangeStore(config.range_db_path)
    # One model client for the mission crew and the range target, so there is one seam to it.
    client: HealthyModelClient | None = model_client or (
        HttpModelClient(config.model_url) if config.model_url else None
    )
    app.state.config = config
    app.state.store = event_store
    app.state.registry = Registry(config, event_store, client)
    app.state.range_store = range_log
    app.state.range = RangeService(range_log, client, config.budgets)

    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(HTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _invalid)
    app.add_exception_handler(
        SupervisorError, lambda _r, e: _error(409, str(e))
    )  # a request the run can't take now
    app.add_exception_handler(PolicyError, lambda _r, e: _error(422, str(e)))
    app.add_exception_handler(RunNotFoundError, lambda _r, _e: _error(404, "no such run"))

    app.include_router(routes_run.router)
    app.include_router(routes_pilot.router)
    app.include_router(routes_range.router)
    if WEB_DIR.is_dir():
        app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")

    # The last one added is the outermost, so it runs first: request id and log, then security
    # headers (so even a rejected Host gets them), then the host check, then the body limit.
    app.add_middleware(ErrorBoundaryMiddleware)
    app.add_middleware(BodyLimitMiddleware, max_bytes=config.max_body_bytes)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(config.allowed_hosts))
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestContextMiddleware)
    return app
