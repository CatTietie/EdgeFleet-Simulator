"""Alarm rules management endpoints."""
import uuid

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_rule_engine, get_rule_sync
from app.middleware.tenant_context import TenantContext, get_tenant_context, require_role
from app.models import AlarmRule
from app.schemas import RuleCreate, RuleResponse, RuleUpdate
from app.rule_dsl.parser import parse_rule, RuleParseError

router = APIRouter(prefix="/rules", tags=["rules"])


@router.get("", response_model=list[RuleResponse])
async def list_rules(
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    query = select(AlarmRule).where(AlarmRule.org_id == ctx.org_id)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{rule_id}", response_model=RuleResponse)
async def get_rule(
    rule_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    query = select(AlarmRule).where(AlarmRule.id == rule_id, AlarmRule.org_id == ctx.org_id)
    result = await db.execute(query)
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule


@router.post("", response_model=RuleResponse)
async def create_rule(
    body: RuleCreate,
    ctx: TenantContext = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
    rule_engine=Depends(get_rule_engine),
    rule_sync=Depends(get_rule_sync),
):
    rule_id = str(uuid.uuid4())

    # Validate DSL
    rule_data = {
        "rule_id": rule_id,
        "org_id": ctx.org_id,
        "name": body.name,
        "enabled": True,
        "target": body.target,
        "trigger_condition": body.trigger_condition,
        "recovery_condition": body.recovery_condition,
        "severity": body.severity,
        "actions": body.actions,
    }
    try:
        parsed = parse_rule(rule_data)
    except RuleParseError as e:
        raise HTTPException(status_code=400, detail=f"Invalid rule DSL: {e}")

    db_rule = AlarmRule(
        id=rule_id,
        org_id=ctx.org_id,
        name=body.name,
        description=body.description,
        severity=body.severity,
        target=body.target,
        trigger_condition=body.trigger_condition,
        recovery_condition=body.recovery_condition,
        actions=body.actions,
    )
    db.add(db_rule)
    await db.commit()
    await db.refresh(db_rule)

    rule_engine.register_rule(parsed)

    # Broadcast to other instances
    await rule_sync.publish_rule_change(ctx.org_id, rule_id, "created", rule_data)

    return db_rule


@router.put("/{rule_id}", response_model=RuleResponse)
async def update_rule(
    rule_id: str,
    body: RuleUpdate,
    ctx: TenantContext = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
    rule_engine=Depends(get_rule_engine),
    rule_sync=Depends(get_rule_sync),
):
    query = (
        select(AlarmRule)
        .where(AlarmRule.id == rule_id, AlarmRule.org_id == ctx.org_id)
        .with_for_update()
    )
    result = await db.execute(query)
    db_rule = result.scalar_one_or_none()
    if not db_rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    # Optimistic concurrency check
    if db_rule.version != body.version:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Conflict: rule was modified by another user",
                "server_version": db_rule.version,
            },
        )

    # Capture old rule data for hot-reload change detection
    old_rule_data = {
        "trigger_condition": db_rule.trigger_condition,
        "recovery_condition": db_rule.recovery_condition,
        "target": db_rule.target,
    }

    update_data = body.model_dump(exclude_unset=True, exclude={"version"})
    for key, value in update_data.items():
        setattr(db_rule, key, value)

    db_rule.version += 1
    await db.commit()
    await db.refresh(db_rule)

    # Hot-reload in rule engine
    rule_data = {
        "rule_id": rule_id,
        "org_id": ctx.org_id,
        "name": db_rule.name,
        "enabled": db_rule.enabled,
        "target": db_rule.target,
        "trigger_condition": db_rule.trigger_condition,
        "recovery_condition": db_rule.recovery_condition,
        "severity": db_rule.severity,
        "actions": db_rule.actions,
    }
    new_rule_data = {
        "trigger_condition": db_rule.trigger_condition,
        "recovery_condition": db_rule.recovery_condition,
        "target": db_rule.target,
    }
    try:
        parsed = parse_rule(rule_data)
        await rule_engine.hot_reload_rule(old_rule_data, new_rule_data, parsed, ctx.org_id)
    except RuleParseError:
        pass

    # Broadcast to other instances (include old data for change detection)
    await rule_sync.publish_rule_change(ctx.org_id, rule_id, "updated", rule_data, old_rule_data=old_rule_data)

    return db_rule


@router.delete("/{rule_id}")
async def delete_rule(
    rule_id: str,
    ctx: TenantContext = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
    rule_engine=Depends(get_rule_engine),
    rule_sync=Depends(get_rule_sync),
):
    query = select(AlarmRule).where(AlarmRule.id == rule_id, AlarmRule.org_id == ctx.org_id)
    result = await db.execute(query)
    db_rule = result.scalar_one_or_none()
    if not db_rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    rule_engine.unregister_rule(rule_id)
    await db.delete(db_rule)
    await db.commit()

    # Clear persisted state from Redis
    await rule_engine._state_persistence.clear_rule(ctx.org_id, rule_id)

    # Broadcast to other instances
    await rule_sync.publish_rule_change(ctx.org_id, rule_id, "deleted", None)

    return {"status": "deleted"}
