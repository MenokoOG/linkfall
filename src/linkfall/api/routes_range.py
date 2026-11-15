"""Training range routes: list targets, start a run, read it, recheck it, download the report.

Everything a run shows comes from its log rows through the recheck, so the page and the report
never disagree with the record (ADR 0009). Protected values leave only inside a reply that
stated them.
"""

import asyncio
from dataclasses import asdict, dataclass
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from linkfall.api.routes_run import run_id_of
from linkfall.api.schemas import StartRange
from linkfall.api.security import require_same_origin
from linkfall.range.contract import ProbeResult
from linkfall.range.judge import summarize
from linkfall.range.probes import PROBES
from linkfall.range.recheck import Recheck, recheck
from linkfall.range.report import report_markdown
from linkfall.range.rows import RowKind, line_payload
from linkfall.range.runner import RangeBusyError, RangeService, TargetUnavailableError
from linkfall.range.store import RangeHeader, RangeRunNotFoundError, RangeStore
from linkfall.range.vault import ITEMS

router = APIRouter(prefix="/api/range")


@dataclass(frozen=True, slots=True)
class Logged:
    """One range run as its log holds it right now."""

    header: RangeHeader
    ended: bool
    check: Recheck


def service_of(request: Request) -> RangeService:
    service: RangeService = request.app.state.range
    return service


def _read(store: RangeStore, run_id: str) -> Logged:
    header = store.get_run(run_id)
    rows = store.read_rows(run_id)
    return Logged(header, any(row.kind == RowKind.END for row in rows), recheck(rows))


async def logged_run(request: Request, run_id: str = Depends(run_id_of)) -> Logged:
    store: RangeStore = request.app.state.range_store
    try:
        return await asyncio.to_thread(_read, store, run_id)
    except RangeRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail="no such run") from exc


type LoggedRun = Annotated[Logged, Depends(logged_run)]


def _probe_json(result: ProbeResult) -> dict[str, object]:
    return {
        "id": result.probe.id,
        "verdict": result.verdict.value,
        "lines": [line_payload(line) for line in result.lines],
    }


@router.get("")
async def describe_range(request: Request) -> dict[str, object]:
    service = service_of(request)
    return {
        "targets": [asdict(target) for target in await service.targets()],
        "probes": [
            {"id": p.id, "technique": p.technique, "rule": p.rule, "kind": p.kind.value}
            for p in PROBES
        ],
        "items": [{"id": item.id, "label": item.label} for item in ITEMS],
        "busy": service.busy,
    }


@router.post("/runs", status_code=202, dependencies=[Depends(require_same_origin)])
async def start_run(body: StartRange, request: Request) -> dict[str, object]:
    try:
        run_id = await service_of(request).start(body.target)
    except RangeBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except TargetUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"run_id": run_id, "status": "running"}


@router.get("/runs/{run_id}")
async def get_run(request: Request, run: LoggedRun) -> dict[str, object]:
    service = service_of(request)
    run_id = run.header.run_id
    return {
        "run_id": run_id,
        "target": run.header.target,
        "kind": run.header.kind,
        "created_at": run.header.created_at,
        "status": service.status(run_id, run.ended).value,
        "current_probe": service.current_probe(run_id),
        "error": service.error(run_id),
        "log_check": run.check.status.value,
        "probes": [_probe_json(result) for result in run.check.results],
        "summary": asdict(summarize(run.check.results)),
    }


@router.post("/runs/{run_id}/recheck", dependencies=[Depends(require_same_origin)])
async def recheck_run(run: LoggedRun) -> dict[str, object]:
    """Judge the logged lines again and compare. No model is called."""
    return {
        "status": run.check.status.value,
        "fingerprint": run.check.fingerprint,
        "row_id": run.check.row_id,
        "reason": run.check.reason,
        "probes": len(run.check.results),
    }


@router.get("/runs/{run_id}/report.md")
async def report(run: LoggedRun) -> Response:
    """A download, never a page: model text in it is not rendered by this origin."""
    name = f"linkfall-range-{run.header.run_id}.md"  # the id passed the run id pattern
    return Response(
        report_markdown(run.header, run.check.results, run.check),
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
