"""Alarm events endpoints."""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_alarm_manager
from app.middleware.tenant_context import TenantContext, get_tenant_context, require_role
from app.models import AlarmEvent
from app.schemas import AlarmEventResponse

router = APIRouter(prefix="/alarms", tags=["alarms"])


@router.get("", response_model=list[AlarmEventResponse])
async def list_alarms(
    event_type: str | None = None,
    device_id: str | None = None,
    limit: int = 100,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    query = select(AlarmEvent).where(AlarmEvent.org_id == ctx.org_id)
    if event_type:
        query = query.where(AlarmEvent.event_type == event_type)
    if device_id:
        query = query.where(AlarmEvent.device_id == device_id)
    if not ctx.is_admin:
        query = query.where(AlarmEvent.group_id.in_(ctx.group_ids))
    query = query.order_by(AlarmEvent.created_at.desc()).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/active")
async def get_active_alarms(
    ctx: TenantContext = Depends(get_tenant_context),
    alarm_manager=Depends(get_alarm_manager),
):
    return alarm_manager.get_active_alarms(ctx.org_id)


@router.post("/{alarm_id}/ack")
async def acknowledge_alarm(
    alarm_id: str,
    ctx: TenantContext = Depends(require_role("operator")),
    db: AsyncSession = Depends(get_db),
):
    query = select(AlarmEvent).where(AlarmEvent.id == alarm_id, AlarmEvent.org_id == ctx.org_id)
    result = await db.execute(query)
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Alarm event not found")
    event.acknowledged = True
    event.acknowledged_by = ctx.user_id
    await db.commit()
    return {"status": "acknowledged"}
