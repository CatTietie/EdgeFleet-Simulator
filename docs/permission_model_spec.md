# Permission Model Specification

## Overview

EdgeFleet uses a three-level organizational hierarchy with role-based access control (RBAC). Data isolation is enforced at every layer: MQTT broker (ACL), API middleware (JWT claims), and database queries (tenant filtering).

## Organizational Hierarchy

```
Organization (Tenant)
  └── Group (Department / Floor / Zone)
       └── User
            └── Role: admin | operator | viewer
```

### Organization

The top-level isolation boundary. Each organization:
- Has its own set of devices, groups, alarm rules, and alarm events
- Is assigned a unique MQTT username for broker ACL
- Cannot access any data belonging to other organizations

### Group

A logical grouping of devices within an organization:
- Represents a department, floor, zone, or functional area
- Users can be assigned to one or more groups
- Alarm rules can target a specific group

### User

An individual with access to the platform:
- Belongs to exactly one organization
- Is assigned to one or more groups (or all groups if admin)
- Has exactly one role within their organization

## Roles and Permissions

### Role Definitions

| Role | Scope | Description |
|------|-------|-------------|
| `admin` | Entire organization | Full control over all resources within the org |
| `operator` | Assigned groups | Can manage devices and acknowledge alarms in their groups |
| `viewer` | Assigned groups | Read-only access to devices and alarms in their groups |

### Permission Matrix

| Resource | Action | Admin | Operator | Viewer |
|----------|--------|-------|----------|--------|
| Devices | List/Read | All in org | Own groups | Own groups |
| Devices | Create/Update/Delete | Yes | No | No |
| Devices | Send Command | Yes | Yes | No |
| Alarm Rules | List/Read | All in org | Own groups | Own groups |
| Alarm Rules | Create/Update/Delete | Yes | No | No |
| Alarm Events | List/Read | All in org | Own groups | Own groups |
| Alarm Events | Acknowledge | Yes | Yes | No |
| Alarm Events | Close | Yes | No | No |
| Users | List/Read | All in org | All in org | Self only |
| Users | Create/Update/Delete | Yes | No | No |
| Groups | List/Read | All in org | All in org | Own groups |
| Groups | Create/Update/Delete | Yes | No | No |
| Webhooks | Configure | Yes | No | No |
| Dashboard | View | Yes | Yes | Yes |
| Dashboard | Configure Layouts | Yes | Yes | No |

## Authentication

### Login Flow

```
POST /api/v1/auth/login
Body: { "username": "string", "password": "string" }
Response: {
  "access_token": "JWT (15 min TTL)",
  "refresh_token": "opaque token (7 day TTL)",
  "token_type": "bearer"
}
```

### JWT Payload

```json
{
  "sub": "user-uuid-001",
  "org_id": "org-abc123",
  "group_ids": ["floor-3", "floor-4"],
  "role": "operator",
  "exp": 1717850100,
  "iat": 1717849200
}
```

| Claim | Type | Description |
|-------|------|-------------|
| `sub` | string | User UUID |
| `org_id` | string | Organization the user belongs to |
| `group_ids` | string[] | Groups the user is assigned to (empty for admin = all groups) |
| `role` | string | One of: `admin`, `operator`, `viewer` |
| `exp` | integer | Token expiration (Unix epoch) |
| `iat` | integer | Token issued at (Unix epoch) |

### Token Refresh

```
POST /api/v1/auth/refresh
Body: { "refresh_token": "string" }
Response: { "access_token": "new JWT", "refresh_token": "new refresh token" }
```

## API Enforcement

### Middleware: Tenant Context Injection

Every authenticated request passes through `tenant_context` middleware that:

1. Extracts and validates the JWT from the `Authorization: Bearer <token>` header
2. Injects `org_id`, `group_ids`, and `role` into the request state
3. Rejects requests with expired or invalid tokens (HTTP 401)

### Query-Level Filtering

All database and InfluxDB queries **must** include tenant filtering:

```python
# SQLAlchemy example
query = select(Device).where(Device.org_id == request.state.org_id)

# For non-admin users, also filter by group
if request.state.role != "admin":
    query = query.where(Device.group_id.in_(request.state.group_ids))
```

```python
# InfluxDB example
query = f'''
from(bucket: "telemetry")
  |> range(start: -1h)
  |> filter(fn: (r) => r.org_id == "{org_id}")
  |> filter(fn: (r) => r.group_id == "{group_id}")
'''
```

### Role-Based Endpoint Guards

```python
from app.middleware.tenant_context import require_role

@router.post("/rules")
async def create_rule(rule: RuleCreate, user=Depends(require_role("admin"))):
    ...

@router.post("/alarms/{alarm_id}/ack")
async def ack_alarm(alarm_id: str, user=Depends(require_role("operator"))):
    ...
```

The `require_role` dependency checks that the user's role has at least the required permission level: `admin > operator > viewer`.

## MQTT Broker Isolation

### Per-Organization Credentials

Each organization is assigned MQTT credentials:
- **Username**: `{org_id}`
- **Password**: Generated and stored hashed in Mosquitto passwd file

### ACL Enforcement

```
# Devices can only publish/subscribe within their org namespace
pattern readwrite edgefleet/%u/#
```

This ensures:
- Organization A's devices publish to `edgefleet/org-a/...`
- Organization A's devices **cannot** subscribe to `edgefleet/org-b/...`
- The platform service account has a separate read-all permission

## Data Isolation Summary

| Layer | Mechanism | Enforcement Point |
|-------|-----------|-------------------|
| MQTT Transport | ACL pattern by username | Mosquitto broker |
| API Gateway | JWT claims + middleware | FastAPI middleware |
| Database (PostgreSQL) | `org_id` column + WHERE clause | Every query |
| Time-Series (InfluxDB) | `org_id` tag + Flux filter | Every query |
| WebSocket | Room per org_id | Connection manager |
| Frontend | API-level filtering | Backend enforced |

## Automated Test Requirements

The following scenarios must be covered by automated tests:

1. **Cross-org isolation**: User in org-A requests devices/alarms/rules belonging to org-B → HTTP 404 (not 403, to avoid information leakage)
2. **Cross-group isolation**: Viewer in group-A requests device in group-B → HTTP 404
3. **Role escalation prevention**: Operator attempts admin-only action → HTTP 403
4. **Token expiration**: Expired JWT → HTTP 401
5. **MQTT ACL**: Device publishing to wrong org topic → connection rejected/message dropped
6. **Webhook scoping**: Alarm in org-A triggers only org-A's webhook endpoints, not org-B's
