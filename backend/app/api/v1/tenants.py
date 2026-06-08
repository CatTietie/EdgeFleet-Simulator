"""Tenant (organization and group) management endpoints."""
import uuid

from fastapi import APIRouter, HTTPException, Depends
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.middleware.tenant_context import TenantContext, require_role
from app.models import Organization, Group, User
from app.schemas import OrgCreate, OrgResponse, GroupCreate, GroupResponse, UserCreate, UserResponse

router = APIRouter(prefix="/tenants", tags=["tenants"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@router.post("/orgs", response_model=OrgResponse)
async def create_org(body: OrgCreate, db: AsyncSession = Depends(get_db)):
    org = Organization(
        id=body.id,
        name=body.name,
        mqtt_username=body.id,
        mqtt_password_hash=pwd_context.hash(body.id + "123"),
    )
    db.add(org)
    await db.commit()
    await db.refresh(org)
    return org


@router.get("/orgs/{org_id}", response_model=OrgResponse)
async def get_org(
    org_id: str,
    ctx: TenantContext = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    if ctx.org_id != org_id:
        raise HTTPException(status_code=404, detail="Organization not found")
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


@router.post("/groups", response_model=GroupResponse)
async def create_group(
    body: GroupCreate,
    ctx: TenantContext = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    group = Group(id=body.id, org_id=ctx.org_id, name=body.name, description=body.description)
    db.add(group)
    await db.commit()
    await db.refresh(group)
    return group


@router.get("/groups", response_model=list[GroupResponse])
async def list_groups(
    ctx: TenantContext = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    query = select(Group).where(Group.org_id == ctx.org_id)
    if not ctx.is_admin:
        query = query.where(Group.id.in_(ctx.group_ids))
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/users", response_model=UserResponse)
async def create_user(
    body: UserCreate,
    ctx: TenantContext = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    user = User(
        id=str(uuid.uuid4()),
        org_id=ctx.org_id,
        username=body.username,
        password_hash=pwd_context.hash(body.password),
        role=body.role,
        group_ids=body.group_ids,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    ctx: TenantContext = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    query = select(User).where(User.org_id == ctx.org_id)
    result = await db.execute(query)
    return result.scalars().all()
