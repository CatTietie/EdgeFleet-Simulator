"""Unit tests for the rule DSL parser."""
import pytest
from app.rule_dsl.parser import parse_rule, RuleParseError
from app.rule_dsl.models import (
    Comparator, CompareExpr, ConsecutiveTemporal, LogicalExpr,
    LogicalOperator, RuleDef, TargetScope, WindowTemporal,
)


def _make_rule(trigger_condition, recovery_condition=None):
    return {
        "rule_id": "test-rule-1",
        "name": "Test Rule",
        "org_id": "org-test",
        "enabled": True,
        "target": {"scope": "org"},
        "trigger_condition": trigger_condition,
        "recovery_condition": recovery_condition,
        "severity": "warning",
        "actions": {"webhook_urls": ["http://example.com/hook"], "cooldown_seconds": 30},
    }


class TestParseSimpleCondition:
    def test_single_compare(self):
        rule = parse_rule(_make_rule(
            {"metric": "temperature", "comparator": ">", "threshold": 80, "temporal": None}
        ))
        assert isinstance(rule.trigger_condition, CompareExpr)
        assert rule.trigger_condition.metric == "temperature"
        assert rule.trigger_condition.comparator == Comparator.GT
        assert rule.trigger_condition.threshold == 80.0
        assert rule.trigger_condition.temporal is None

    def test_with_consecutive_temporal(self):
        rule = parse_rule(_make_rule(
            {"metric": "temperature", "comparator": ">", "threshold": 80,
             "temporal": {"type": "consecutive", "count": 3}}
        ))
        assert isinstance(rule.trigger_condition.temporal, ConsecutiveTemporal)
        assert rule.trigger_condition.temporal.count == 3

    def test_with_window_temporal(self):
        rule = parse_rule(_make_rule(
            {"metric": "humidity", "comparator": "<", "threshold": 20,
             "temporal": {"type": "within", "seconds": 60, "min_occurrences": 3}}
        ))
        assert isinstance(rule.trigger_condition.temporal, WindowTemporal)
        assert rule.trigger_condition.temporal.seconds == 60
        assert rule.trigger_condition.temporal.min_occurrences == 3


class TestParseLogicalExpr:
    def test_and_two_conditions(self):
        rule = parse_rule(_make_rule({
            "operator": "AND",
            "conditions": [
                {"metric": "temperature", "comparator": ">", "threshold": 80, "temporal": {"type": "consecutive", "count": 3}},
                {"metric": "humidity", "comparator": "<", "threshold": 20, "temporal": None},
            ]
        }))
        assert isinstance(rule.trigger_condition, LogicalExpr)
        assert rule.trigger_condition.operator == LogicalOperator.AND
        assert len(rule.trigger_condition.conditions) == 2

    def test_or_conditions(self):
        rule = parse_rule(_make_rule({
            "operator": "OR",
            "conditions": [
                {"metric": "temperature", "comparator": ">", "threshold": 90, "temporal": None},
                {"metric": "temperature", "comparator": "<", "threshold": -5, "temporal": None},
            ]
        }))
        assert rule.trigger_condition.operator == LogicalOperator.OR


class TestParseTarget:
    def test_org_scope(self):
        rule = parse_rule(_make_rule(
            {"metric": "temperature", "comparator": ">", "threshold": 80, "temporal": None}
        ))
        assert rule.target.scope == TargetScope.ORG

    def test_group_scope(self):
        data = _make_rule(
            {"metric": "temperature", "comparator": ">", "threshold": 80, "temporal": None}
        )
        data["target"] = {"scope": "group", "group_id": "floor-3"}
        rule = parse_rule(data)
        assert rule.target.scope == TargetScope.GROUP
        assert rule.target.group_id == "floor-3"

    def test_device_scope(self):
        data = _make_rule(
            {"metric": "temperature", "comparator": ">", "threshold": 80, "temporal": None}
        )
        data["target"] = {"scope": "device", "device_ids": ["sensor-001", "sensor-002"]}
        rule = parse_rule(data)
        assert rule.target.scope == TargetScope.DEVICE
        assert rule.target.device_ids == ["sensor-001", "sensor-002"]


class TestParseErrors:
    def test_missing_rule_id(self):
        with pytest.raises(RuleParseError):
            parse_rule({"name": "broken", "org_id": "x", "trigger_condition": {}})

    def test_invalid_comparator(self):
        with pytest.raises((RuleParseError, ValueError)):
            parse_rule(_make_rule(
                {"metric": "temp", "comparator": "INVALID", "threshold": 80, "temporal": None}
            ))

    def test_missing_trigger_condition(self):
        with pytest.raises((RuleParseError, KeyError)):
            parse_rule({"rule_id": "x", "org_id": "y", "name": "z"})
