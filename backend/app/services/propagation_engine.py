"""Alarm propagation engine: propagates alarms from parent to child devices along dependency graph."""
import asyncio
import logging
import time

from app.services.dependency_manager import DependencyManager

logger = logging.getLogger(__name__)

PROPAGATION_DELAY_SECONDS = 5


class PropagationEngine:
    def __init__(self, dependency_manager: DependencyManager, alarm_manager):
        self._dep_mgr = dependency_manager
        self._alarm_manager = alarm_manager
        self._pending: dict[tuple[str, str], asyncio.Task] = {}
        self._active_derived: dict[tuple[str, str], list[str]] = {}

    async def on_alarm_event(self, event):
        device_id = event.device_id

        if getattr(event, "is_derived", False):
            return

        children = self._dep_mgr.get_children(device_id)
        if not children:
            return

        key = (event.rule_id, device_id)

        if event.event_type == "triggered":
            existing_task = self._pending.get(key)
            if existing_task and not existing_task.done():
                existing_task.cancel()
            task = asyncio.create_task(self._delayed_propagate(event, children, key))
            self._pending[key] = task

        elif event.event_type == "recovered":
            pending_task = self._pending.pop(key, None)
            if pending_task and not pending_task.done():
                pending_task.cancel()
                logger.info(
                    f"Propagation cancelled (recovered within {PROPAGATION_DELAY_SECONDS}s): "
                    f"device={device_id} rule={event.rule_id}"
                )
            else:
                await self._recover_derived(device_id, event.rule_id, event.org_id, event.group_id)

    async def _delayed_propagate(self, event, children: list[str], key: tuple[str, str]):
        try:
            await asyncio.sleep(PROPAGATION_DELAY_SECONDS)
        except asyncio.CancelledError:
            return

        self._pending.pop(key, None)
        propagated_children = []

        for child_id in children:
            derived_alarm_id = f"derived-{event.alarm_id}-{child_id}"

            derived_event = _DerivedAlarmEvent(
                alarm_id=derived_alarm_id,
                rule_id=event.rule_id,
                rule_name=f"[Derived] {event.rule_name}",
                device_id=child_id,
                org_id=event.org_id,
                group_id=event.group_id,
                event_type="triggered",
                severity=event.severity,
                values={"root_cause_device": event.device_id},
                timestamp_ms=int(time.time() * 1000),
                is_derived=True,
                root_cause_device_id=event.device_id,
                root_cause_alarm_id=event.alarm_id,
            )

            suppress = self._dep_mgr.is_suppressed(event.device_id, child_id)

            if suppress:
                await self._alarm_manager.record_only(derived_event)
            else:
                await self._alarm_manager.handle_event(derived_event)

            propagated_children.append(child_id)
            logger.info(
                f"Derived alarm propagated: parent={event.device_id} -> child={child_id} "
                f"suppress_notification={suppress}"
            )

        self._active_derived[key] = propagated_children

    async def _recover_derived(self, parent_device_id: str, rule_id: str, org_id: str, group_id: str):
        key = (rule_id, parent_device_id)
        affected_children = self._active_derived.pop(key, [])

        if not affected_children:
            return

        for child_id in affected_children:
            recovery_event = _DerivedAlarmEvent(
                alarm_id=f"derived-recover-{rule_id}-{child_id}-{int(time.time()*1000)}",
                rule_id=rule_id,
                rule_name="[Derived] Recovery",
                device_id=child_id,
                org_id=org_id,
                group_id=group_id,
                event_type="recovered",
                severity="info",
                values={"root_cause_device": parent_device_id},
                timestamp_ms=int(time.time() * 1000),
                is_derived=True,
                root_cause_device_id=parent_device_id,
                root_cause_alarm_id="",
            )

            suppress = self._dep_mgr.is_suppressed(parent_device_id, child_id)
            if suppress:
                await self._alarm_manager.record_only(recovery_event)
            else:
                await self._alarm_manager.handle_event(recovery_event)

        logger.info(
            f"Derived alarms auto-recovered: parent={parent_device_id} "
            f"children={len(affected_children)} rule={rule_id}"
        )


class _DerivedAlarmEvent:
    """Lightweight alarm event object compatible with AlarmManager.handle_event."""

    __slots__ = (
        "alarm_id", "rule_id", "rule_name", "device_id", "org_id", "group_id",
        "event_type", "severity", "values", "timestamp_ms",
        "is_derived", "root_cause_device_id", "root_cause_alarm_id",
    )

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
