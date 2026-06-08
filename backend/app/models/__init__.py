"""SQLAlchemy models for multi-tenant data."""
from datetime import datetime
from sqlalchemy import Column, String, Boolean, Integer, Float, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(String(36), primary_key=True)
    name = Column(String(128), nullable=False)
    mqtt_username = Column(String(64), unique=True, nullable=False)
    mqtt_password_hash = Column(String(256), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    groups = relationship("Group", back_populates="organization", cascade="all, delete-orphan")
    users = relationship("User", back_populates="organization", cascade="all, delete-orphan")


class Group(Base):
    __tablename__ = "groups"

    id = Column(String(36), primary_key=True)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False)
    name = Column(String(128), nullable=False)
    description = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    organization = relationship("Organization", back_populates="groups")
    devices = relationship("Device", back_populates="group", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False)
    username = Column(String(64), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(16), nullable=False, default="viewer")  # admin, operator, viewer
    group_ids = Column(JSON, default=list)  # list of group_id strings
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    organization = relationship("Organization", back_populates="users")


class Device(Base):
    __tablename__ = "devices"

    id = Column(String(64), primary_key=True)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False)
    group_id = Column(String(36), ForeignKey("groups.id"), nullable=False)
    name = Column(String(128), nullable=False)
    device_type = Column(String(64), default="sensor")
    status = Column(String(16), default="offline")  # online, offline
    last_seen_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    group = relationship("Group", back_populates="devices")


class AlarmRule(Base):
    __tablename__ = "alarm_rules"

    id = Column(String(36), primary_key=True)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False)
    name = Column(String(128), nullable=False)
    description = Column(Text, default="")
    enabled = Column(Boolean, default=True)
    severity = Column(String(16), default="warning")
    target = Column(JSON, nullable=False)  # {scope, group_id, device_ids}
    trigger_condition = Column(JSON, nullable=False)
    recovery_condition = Column(JSON, nullable=True)
    actions = Column(JSON, nullable=False)  # {webhook_urls, cooldown_seconds}
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AlarmEvent(Base):
    __tablename__ = "alarm_events"

    id = Column(String(128), primary_key=True)
    rule_id = Column(String(36), nullable=False)
    device_id = Column(String(64), nullable=False)
    org_id = Column(String(36), nullable=False)
    group_id = Column(String(36), default="")
    event_type = Column(String(16), nullable=False)  # triggered, recovered
    severity = Column(String(16), default="warning")
    values = Column(JSON, default=dict)
    acknowledged = Column(Boolean, default=False)
    acknowledged_by = Column(String(36), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
