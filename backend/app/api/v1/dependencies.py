"""Device dependency CRUD API endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_dependency_manager, get_alarm_manager
from app.middleware.tenant_context import TenantContext, get_tenant_context, require_role
from app.schemas import (
    DependencyCreate,
    DependencyResponse,
    DependencyUpdate,
    TopologyNode,
    TopologyEdge,
    TopologyResponse,
)
from app.models import Device
from sqlalchemy import select

router = APIRouter(prefix="/dependencies", tags=["dependencies"])


@router.post("/", response_model=DependencyResponse)
async def create_dependency(
    body: DependencyCreate,
    ctx: TenantContext = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    dep_mgr = get_dependency_manager()
    try:
        edge = await dep_mgr.add_dependency(
            org_id=ctx.org_id,
            parent_device_id=body.parent_device_id,
            child_device_id=body.child_device_id,
            dependency_type=body.dependency_type,
            session=db,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return DependencyResponse(
        id=edge.id,
        org_id=edge.org_id,
        parent_device_id=edge.parent_device_id,
        child_device_id=edge.child_device_id,
        dependency_type=edge.dependency_type,
        suppress_derived_notifications=edge.suppress_derived_notifications,
        created_at=edge.created_at,
    )


@router.get("/", response_model=list[DependencyResponse])
async def list_dependencies(
    ctx: TenantContext = Depends(get_tenant_context),
):
    dep_mgr = get_dependency_manager()
    edges = dep_mgr.get_org_edges(ctx.org_id)
    return [
        DependencyResponse(
            id=e.id,
            org_id=e.org_id,
            parent_device_id=e.parent_device_id,
            child_device_id=e.child_device_id,
            dependency_type=e.dependency_type,
            suppress_derived_notifications=e.suppress_derived_notifications,
            created_at=e.created_at,
        )
        for e in edges
    ]


@router.get("/topology", response_model=TopologyResponse)
async def get_topology(
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    dep_mgr = get_dependency_manager()
    alarm_mgr = get_alarm_manager()

    edges = dep_mgr.get_org_edges(ctx.org_id)

    device_ids = set()
    for e in edges:
        device_ids.add(e.parent_device_id)
        device_ids.add(e.child_device_id)

    if not device_ids:
        return TopologyResponse(nodes=[], edges=[])

    result = await db.execute(
        select(Device).where(Device.id.in_(list(device_ids)), Device.org_id == ctx.org_id)
    )
    devices = {d.id: d for d in result.scalars().all()}

    active_alarms = alarm_mgr.get_active_alarms(ctx.org_id)
    alarmed_devices = {a["device_id"] for a in active_alarms}

    nodes = [
        TopologyNode(
            device_id=d.id,
            name=d.name,
            device_type=d.device_type,
            status=d.status,
            has_active_alarm=d.id in alarmed_devices,
        )
        for d in devices.values()
    ]

    topo_edges = [
        TopologyEdge(
            id=e.id,
            parent_device_id=e.parent_device_id,
            child_device_id=e.child_device_id,
            dependency_type=e.dependency_type,
            suppress_derived_notifications=e.suppress_derived_notifications,
        )
        for e in edges
    ]

    return TopologyResponse(nodes=nodes, edges=topo_edges)


@router.put("/{edge_id}", response_model=DependencyResponse)
async def update_dependency(
    edge_id: str,
    body: DependencyUpdate,
    ctx: TenantContext = Depends(require_role("operator")),
    db: AsyncSession = Depends(get_db),
):
    dep_mgr = get_dependency_manager()
    edge = dep_mgr.get_edge(edge_id)
    if not edge or edge.org_id != ctx.org_id:
        raise HTTPException(status_code=404, detail="Dependency not found")

    updated = await dep_mgr.update_dependency(edge_id, body.suppress_derived_notifications, db)
    return DependencyResponse(
        id=updated.id,
        org_id=updated.org_id,
        parent_device_id=updated.parent_device_id,
        child_device_id=updated.child_device_id,
        dependency_type=updated.dependency_type,
        suppress_derived_notifications=updated.suppress_derived_notifications,
        created_at=updated.created_at,
    )


@router.delete("/{edge_id}")
async def delete_dependency(
    edge_id: str,
    ctx: TenantContext = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    dep_mgr = get_dependency_manager()
    edge = dep_mgr.get_edge(edge_id)
    if not edge or edge.org_id != ctx.org_id:
        raise HTTPException(status_code=404, detail="Dependency not found")

    await dep_mgr.remove_dependency(edge_id, db)
    return {"detail": "Dependency removed"}
