"""Tenant context middleware and role-based access dependencies."""
from dataclasses import dataclass
from functools import wraps

import jwt
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.config import settings

security = HTTPBearer()

ROLE_HIERARCHY = {"admin": 3, "operator": 2, "viewer": 1}


@dataclass
class TenantContext:
    user_id: str
    org_id: str
    group_ids: list[str]
    role: str

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    def can_access_group(self, group_id: str) -> bool:
        return self.is_admin or group_id in self.group_ids


async def get_tenant_context(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> TenantContext:
    """Extract and validate JWT, returning the tenant context."""
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    return TenantContext(
        user_id=payload["sub"],
        org_id=payload["org_id"],
        group_ids=payload.get("group_ids", []),
        role=payload.get("role", "viewer"),
    )


def require_role(minimum_role: str):
    """Dependency that checks the user has at least the specified role level."""
    min_level = ROLE_HIERARCHY.get(minimum_role, 0)

    async def _check(ctx: TenantContext = Depends(get_tenant_context)):
        user_level = ROLE_HIERARCHY.get(ctx.role, 0)
        if user_level < min_level:
            raise HTTPException(
                status_code=403,
                detail=f"Requires {minimum_role} role or higher",
            )
        return ctx

    return _check
