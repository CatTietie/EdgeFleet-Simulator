"""Device management endpoints."""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.middleware.tenant_context import TenantContext, get_tenant_context, require_role
from app.models import Device
from app.schemas import DeviceCreate, DeviceResponse

router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("", response_model=list[DeviceResponse])
async def list_devices(
    group_id: str | None = None,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    query = select(Device).where(Device.org_id == ctx.org_id)
    if not ctx.is_admin:
        query = query.where(Device.group_id.in_(ctx.group_ids))
    if group_id:
        query = query.where(Device.group_id == group_id)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{device_id}", response_model=DeviceResponse)
async def get_device(
    device_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    query = select(Device).where(Device.id == device_id, Device.org_id == ctx.org_id)
    if not ctx.is_admin:
        query = query.where(Device.group_id.in_(ctx.group_ids))
    result = await db.execute(query)
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


@router.post("", response_model=DeviceResponse)
async def create_device(
    body: DeviceCreate,
    ctx: TenantContext = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    device = Device(
        id=body.id,
        org_id=ctx.org_id,
        group_id=body.group_id,
        name=body.name,
        device_type=body.device_type,
    )
    db.add(device)
    await db.commit()
    await db.refresh(device)
    return device


@router.delete("/{device_id}")
async def delete_device(
    device_id: str,
    ctx: TenantContext = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    query = select(Device).where(Device.id == device_id, Device.org_id == ctx.org_id)
    result = await db.execute(query)
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    await db.delete(device)
    await db.commit()
    return {"status": "deleted"}
