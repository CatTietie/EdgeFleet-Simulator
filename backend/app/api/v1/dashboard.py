"""Dashboard data endpoints (telemetry queries)."""
from fastapi import APIRouter, Depends

from app.dependencies import get_influx_query
from app.middleware.tenant_context import TenantContext, get_tenant_context

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/device/{device_id}/latest")
async def device_latest(
    device_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    influx=Depends(get_influx_query),
):
    data = await influx.get_latest(ctx.org_id, device_id)
    return data or {"device_id": device_id, "metrics": {}, "timestamp": None}


@router.get("/device/{device_id}/timeseries")
async def device_timeseries(
    device_id: str,
    metric: str = "temperature",
    range_start: str = "-1h",
    aggregate: str = "1m",
    ctx: TenantContext = Depends(get_tenant_context),
    influx=Depends(get_influx_query),
):
    return await influx.get_time_series(
        org_id=ctx.org_id,
        device_id=device_id,
        metric=metric,
        range_start=range_start,
        aggregate_window=aggregate,
    )


@router.get("/group/{group_id}/summary")
async def group_summary(
    group_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    influx=Depends(get_influx_query),
):
    if not ctx.can_access_group(group_id):
        return []
    return await influx.get_group_summary(ctx.org_id, group_id)
