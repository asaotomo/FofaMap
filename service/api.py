"""FastAPI surface for FofaMap."""

from __future__ import annotations

import datetime as dt
import os
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from config import settings
from core.agent import FofaAgent
from core.client import FofaClient
from core.exporter import export_pages
from core.fields import field_catalog
from core.models import ExportRequest, FofaError, SearchPage, SearchRequest
from core.scanner import NucleiScanner
from core.scans import ScanApproval, ScanPlanRequest
from core.version import VERSION
from providers.registry import ProviderRegistry, ProviderRouter
from service.auth import require_service_auth
from service.paths import database_url, output_root
from service.store import JobStore

app = FastAPI(title="FofaMap API", version=VERSION, description="只读 FOFA 检索、导出与厂商无关智能体接口")
store = JobStore(database_url())
store.purge_expired(Path(settings.system.output_dir))


def _not_found(exc: KeyError) -> HTTPException:
    return HTTPException(status_code=404, detail=f"job not found: {exc.args[0]}")


@app.exception_handler(FofaError)
async def fofa_error_handler(_request, exc: FofaError):
    from fastapi.responses import JSONResponse

    status = 429 if exc.code.value == "rate_limited" else 401 if exc.code.value == "auth_failed" else 400
    return JSONResponse(status_code=status, content={"error": exc.as_dict()})


@app.get("/v1/account", dependencies=[Depends(require_service_auth)])
async def account():
    async with FofaClient() as client:
        return await client.account()


@app.get("/v1/fields", dependencies=[Depends(require_service_auth)])
async def fields():
    return field_catalog()


@app.post("/v1/search", response_model=SearchPage, dependencies=[Depends(require_service_auth)])
async def search(request: SearchRequest):
    async with FofaClient() as client:
        return await client.search_page(request.model_copy(update={"cursor": None, "continuous": False}))


@app.post("/v1/search/next", response_model=SearchPage, dependencies=[Depends(require_service_auth)])
async def search_next(request: SearchRequest):
    if not request.cursor:
        raise HTTPException(status_code=422, detail="cursor is required")
    async with FofaClient() as client:
        return await client.search_page(request.model_copy(update={"continuous": True}))


@app.get("/v1/hosts/{host}", dependencies=[Depends(require_service_auth)])
async def host_profile(host: str, detail: bool = True):
    async with FofaClient() as client:
        return await client.host_profile(host, detail=detail)


class StatsRequest(BaseModel):
    query: str
    fields: list[str]
    size: int = 5


@app.post("/v1/stats", dependencies=[Depends(require_service_auth)])
async def stats(request: StatsRequest):
    async with FofaClient() as client:
        return await client.stats(request.query, request.fields, size=request.size)


@app.get("/v1/syntax", dependencies=[Depends(require_service_auth)])
async def syntax():
    from core.syntax import syntax_catalog

    return syntax_catalog()


@app.get("/v1/rules", dependencies=[Depends(require_service_auth)])
async def rules(keyword: str = ""):
    from core.rules import rules_catalog

    return rules_catalog(keyword)


async def _run_export(job_id: str, request: ExportRequest) -> None:
    store.update(job_id, status="running")
    try:
        root = output_root()
        filename = Path(request.filename or f"{job_id}.{request.format}").name
        destination = root / filename
        async with FofaClient() as client:
            path, count = await export_pages(client.iter_search(request.search), destination, request.format)
        store.update(job_id, status="completed", result={"records": count}, artifact_path=str(path.resolve()))
    except FofaError as exc:
        store.update(job_id, status="failed", error=exc.as_dict())
    except Exception as exc:
        store.update(job_id, status="failed", error={"code": "export_error", "message": str(exc)})


@app.post("/v1/exports", dependencies=[Depends(require_service_auth)])
async def create_export(request: ExportRequest, background: BackgroundTasks):
    expires = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=settings.system.artifact_retention_days)
    job = store.create("export", request.model_dump(mode="json"), expires_at=expires.isoformat())
    background.add_task(_run_export, job["id"], request)
    return job


@app.get("/v1/jobs/{job_id}", dependencies=[Depends(require_service_auth)])
async def job_status(job_id: str):
    try:
        return store.get(job_id)
    except KeyError as exc:
        raise _not_found(exc) from exc


@app.get("/v1/artifacts/{job_id}", dependencies=[Depends(require_service_auth)])
async def artifact(job_id: str):
    try:
        job = store.get(job_id)
    except KeyError as exc:
        raise _not_found(exc) from exc
    path = Path(job.get("artifact_path") or "")
    root = output_root()
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(root)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="artifact not found") from exc
    return FileResponse(resolved, filename=resolved.name)


class AgentRequest(BaseModel):
    intent: str
    max_records: int = 1000
    max_pages: int = 10


@app.post("/v1/agent/runs", dependencies=[Depends(require_service_auth)])
async def agent_run(request: AgentRequest):
    job = store.create("agent", request.model_dump(mode="json"))
    store.update(job["id"], status="running")
    registry = ProviderRegistry(settings, execution_mode="service")
    router = ProviderRouter(registry)
    async with FofaClient() as client:
        result = await FofaAgent(client, router).run(request.intent, max_records=request.max_records, max_pages=request.max_pages)
    await registry.aclose()
    status = "completed" if result.error is None else "failed"
    store.update(job["id"], status=status, result=result.model_dump(mode="json"), error=result.error)
    return {"job_id": job["id"], "run": result}


@app.post("/v1/scans/plans", dependencies=[Depends(require_service_auth)])
async def scan_plan(request: ScanPlanRequest):
    if os.getenv("FOFAMAP_ENABLE_SCANNING", "false").lower() != "true":
        raise HTTPException(status_code=403, detail="active scanning is disabled")
    approval = ScanApproval(store, allow_private=settings.system.allow_private_network)
    try:
        job, token = approval.create(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"plan": job, "approval_token": token}


class ScanExecuteRequest(BaseModel):
    approval_token: str
    install_if_missing: bool = False


@app.post("/v1/scans/{plan_id}/execute", dependencies=[Depends(require_service_auth)])
async def scan_execute(plan_id: str, request: ScanExecuteRequest):
    if os.getenv("FOFAMAP_ENABLE_SCANNING", "false").lower() != "true":
        raise HTTPException(status_code=403, detail="active scanning is disabled")
    approval = ScanApproval(store, allow_private=settings.system.allow_private_network)
    try:
        approval.verify(plan_id, request.approval_token)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    from core.nuclei_install import ensure_installed, needs_setup

    if needs_setup(NucleiScanner().executable):
        if not request.install_if_missing:
            raise HTTPException(status_code=409, detail="Nuclei needs installation. Ask the user for consent first; "
                                "retry with install_if_missing=true only after consent, or install it manually.")
        await ensure_installed(consent=True)
    job = approval.consume(plan_id, request.approval_token)
    store.update(plan_id, status="running")
    try:
        scan = await NucleiScanner().run_plan(
            ScanPlanRequest.model_validate(job["payload"]),
            output_root() / f"scan-{plan_id}",
        )
        return store.update(
            plan_id,
            status="completed",
            artifact_path=str(scan.artifact.resolve()),
            result=scan.to_job_payload(),
        )
    except Exception as exc:
        store.update(plan_id, status="failed", error={"code": "scan_error", "message": str(exc)})
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def main() -> None:
    import uvicorn

    uvicorn.run("service.api:app", host=os.getenv("FOFAMAP_BIND_HOST", "127.0.0.1"), port=int(os.getenv("FOFAMAP_PORT", "8000")))


if __name__ == "__main__":
    main()
