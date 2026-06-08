"""Unit tests for the rule evaluator - especially boundary conditions."""
import pytest
from app.rule_dsl.models import Comparator, CompareExpr, ConsecutiveTemporal, LogicalExpr, LogicalOperator, WindowTemporal
from app.rule_dsl.evaluator import evaluate_condition
from app.rule_dsl.state_machine import DeviceRuleState


def _make_state(metric: str, values: list[tuple[int, float]]) -> DeviceRuleState:
    state = DeviceRuleState(device_id="test-device", rule_id="test-rule")
    for ts, val in values:
        state.update_buffer(metric, ts, val)
    return state


class TestComparatorBoundary:
    """Test that boundary conditions (value == threshold) behave correctly."""

    def test_gt_exact_threshold_does_not_trigger(self):
        """Value exactly equals threshold with '>' should NOT trigger."""
        expr = CompareExpr(metric="temperature", comparator=Comparator.GT, threshold=80.0)
        state = _make_state("temperature", [(1000, 80.0)])
        assert evaluate_condition(expr, state, 1000) is False

    def test_gt_above_threshold_triggers(self):
        expr = CompareExpr(metric="temperature", comparator=Comparator.GT, threshold=80.0)
        state = _make_state("temperature", [(1000, 80.1)])
        assert evaluate_condition(expr, state, 1000) is True

    def test_gte_exact_threshold_triggers(self):
        """Value exactly equals threshold with '>=' SHOULD trigger."""
        expr = CompareExpr(metric="temperature", comparator=Comparator.GTE, threshold=80.0)
        state = _make_state("temperature", [(1000, 80.0)])
        assert evaluate_condition(expr, state, 1000) is True

    def test_lt_exact_threshold_does_not_trigger(self):
        expr = CompareExpr(metric="humidity", comparator=Comparator.LT, threshold=20.0)
        state = _make_state("humidity", [(1000, 20.0)])
        assert evaluate_condition(expr, state, 1000) is False

    def test_lte_exact_threshold_triggers(self):
        expr = CompareExpr(metric="humidity", comparator=Comparator.LTE, threshold=20.0)
        state = _make_state("humidity", [(1000, 20.0)])
        assert evaluate_condition(expr, state, 1000) is True

    def test_eq_exact_match(self):
        expr = CompareExpr(metric="temperature", comparator=Comparator.EQ, threshold=50.0)
        state = _make_state("temperature", [(1000, 50.0)])
        assert evaluate_condition(expr, state, 1000) is True

    def test_neq_exact_match_does_not_trigger(self):
        expr = CompareExpr(metric="temperature", comparator=Comparator.NEQ, threshold=50.0)
        state = _make_state("temperature", [(1000, 50.0)])
        assert evaluate_condition(expr, state, 1000) is False


class TestConsecutiveTemporal:
    def test_not_enough_readings(self):
        """Fewer than N readings → condition is false."""
        expr = CompareExpr(
            metric="temperature", comparator=Comparator.GT, threshold=80.0,
            temporal=ConsecutiveTemporal(count=3),
        )
        state = _make_state("temperature", [(1000, 85.0), (2000, 85.0)])
        assert evaluate_condition(expr, state, 2000) is False

    def test_exactly_n_readings_all_match(self):
        """Exactly N readings, all matching → trigger."""
        expr = CompareExpr(
            metric="temperature", comparator=Comparator.GT, threshold=80.0,
            temporal=ConsecutiveTemporal(count=3),
        )
        state = _make_state("temperature", [(1000, 85.0), (2000, 82.0), (3000, 81.0)])
        assert evaluate_condition(expr, state, 3000) is True

    def test_n_minus_1_then_break(self):
        """N-1 matching readings, then one not matching → false."""
        expr = CompareExpr(
            metric="temperature", comparator=Comparator.GT, threshold=80.0,
            temporal=ConsecutiveTemporal(count=3),
        )
        state = _make_state("temperature", [(1000, 85.0), (2000, 82.0), (3000, 79.0)])
        assert evaluate_condition(expr, state, 3000) is False

    def test_consecutive_with_older_non_matching(self):
        """Old non-matching readings shouldn't matter if last N all match."""
        expr = CompareExpr(
            metric="temperature", comparator=Comparator.GT, threshold=80.0,
            temporal=ConsecutiveTemporal(count=3),
        )
        state = _make_state("temperature", [
            (1000, 50.0), (2000, 60.0),  # old, non-matching
            (3000, 85.0), (4000, 82.0), (5000, 81.0),  # last 3 match
        ])
        assert evaluate_condition(expr, state, 5000) is True


class TestWindowTemporal:
    def test_within_window_enough_occurrences(self):
        expr = CompareExpr(
            metric="temperature", comparator=Comparator.GT, threshold=80.0,
            temporal=WindowTemporal(seconds=60, min_occurrences=3),
        )
        # All within 60 seconds of current time (60000ms)
        state = _make_state("temperature", [
            (10000, 85.0), (20000, 82.0), (50000, 81.0),
        ])
        assert evaluate_condition(expr, state, 60000) is True

    def test_within_window_not_enough_occurrences(self):
        expr = CompareExpr(
            metric="temperature", comparator=Comparator.GT, threshold=80.0,
            temporal=WindowTemporal(seconds=60, min_occurrences=3),
        )
        state = _make_state("temperature", [
            (10000, 85.0), (20000, 82.0), (50000, 70.0),  # third doesn't match
        ])
        assert evaluate_condition(expr, state, 60000) is False

    def test_readings_outside_window_ignored(self):
        expr = CompareExpr(
            metric="temperature", comparator=Comparator.GT, threshold=80.0,
            temporal=WindowTemporal(seconds=10, min_occurrences=2),
        )
        state = _make_state("temperature", [
            (1000, 85.0),   # outside window (current=60000, window=10s=10000ms, cutoff=50000)
            (55000, 82.0),  # inside
            (58000, 83.0),  # inside
        ])
        assert evaluate_condition(expr, state, 60000) is True


class TestLogicalExpr:
    def test_and_all_true(self):
        expr = LogicalExpr(
            operator=LogicalOperator.AND,
            conditions=[
                CompareExpr(metric="temperature", comparator=Comparator.GT, threshold=80.0),
                CompareExpr(metric="humidity", comparator=Comparator.LT, threshold=20.0),
            ],
        )
        state = DeviceRuleState(device_id="d", rule_id="r")
        state.update_buffer("temperature", 1000, 85.0)
        state.update_buffer("humidity", 1000, 15.0)
        assert evaluate_condition(expr, state, 1000) is True

    def test_and_one_false(self):
        expr = LogicalExpr(
            operator=LogicalOperator.AND,
            conditions=[
                CompareExpr(metric="temperature", comparator=Comparator.GT, threshold=80.0),
                CompareExpr(metric="humidity", comparator=Comparator.LT, threshold=20.0),
            ],
        )
        state = DeviceRuleState(device_id="d", rule_id="r")
        state.update_buffer("temperature", 1000, 85.0)
        state.update_buffer("humidity", 1000, 25.0)  # Not < 20
        assert evaluate_condition(expr, state, 1000) is False

    def test_or_one_true(self):
        expr = LogicalExpr(
            operator=LogicalOperator.OR,
            conditions=[
                CompareExpr(metric="temperature", comparator=Comparator.GT, threshold=90.0),
                CompareExpr(metric="temperature", comparator=Comparator.LT, threshold=0.0),
            ],
        )
        state = _make_state("temperature", [(1000, 95.0)])
        assert evaluate_condition(expr, state, 1000) is True

    def test_empty_buffer_returns_false(self):
        expr = CompareExpr(metric="temperature", comparator=Comparator.GT, threshold=80.0)
        state = DeviceRuleState(device_id="d", rule_id="r")
        assert evaluate_condition(expr, state, 1000) is False
