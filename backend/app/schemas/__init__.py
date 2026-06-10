"""Pydantic schemas for API request/response."""
from datetime import datetime
from pydantic import BaseModel, Field


# Auth
class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


# Tenant
class OrgCreate(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9-]+$", max_length=36)
    name: str = Field(max_length=128)


class OrgResponse(BaseModel):
    id: str
    name: str
    created_at: datetime | None = None


class GroupCreate(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9-]+$", max_length=36)
    name: str = Field(max_length=128)
    description: str = ""


class GroupResponse(BaseModel):
    id: str
    org_id: str
    name: str
    description: str
    created_at: datetime | None = None


# User
class UserCreate(BaseModel):
    username: str = Field(max_length=64)
    password: str = Field(min_length=6)
    role: str = Field(pattern=r"^(admin|operator|viewer)$")
    group_ids: list[str] = []


class UserResponse(BaseModel):
    id: str
    org_id: str
    username: str
    role: str
    group_ids: list[str]
    is_active: bool
    created_at: datetime | None = None


# Device
class DeviceCreate(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9-]+$", max_length=64)
    group_id: str
    name: str = Field(max_length=128)
    device_type: str = "sensor"


class DeviceResponse(BaseModel):
    id: str
    org_id: str
    group_id: str
    name: str
    device_type: str
    status: str
    last_seen_at: datetime | None = None
    created_at: datetime | None = None


# Alarm Rule
class RuleCreate(BaseModel):
    name: str = Field(max_length=128)
    description: str = ""
    severity: str = "warning"
    target: dict
    trigger_condition: dict
    recovery_condition: dict | None = None
    actions: dict


class RuleResponse(BaseModel):
    id: str
    org_id: str
    name: str
    description: str
    enabled: bool
    severity: str
    target: dict
    trigger_condition: dict
    recovery_condition: dict | None
    actions: dict
    created_at: datetime | None = None
    updated_at: datetime | None = None


class RuleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    enabled: bool | None = None
    severity: str | None = None
    target: dict | None = None
    trigger_condition: dict | None = None
    recovery_condition: dict | None = None
    actions: dict | None = None


# Alarm Event
class AlarmEventResponse(BaseModel):
    id: str
    rule_id: str
    device_id: str
    org_id: str
    group_id: str
    event_type: str
    severity: str
    values: dict
    acknowledged: bool
    acknowledged_by: str | None
    is_derived: bool = False
    root_cause_device_id: str | None = None
    root_cause_alarm_id: str | None = None
    created_at: datetime | None = None


# Device Dependency
class DependencyCreate(BaseModel):
    parent_device_id: str
    child_device_id: str
    dependency_type: str = Field(pattern=r"^(gateway_sensor|power_device|switch_device)$")


class DependencyResponse(BaseModel):
    id: str
    org_id: str
    parent_device_id: str
    child_device_id: str
    dependency_type: str
    suppress_derived_notifications: bool
    created_at: datetime | None = None


class DependencyUpdate(BaseModel):
    suppress_derived_notifications: bool | None = None


class TopologyNode(BaseModel):
    device_id: str
    name: str
    device_type: str
    status: str
    has_active_alarm: bool = False


class TopologyEdge(BaseModel):
    id: str
    parent_device_id: str
    child_device_id: str
    dependency_type: str
    suppress_derived_notifications: bool


class TopologyResponse(BaseModel):
    nodes: list[TopologyNode]
    edges: list[TopologyEdge]
