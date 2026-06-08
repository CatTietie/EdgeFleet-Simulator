"""Unit tests for the device-rule state machine transitions."""
import pytest
from app.rule_dsl.models import AlarmState
from app.rule_dsl.state_machine import DeviceRuleState, StateStore, STALE_TIMEOUT_MS


class TestDeviceRuleState:
    def test_initial_state_is_normal(self):
        state = DeviceRuleState(device_id="d1", rule_id="r1")
        assert state.current_state == AlarmState.NORMAL

    def test_trigger_sets_alarm(self):
        state = DeviceRuleState(device_id="d1", rule_id="r1")
        state.trigger(current_time_ms=10000, cooldown_seconds=60)
        assert state.current_state == AlarmState.ALARM
        assert state.last_triggered_at_ms == 10000
        assert state.cooldown_until_ms == 10000 + 60000

    def test_recover_sets_normal(self):
        state = DeviceRuleState(device_id="d1", rule_id="r1")
        state.trigger(current_time_ms=10000, cooldown_seconds=60)
        state.recover()
        assert state.current_state == AlarmState.NORMAL

    def test_cooldown_prevents_retrigger(self):
        state = DeviceRuleState(device_id="d1", rule_id="r1")
        state.trigger(current_time_ms=10000, cooldown_seconds=60)
        state.recover()
        assert state.is_in_cooldown(20000) is True
        assert state.is_in_cooldown(70001) is False

    def test_buffer_update(self):
        state = DeviceRuleState(device_id="d1", rule_id="r1")
        state.update_buffer("temperature", 1000, 25.0)
        state.update_buffer("temperature", 2000, 26.0)
        buf = state.get_buffer("temperature")
        assert len(buf) == 2
        assert buf[-1] == (2000, 26.0)

    def test_stale_buffer_clears(self):
        state = DeviceRuleState(device_id="d1", rule_id="r1")
        state.update_buffer("temperature", 1000, 25.0)
        state.update_buffer("temperature", 2000, 26.0)
        # Jump far into the future past stale timeout from LAST write (2000)
        state.update_buffer("temperature", 2000 + STALE_TIMEOUT_MS + 1, 30.0)
        buf = state.get_buffer("temperature")
        # Buffer was cleared then new value added
        assert len(buf) == 1
        assert buf[0][1] == 30.0

    def test_false_streak_increment(self):
        state = DeviceRuleState(device_id="d1", rule_id="r1")
        state.trigger(current_time_ms=10000, cooldown_seconds=60)
        state.increment_false_streak()
        state.increment_false_streak()
        assert state.false_streak == 2
        state.recover()
        assert state.false_streak == 0


class TestStateStore:
    def test_get_or_create(self):
        store = StateStore()
        s1 = store.get_or_create("d1", "r1")
        s2 = store.get_or_create("d1", "r1")
        assert s1 is s2
        assert store.size == 1

    def test_different_keys(self):
        store = StateStore()
        store.get_or_create("d1", "r1")
        store.get_or_create("d1", "r2")
        store.get_or_create("d2", "r1")
        assert store.size == 3

    def test_remove_rule(self):
        store = StateStore()
        s1 = store.get_or_create("d1", "r1")
        s2 = store.get_or_create("d2", "r1")
        s2.trigger(1000, 60)
        alarmed = store.remove_rule("r1")
        assert store.size == 0
        assert len(alarmed) == 1
        assert alarmed[0].device_id == "d2"

    def test_get_all_for_device(self):
        store = StateStore()
        store.get_or_create("d1", "r1")
        store.get_or_create("d1", "r2")
        store.get_or_create("d2", "r1")
        results = store.get_all_for_device("d1")
        assert len(results) == 2
