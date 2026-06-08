"""Core rule engine: evaluates incoming data points against all applicable rules."""
import asyncio
import logging
import time
from dataclasses import dataclass

from app.rule_dsl.models import (
    AlarmState,
    Condition,
    RuleDef,
    RuleTarget,
    TargetScope,
)
from app.rule_dsl.evaluator import evaluate_condition
from app.rule_dsl.state_machine import (
    DEFAULT_RECOVERY_FALSE_STREAK,
    DeviceRuleState,
    StateStore,
)

logger = logging.getLogger(__name__)


@dataclass
class AlarmEvent:
    alarm_id: str
    rule_id: str
    rule_name: str
    device_id: str
    org_id: str
    group_id: str
    event_type: str  # "triggered" or "recovered"
    severity: str
    values: dict
    timestamp_ms: int


class RuleEngine:
    def __init__(self, alarm_manager):
        self._rules: dict[str, RuleDef] = {}
        self._rule_index: dict[str, list[str]] = {}  # org_id -> [rule_ids]
        self._group_index: dict[tuple[str, str], list[str]] = {}  # (org_id, group_id) -> [rule_ids]
        self._state_store = StateStore()
        self._alarm_manager = alarm_manager

    def register_rule(self, rule: RuleDef):
        self._rules[rule.rule_id] = rule
        if rule.org_id not in self._rule_index:
            self._rule_index[rule.org_id] = []
        self._rule_index[rule.org_id].append(rule.rule_id)

        if rule.target.scope == TargetScope.GROUP and rule.target.group_id:
            key = (rule.org_id, rule.target.group_id)
            if key not in self._group_index:
                self._group_index[key] = []
            self._group_index[key].append(rule.rule_id)

    def unregister_rule(self, rule_id: str):
        rule = self._rules.pop(rule_id, None)
        if not rule:
            return

        if rule.org_id in self._rule_index:
            self._rule_index[rule.org_id] = [
                rid for rid in self._rule_index[rule.org_id] if rid != rule_id
            ]

        if rule.target.scope == TargetScope.GROUP and rule.target.group_id:
            key = (rule.org_id, rule.target.group_id)
            if key in self._group_index:
                self._group_index[key] = [
                    rid for rid in self._group_index[key] if rid != rule_id
                ]

        # Auto-recover any active alarms for this rule
        alarmed_states = self._state_store.remove_rule(rule_id)
        for state in alarmed_states:
            event = AlarmEvent(
                alarm_id=f"alm-{rule_id}-{state.device_id}-{int(time.time()*1000)}",
                rule_id=rule_id,
                rule_name=rule.name,
                device_id=state.device_id,
                org_id=rule.org_id,
                group_id="",
                event_type="recovered",
                severity=rule.severity,
                values={},
                timestamp_ms=int(time.time() * 1000),
            )
            asyncio.create_task(self._alarm_manager.handle_event(event))

    def _find_applicable_rules(self, org_id: str, group_id: str, device_id: str) -> list[RuleDef]:
        applicable = []
        rule_ids = set()

        # Org-level rules
        for rid in self._rule_index.get(org_id, []):
            rule = self._rules.get(rid)
            if rule and rule.enabled and rule.target.scope == TargetScope.ORG:
                rule_ids.add(rid)
                applicable.append(rule)

        # Group-level rules
        for rid in self._group_index.get((org_id, group_id), []):
            if rid in rule_ids:
                continue
            rule = self._rules.get(rid)
            if rule and rule.enabled:
                rule_ids.add(rid)
                applicable.append(rule)

        # Device-level rules
        for rid in self._rule_index.get(org_id, []):
            if rid in rule_ids:
                continue
            rule = self._rules.get(rid)
            if rule and rule.enabled and rule.target.scope == TargetScope.DEVICE:
                if rule.target.device_ids and device_id in rule.target.device_ids:
                    applicable.append(rule)

        return applicable

    async def evaluate(self, data_point: dict):
        """Evaluate all applicable rules for an incoming data point."""
        org_id = data_point["org_id"]
        group_id = data_point["group_id"]
        device_id = data_point["device_id"]
        timestamp_ms = data_point["timestamp"]
        metrics = data_point["metrics"]

        rules = self._find_applicable_rules(org_id, group_id, device_id)
        if not rules:
            return

        for rule in rules:
            state = self._state_store.get_or_create(device_id, rule.rule_id)

            # Update ring buffers
            for metric_name, value in metrics.items():
                state.update_buffer(metric_name, timestamp_ms, value)

            # Evaluate based on current alarm state
            event = self._evaluate_single(rule, state, data_point)
            if event:
                await self._alarm_manager.handle_event(event)

    def _evaluate_single(self, rule: RuleDef, state: DeviceRuleState, data_point: dict) -> AlarmEvent | None:
        timestamp_ms = data_point["timestamp"]

        if state.current_state == AlarmState.NORMAL:
            triggered = evaluate_condition(rule.trigger_condition, state, timestamp_ms)
            if triggered and not state.is_in_cooldown(timestamp_ms):
                state.trigger(timestamp_ms, rule.actions.cooldown_seconds)
                return AlarmEvent(
                    alarm_id=f"alm-{rule.rule_id}-{state.device_id}-{timestamp_ms}",
                    rule_id=rule.rule_id,
                    rule_name=rule.name,
                    device_id=state.device_id,
                    org_id=data_point["org_id"],
                    group_id=data_point["group_id"],
                    event_type="triggered",
                    severity=rule.severity,
                    values=data_point["metrics"],
                    timestamp_ms=timestamp_ms,
                )

        elif state.current_state == AlarmState.ALARM:
            if rule.recovery_condition:
                recovered = evaluate_condition(rule.recovery_condition, state, timestamp_ms)
                if recovered:
                    state.recover()
                    return AlarmEvent(
                        alarm_id=f"alm-{rule.rule_id}-{state.device_id}-{timestamp_ms}",
                        rule_id=rule.rule_id,
                        rule_name=rule.name,
                        device_id=state.device_id,
                        org_id=data_point["org_id"],
                        group_id=data_point["group_id"],
                        event_type="recovered",
                        severity=rule.severity,
                        values=data_point["metrics"],
                        timestamp_ms=timestamp_ms,
                    )
            else:
                # Default recovery: trigger condition false for N consecutive evaluations
                triggered = evaluate_condition(rule.trigger_condition, state, timestamp_ms)
                if not triggered:
                    state.increment_false_streak()
                    if state.false_streak >= DEFAULT_RECOVERY_FALSE_STREAK:
                        state.recover()
                        return AlarmEvent(
                            alarm_id=f"alm-{rule.rule_id}-{state.device_id}-{timestamp_ms}",
                            rule_id=rule.rule_id,
                            rule_name=rule.name,
                            device_id=state.device_id,
                            org_id=data_point["org_id"],
                            group_id=data_point["group_id"],
                            event_type="recovered",
                            severity=rule.severity,
                            values=data_point["metrics"],
                            timestamp_ms=timestamp_ms,
                        )
                else:
                    state.false_streak = 0

        return None

    @property
    def rule_count(self) -> int:
        return len(self._rules)

    @property
    def state_count(self) -> int:
        return self._state_store.size
