"""Recursive condition evaluator for the alarm rule DSL."""
from operator import gt, lt, ge, le, eq, ne

from app.rule_dsl.models import (
    Comparator,
    CompareExpr,
    Condition,
    ConsecutiveTemporal,
    LogicalExpr,
    LogicalOperator,
    WindowTemporal,
)
from app.rule_dsl.state_machine import DeviceRuleState

COMPARATOR_OPS = {
    Comparator.GT: gt,
    Comparator.LT: lt,
    Comparator.GTE: ge,
    Comparator.LTE: le,
    Comparator.EQ: eq,
    Comparator.NEQ: ne,
}


def evaluate_condition(condition: Condition, state: DeviceRuleState, current_time_ms: int) -> bool:
    """Evaluate a condition tree against the current device-rule state."""
    if isinstance(condition, LogicalExpr):
        return _evaluate_logical(condition, state, current_time_ms)
    elif isinstance(condition, CompareExpr):
        return _evaluate_compare(condition, state, current_time_ms)
    return False


def _evaluate_logical(expr: LogicalExpr, state: DeviceRuleState, current_time_ms: int) -> bool:
    if expr.operator == LogicalOperator.AND:
        return all(evaluate_condition(c, state, current_time_ms) for c in expr.conditions)
    else:  # OR
        return any(evaluate_condition(c, state, current_time_ms) for c in expr.conditions)


def _evaluate_compare(expr: CompareExpr, state: DeviceRuleState, current_time_ms: int) -> bool:
    buffer = state.get_buffer(expr.metric)
    if not buffer:
        return False

    op = COMPARATOR_OPS[expr.comparator]

    if expr.temporal is None:
        _, latest_value = buffer[-1]
        return op(latest_value, expr.threshold)

    elif isinstance(expr.temporal, ConsecutiveTemporal):
        n = expr.temporal.count
        if len(buffer) < n:
            return False
        return all(
            op(value, expr.threshold)
            for _, value in list(buffer)[-n:]
        )

    elif isinstance(expr.temporal, WindowTemporal):
        cutoff_ms = current_time_ms - (expr.temporal.seconds * 1000)
        recent = [(ts, val) for ts, val in buffer if ts >= cutoff_ms]
        matching = sum(1 for _, val in recent if op(val, expr.threshold))
        return matching >= expr.temporal.min_occurrences

    return False
