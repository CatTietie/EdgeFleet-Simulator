"""Parse JSON rule definitions into AST nodes."""
from app.rule_dsl.models import (
    AlarmState,
    Comparator,
    CompareExpr,
    ConsecutiveTemporal,
    Condition,
    LogicalExpr,
    LogicalOperator,
    RuleActions,
    RuleDef,
    RuleTarget,
    TargetScope,
    TemporalType,
    WindowTemporal,
)


class RuleParseError(Exception):
    pass


def parse_rule(data: dict) -> RuleDef:
    """Parse a JSON rule definition into a RuleDef AST."""
    try:
        target = _parse_target(data.get("target", {}))
        trigger = _parse_condition(data["trigger_condition"])
        recovery = None
        if data.get("recovery_condition"):
            recovery = _parse_condition(data["recovery_condition"])
        actions = _parse_actions(data.get("actions", {}))

        return RuleDef(
            rule_id=data["rule_id"],
            name=data.get("name", ""),
            org_id=data["org_id"],
            enabled=data.get("enabled", True),
            target=target,
            trigger_condition=trigger,
            recovery_condition=recovery,
            severity=data.get("severity", "warning"),
            actions=actions,
        )
    except KeyError as e:
        raise RuleParseError(f"Missing required field: {e}")
    except (ValueError, TypeError) as e:
        raise RuleParseError(f"Invalid rule definition: {e}")


def _parse_target(data: dict) -> RuleTarget:
    scope = TargetScope(data.get("scope", "org"))
    return RuleTarget(
        scope=scope,
        group_id=data.get("group_id"),
        device_ids=data.get("device_ids"),
    )


def _parse_condition(data: dict) -> Condition:
    if "operator" in data:
        return _parse_logical(data)
    elif "metric" in data:
        return _parse_compare(data)
    else:
        raise RuleParseError(f"Cannot determine condition type: {data}")


def _parse_logical(data: dict) -> LogicalExpr:
    operator = LogicalOperator(data["operator"])
    conditions = [_parse_condition(c) for c in data["conditions"]]
    return LogicalExpr(operator=operator, conditions=conditions)


def _parse_compare(data: dict) -> CompareExpr:
    comparator = Comparator(data["comparator"])
    temporal = _parse_temporal(data.get("temporal"))
    return CompareExpr(
        metric=data["metric"],
        comparator=comparator,
        threshold=float(data["threshold"]),
        temporal=temporal,
    )


def _parse_temporal(data: dict | None):
    if data is None:
        return None
    temporal_type = TemporalType(data["type"])
    if temporal_type == TemporalType.CONSECUTIVE:
        return ConsecutiveTemporal(count=int(data["count"]))
    elif temporal_type == TemporalType.WITHIN:
        return WindowTemporal(
            seconds=int(data["seconds"]),
            min_occurrences=int(data["min_occurrences"]),
        )
    raise RuleParseError(f"Unknown temporal type: {data['type']}")


def _parse_actions(data: dict) -> RuleActions:
    return RuleActions(
        webhook_urls=data.get("webhook_urls", []),
        cooldown_seconds=data.get("cooldown_seconds", 60),
    )
