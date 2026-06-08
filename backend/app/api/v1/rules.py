"""Alarm rules management endpoints."""
import uuid

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_rule_engine
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

    # Register in rule engine
    rule_engine.register_rule(parsed)

    return db_rule


@router.put("/{rule_id}", response_model=RuleResponse)
async def update_rule(
    rule_id: str,
    body: RuleUpdate,
    ctx: TenantContext = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
    rule_engine=Depends(get_rule_engine),
):
    query = select(AlarmRule).where(AlarmRule.id == rule_id, AlarmRule.org_id == ctx.org_id)
    result = await db.execute(query)
    db_rule = result.scalar_one_or_none()
    if not db_rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_rule, key, value)

    await db.commit()
    await db.refresh(db_rule)

    # Re-register in rule engine
    rule_engine.unregister_rule(rule_id)
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
    try:
        parsed = parse_rule(rule_data)
        rule_engine.register_rule(parsed)
    except RuleParseError:
        pass

    return db_rule


@router.delete("/{rule_id}")
async def delete_rule(
    rule_id: str,
    ctx: TenantContext = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
    rule_engine=Depends(get_rule_engine),
):
    query = select(AlarmRule).where(AlarmRule.id == rule_id, AlarmRule.org_id == ctx.org_id)
    result = await db.execute(query)
    db_rule = result.scalar_one_or_none()
    if not db_rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    rule_engine.unregister_rule(rule_id)
    await db.delete(db_rule)
    await db.commit()
    return {"status": "deleted"}
