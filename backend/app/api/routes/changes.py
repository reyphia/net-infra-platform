from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_change_plan_service, get_db
from app.api.schemas import ChangeApplyRequest, ChangePlanCreate, ChangePlanOut
from app.changes.service import ChangePlanError, ChangePlanService
from app.db.models import ChangeExecution, ChangePlan

router = APIRouter(prefix="/change-plans", tags=["change-management"])


@router.post("", response_model=ChangePlanOut, status_code=201)
async def create_change_plan(
    body: ChangePlanCreate, service: ChangePlanService = Depends(get_change_plan_service)
) -> ChangePlan:
    try:
        return await service.create_plan(
            name=body.name,
            operator=body.operator,
            proposed_config=body.proposed_config,
            device_ids=body.device_ids,
            save_after_apply=body.save_after_apply,
        )
    except ChangePlanError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("", response_model=list[ChangePlanOut])
async def list_change_plans(session: AsyncSession = Depends(get_db)) -> list[ChangePlan]:
    result = await session.execute(select(ChangePlan).order_by(ChangePlan.created_at.desc()))
    return list(result.scalars().all())


@router.get("/{plan_id}", response_model=ChangePlanOut)
async def get_change_plan(plan_id: str, session: AsyncSession = Depends(get_db)) -> ChangePlan:
    plan = await session.get(ChangePlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"No change plan with id {plan_id}")
    return plan


@router.get("/{plan_id}/devices")
async def get_plan_devices(plan_id: str, service: ChangePlanService = Depends(get_change_plan_service)) -> list[dict]:
    pairs = await service._plan_devices(plan_id)  # noqa: SLF001 - internal helper reused for a read-only listing
    return [
        {
            "device_id": device.id,
            "hostname": device.hostname,
            "management_ip": device.management_ip,
            "eligible": cpd.eligible,
            "ineligibility_reason": cpd.ineligibility_reason,
        }
        for cpd, device in pairs
    ]


@router.post("/{plan_id}/validate", response_model=ChangePlanOut)
async def validate_change_plan(plan_id: str, service: ChangePlanService = Depends(get_change_plan_service)) -> ChangePlan:
    try:
        return await service.validate_plan(plan_id)
    except ChangePlanError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{plan_id}/preview", response_model=ChangePlanOut)
async def preview_change_plan(plan_id: str, service: ChangePlanService = Depends(get_change_plan_service)) -> ChangePlan:
    try:
        return await service.preview_plan(plan_id)
    except ChangePlanError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{plan_id}/apply", response_model=ChangePlanOut)
async def apply_change_plan(
    plan_id: str, body: ChangeApplyRequest, service: ChangePlanService = Depends(get_change_plan_service)
) -> ChangePlan:
    """Requires the caller to re-supply `confirmed_by` -- this IS the explicit
    confirmation step; there is no separate hidden 'confirm' endpoint that
    could be triggered accidentally."""
    try:
        return await service.apply_plan(plan_id, confirmed_by=body.confirmed_by)
    except ChangePlanError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{plan_id}/executions")
async def get_plan_executions(plan_id: str, session: AsyncSession = Depends(get_db)) -> list[dict]:
    result = await session.execute(select(ChangeExecution).where(ChangeExecution.plan_id == plan_id))
    executions = result.scalars().all()
    return [
        {
            "id": e.id,
            "device_id": e.device_id,
            "apply_success": e.apply_success,
            "apply_error": e.apply_error,
            "verified": e.verified,
            "rollback_status": e.rollback_status,
            "rollback_detail": e.rollback_detail,
        }
        for e in executions
    ]


@router.post("/executions/{execution_id}/rollback")
async def rollback_execution(
    execution_id: str, operator: str, service: ChangePlanService = Depends(get_change_plan_service)
) -> dict:
    try:
        execution = await service.rollback_execution(execution_id, operator=operator)
    except ChangePlanError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "id": execution.id,
        "rollback_status": execution.rollback_status,
        "rollback_detail": execution.rollback_detail,
    }
