"""AST node dataclasses for the alarm rule DSL."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Comparator(str, Enum):
    GT = ">"
    LT = "<"
    GTE = ">="
    LTE = "<="
    EQ = "=="
    NEQ = "!="


class LogicalOperator(str, Enum):
    AND = "AND"
    OR = "OR"


class TemporalType(str, Enum):
    CONSECUTIVE = "consecutive"
    WITHIN = "within"


class AlarmState(str, Enum):
    NORMAL = "NORMAL"
    ALARM = "ALARM"


class TargetScope(str, Enum):
    ORG = "org"
    GROUP = "group"
    DEVICE = "device"


@dataclass
class ConsecutiveTemporal:
    type: TemporalType = TemporalType.CONSECUTIVE
    count: int = 1


@dataclass
class WindowTemporal:
    type: TemporalType = TemporalType.WITHIN
    seconds: int = 60
    min_occurrences: int = 1


Temporal = ConsecutiveTemporal | WindowTemporal | None


@dataclass
class CompareExpr:
    metric: str
    comparator: Comparator
    threshold: float
    temporal: Temporal = None


@dataclass
class LogicalExpr:
    operator: LogicalOperator
    conditions: list[CompareExpr | LogicalExpr] = field(default_factory=list)


Condition = CompareExpr | LogicalExpr


@dataclass
class RuleTarget:
    scope: TargetScope
    group_id: Optional[str] = None
    device_ids: Optional[list[str]] = None


@dataclass
class RuleActions:
    webhook_urls: list[str] = field(default_factory=list)
    cooldown_seconds: int = 60


@dataclass
class RuleDef:
    rule_id: str
    name: str
    org_id: str
    enabled: bool
    target: RuleTarget
    trigger_condition: Condition
    recovery_condition: Optional[Condition]
    severity: str = "warning"
    actions: RuleActions = field(default_factory=RuleActions)
