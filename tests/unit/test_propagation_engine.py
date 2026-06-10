"""Unit tests for PropagationEngine: 5s delay, cancel, auto-recovery, suppression, 1-layer-only."""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.propagation_engine import PropagationEngine, PROPAGATION_DELAY_SECONDS


class FakeAlarmEvent:
    def __init__(self, alarm_id, rule_id, rule_name, device_id, org_id, group_id,
                 event_type, severity, values, timestamp_ms, is_derived=False):
        self.alarm_id = alarm_id
        self.rule_id = rule_id
        self.rule_name = rule_name
        self.device_id = device_id
        self.org_id = org_id
        self.group_id = group_id
        self.event_type = event_type
        self.severity = severity
        self.values = values
        self.timestamp_ms = timestamp_ms
        self.is_derived = is_derived


def make_trigger_event(device_id="gw-1", rule_id="rule-1"):
    return FakeAlarmEvent(
        alarm_id=f"alm-{rule_id}-{device_id}-1000",
        rule_id=rule_id,
        rule_name="High Temp",
        device_id=device_id,
        org_id="org-1",
        group_id="group-1",
        event_type="triggered",
        severity="critical",
        values={"temperature": 80.0},
        timestamp_ms=1000,
    )


def make_recovery_event(device_id="gw-1", rule_id="rule-1"):
    return FakeAlarmEvent(
        alarm_id=f"alm-{rule_id}-{device_id}-2000",
        rule_id=rule_id,
        rule_name="High Temp",
        device_id=device_id,
        org_id="org-1",
        group_id="group-1",
        event_type="recovered",
        severity="critical",
        values={},
        timestamp_ms=2000,
    )


@pytest.fixture
def dep_mgr():
    mgr = MagicMock()
    mgr.get_children.return_value = ["sensor-1", "sensor-2"]
    mgr.is_suppressed.return_value = False
    return mgr


@pytest.fixture
def alarm_mgr():
    mgr = MagicMock()
    mgr.handle_event = AsyncMock()
    mgr.record_only = AsyncMock()
    return mgr


@pytest.fixture
def engine(dep_mgr, alarm_mgr):
    return PropagationEngine(dep_mgr, alarm_mgr)


@pytest.mark.asyncio
async def test_propagation_after_delay(engine, alarm_mgr):
    """Trigger parent alarm, after 5s children should get derived alarms."""
    event = make_trigger_event()

    with patch("app.services.propagation_engine.PROPAGATION_DELAY_SECONDS", 0.1):
        await engine.on_alarm_event(event)
        await asyncio.sleep(0.2)

    assert alarm_mgr.handle_event.call_count == 2
    for call in alarm_mgr.handle_event.call_args_list:
        derived = call[0][0]
        assert derived.is_derived is True
        assert derived.root_cause_device_id == "gw-1"
        assert derived.event_type == "triggered"


@pytest.mark.asyncio
async def test_recovery_within_delay_cancels_propagation(engine, alarm_mgr):
    """If parent recovers within 5s, no derived alarms should fire."""
    trigger = make_trigger_event()
    recovery = make_recovery_event()

    with patch("app.services.propagation_engine.PROPAGATION_DELAY_SECONDS", 0.5):
        await engine.on_alarm_event(trigger)
        await asyncio.sleep(0.1)
        await engine.on_alarm_event(recovery)
        await asyncio.sleep(0.6)

    # No handle_event calls for derived alarms (recovery happens immediately but
    # derived alarms were never created)
    assert alarm_mgr.handle_event.call_count == 0


@pytest.mark.asyncio
async def test_auto_recovery_on_parent_recovery(engine, dep_mgr, alarm_mgr):
    """After propagation, parent recovery should auto-recover derived alarms."""
    trigger = make_trigger_event()
    recovery = make_recovery_event()

    with patch("app.services.propagation_engine.PROPAGATION_DELAY_SECONDS", 0.1):
        await engine.on_alarm_event(trigger)
        await asyncio.sleep(0.2)

    # 2 derived triggered alarms
    assert alarm_mgr.handle_event.call_count == 2
    alarm_mgr.handle_event.reset_mock()

    # Now parent recovers
    await engine.on_alarm_event(recovery)
    await asyncio.sleep(0.1)

    # Should have 2 recovery events for children
    assert alarm_mgr.handle_event.call_count == 2
    for call in alarm_mgr.handle_event.call_args_list:
        derived = call[0][0]
        assert derived.event_type == "recovered"
        assert derived.is_derived is True


@pytest.mark.asyncio
async def test_notification_suppression(engine, dep_mgr, alarm_mgr):
    """When suppress=True, use record_only instead of handle_event."""
    dep_mgr.is_suppressed.return_value = True
    event = make_trigger_event()

    with patch("app.services.propagation_engine.PROPAGATION_DELAY_SECONDS", 0.1):
        await engine.on_alarm_event(event)
        await asyncio.sleep(0.2)

    assert alarm_mgr.handle_event.call_count == 0
    assert alarm_mgr.record_only.call_count == 2


@pytest.mark.asyncio
async def test_only_direct_children_propagated(engine, dep_mgr, alarm_mgr):
    """Only direct children (1 layer) receive derived alarms, not grandchildren."""
    # gw-1 has children [sensor-1, sensor-2]
    # Even if sensor-1 has its own children, they should NOT be propagated to
    dep_mgr.get_children.side_effect = lambda d: ["sensor-1", "sensor-2"] if d == "gw-1" else ["sensor-3"]

    event = make_trigger_event()

    with patch("app.services.propagation_engine.PROPAGATION_DELAY_SECONDS", 0.1):
        await engine.on_alarm_event(event)
        await asyncio.sleep(0.2)

    # Only 2 calls (for sensor-1, sensor-2), not 3
    assert alarm_mgr.handle_event.call_count == 2
    devices_alarmed = {call[0][0].device_id for call in alarm_mgr.handle_event.call_args_list}
    assert devices_alarmed == {"sensor-1", "sensor-2"}


@pytest.mark.asyncio
async def test_derived_alarm_fields(engine, alarm_mgr):
    """Verify derived alarm has all required root cause fields."""
    event = make_trigger_event()

    with patch("app.services.propagation_engine.PROPAGATION_DELAY_SECONDS", 0.1):
        await engine.on_alarm_event(event)
        await asyncio.sleep(0.2)

    derived = alarm_mgr.handle_event.call_args_list[0][0][0]
    assert derived.is_derived is True
    assert derived.root_cause_device_id == "gw-1"
    assert derived.root_cause_alarm_id == event.alarm_id
    assert derived.rule_name.startswith("[Derived]")
    assert derived.severity == "critical"


@pytest.mark.asyncio
async def test_ignores_derived_events(engine, dep_mgr, alarm_mgr):
    """PropagationEngine should not re-propagate derived alarms."""
    event = FakeAlarmEvent(
        alarm_id="derived-alm-1",
        rule_id="rule-1",
        rule_name="[Derived] High Temp",
        device_id="sensor-1",
        org_id="org-1",
        group_id="group-1",
        event_type="triggered",
        severity="critical",
        values={},
        timestamp_ms=1000,
        is_derived=True,
    )

    await engine.on_alarm_event(event)
    await asyncio.sleep(0.1)

    assert alarm_mgr.handle_event.call_count == 0
    assert alarm_mgr.record_only.call_count == 0


@pytest.mark.asyncio
async def test_concurrent_trigger_cancels_previous_pending(engine, dep_mgr, alarm_mgr):
    """Rapid re-trigger on the same rule must cancel the previous pending task, not duplicate."""
    event1 = make_trigger_event()
    event2 = FakeAlarmEvent(
        alarm_id="alm-rule-1-gw-1-3000",
        rule_id="rule-1",
        rule_name="High Temp",
        device_id="gw-1",
        org_id="org-1",
        group_id="group-1",
        event_type="triggered",
        severity="critical",
        values={"temperature": 90.0},
        timestamp_ms=3000,
    )

    with patch("app.services.propagation_engine.PROPAGATION_DELAY_SECONDS", 0.3):
        await engine.on_alarm_event(event1)
        await asyncio.sleep(0.1)
        # Second trigger before the first 0.3s delay expires
        await engine.on_alarm_event(event2)
        # Wait for the second task to complete
        await asyncio.sleep(0.4)

    # Only 2 derived alarms (from event2), not 4 (event1 was cancelled)
    assert alarm_mgr.handle_event.call_count == 2
    for call in alarm_mgr.handle_event.call_args_list:
        derived = call[0][0]
        assert derived.root_cause_alarm_id == event2.alarm_id


@pytest.mark.asyncio
async def test_recovery_only_targets_propagated_children(dep_mgr, alarm_mgr):
    """Recovery must only target children that actually received derived alarms,
    not all current children in the dependency graph."""
    # Initially gw-1 has children [sensor-1, sensor-2]
    dep_mgr.get_children.return_value = ["sensor-1", "sensor-2"]
    engine = PropagationEngine(dep_mgr, alarm_mgr)

    trigger = make_trigger_event()

    with patch("app.services.propagation_engine.PROPAGATION_DELAY_SECONDS", 0.1):
        await engine.on_alarm_event(trigger)
        await asyncio.sleep(0.2)

    assert alarm_mgr.handle_event.call_count == 2
    alarm_mgr.handle_event.reset_mock()

    # After propagation, a new child is added to the dependency graph
    dep_mgr.get_children.return_value = ["sensor-1", "sensor-2", "sensor-3"]

    # Parent recovers
    recovery = make_recovery_event()
    await engine.on_alarm_event(recovery)
    await asyncio.sleep(0.1)

    # Should only recover sensor-1 and sensor-2 (the propagated set), NOT sensor-3
    assert alarm_mgr.handle_event.call_count == 2
    recovered_devices = {call[0][0].device_id for call in alarm_mgr.handle_event.call_args_list}
    assert recovered_devices == {"sensor-1", "sensor-2"}


@pytest.mark.asyncio
async def test_recovery_with_no_active_derived_is_noop(engine, dep_mgr, alarm_mgr):
    """If parent recovers but has no active derived alarms (e.g. was cancelled in time),
    no recovery events should be sent."""
    trigger = make_trigger_event()
    recovery = make_recovery_event()

    with patch("app.services.propagation_engine.PROPAGATION_DELAY_SECONDS", 0.5):
        await engine.on_alarm_event(trigger)
        await asyncio.sleep(0.1)
        # Recovery cancels the pending propagation
        await engine.on_alarm_event(recovery)

    await asyncio.sleep(0.1)
    # Nothing was propagated, nothing to recover
    assert alarm_mgr.handle_event.call_count == 0
