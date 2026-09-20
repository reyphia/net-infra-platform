from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.schemas import DiscoveryJobCreate, DiscoveryJobOut
from app.db.models import DiscoveryJob, DiscoveryJobStatus
from app.db.session import SessionLocal
from app.discovery.engine import DiscoveryConfig, run_discovery
from app.discovery.scope import DiscoveryScope, InvalidScopeError

router = APIRouter(prefix="/discovery", tags=["discovery"])


@router.post("", response_model=DiscoveryJobOut, status_code=202)
async def start_discovery(
    body: DiscoveryJobCreate, background_tasks: BackgroundTasks, session: AsyncSession = Depends(get_db)
) -> DiscoveryJob:
    try:
        DiscoveryScope(body.scope_cidrs)  # validate scope up front; re-expanded inside the background job
    except InvalidScopeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    config = DiscoveryConfig(
        timeout_seconds=body.timeout_seconds,
        max_concurrency=body.max_concurrency,
        retry_count=body.retry_count,
        snmp_community=body.snmp_community,
        snmp_port=body.snmp_port,
        enable_snmp=body.enable_snmp,
        enable_lldp_cdp=body.enable_lldp_cdp,
    )

    job = DiscoveryJob(
        scope_cidrs=body.scope_cidrs,
        status=DiscoveryJobStatus.PENDING.value,
        config={
            "timeout_seconds": body.timeout_seconds,
            "max_concurrency": body.max_concurrency,
            "retry_count": body.retry_count,
            "snmp_port": body.snmp_port,
            "enable_snmp": body.enable_snmp,
            "enable_lldp_cdp": body.enable_lldp_cdp,
            # snmp_community intentionally excluded -- never persist secrets in job config
        },
        counts_by_type={},
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)

    background_tasks.add_task(_run_job_in_background, job.id, body.scope_cidrs, config)
    return job


async def _run_job_in_background(job_id: str, scope_cidrs: list[str], config: DiscoveryConfig) -> None:
    """Runs in its own DB session since the request's session is closed by
    the time a BackgroundTask executes."""
    async with SessionLocal() as session:
        job = await session.get(DiscoveryJob, job_id)
        if job is None:
            return
        try:
            scope = DiscoveryScope(scope_cidrs)
            await run_discovery(session, job, scope, config)
        except Exception as exc:  # noqa: BLE001 - must not crash the background task silently
            job.status = DiscoveryJobStatus.FAILED.value
            job.error = str(exc)
            await session.commit()


@router.get("", response_model=list[DiscoveryJobOut])
async def list_discovery_jobs(session: AsyncSession = Depends(get_db)) -> list[DiscoveryJob]:
    result = await session.execute(select(DiscoveryJob).order_by(DiscoveryJob.created_at.desc()))
    return list(result.scalars().all())


@router.get("/{job_id}", response_model=DiscoveryJobOut)
async def get_discovery_job(job_id: str, session: AsyncSession = Depends(get_db)) -> DiscoveryJob:
    job = await session.get(DiscoveryJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"No discovery job with id {job_id}")
    return job


@router.post("/{job_id}/cancel", response_model=DiscoveryJobOut)
async def cancel_discovery_job(job_id: str, session: AsyncSession = Depends(get_db)) -> DiscoveryJob:
    job = await session.get(DiscoveryJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"No discovery job with id {job_id}")
    if job.status != DiscoveryJobStatus.RUNNING.value:
        raise HTTPException(status_code=409, detail=f"Job is not running (status={job.status}); nothing to cancel.")
    # NOT IMPLEMENTED: cooperative cancellation of an in-flight background
    # task by id (would require tracking asyncio.Task handles per job).
    # Marking the DB row lets the UI reflect intent; in-flight probes for
    # the current batch will still complete.
    job.status = DiscoveryJobStatus.CANCELLED.value
    await session.commit()
    await session.refresh(job)
    return job
