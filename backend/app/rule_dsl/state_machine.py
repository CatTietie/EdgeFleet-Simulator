"""Per-(device, rule) state machine with ring buffers."""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field

from app.rule_dsl.models import AlarmState

BUFFER_MAX_LEN = 100
STALE_TIMEOUT_MS = 60_000


@dataclass
class DeviceRuleState:
    device_id: str
    rule_id: str
    current_state: AlarmState = AlarmState.NORMAL
    buffers: dict[str, deque] = field(default_factory=dict)
    last_data_time_ms: int = 0
    last_triggered_at_ms: int = 0
    cooldown_until_ms: int = 0
    false_streak: int = 0

    def get_buffer(self, metric: str) -> deque | None:
        return self.buffers.get(metric)

    def update_buffer(self, metric: str, timestamp_ms: int, value: float):
        if metric not in self.buffers:
            self.buffers[metric] = deque(maxlen=BUFFER_MAX_LEN)

        # Check staleness: if last data was too long ago, reset buffers
        if self.last_data_time_ms > 0 and (timestamp_ms - self.last_data_time_ms) > STALE_TIMEOUT_MS:
            self.buffers[metric].clear()

        self.buffers[metric].append((timestamp_ms, value))
        self.last_data_time_ms = timestamp_ms

    def is_in_cooldown(self, current_time_ms: int) -> bool:
        return current_time_ms < self.cooldown_until_ms

    def trigger(self, current_time_ms: int, cooldown_seconds: int):
        self.current_state = AlarmState.ALARM
        self.last_triggered_at_ms = current_time_ms
        self.cooldown_until_ms = current_time_ms + (cooldown_seconds * 1000)
        self.false_streak = 0

    def recover(self):
        self.current_state = AlarmState.NORMAL
        self.false_streak = 0

    def increment_false_streak(self):
        self.false_streak += 1


DEFAULT_RECOVERY_FALSE_STREAK = 5


class StateStore:
    """In-memory store for all (device_id, rule_id) state pairs."""

    def __init__(self):
        self._states: dict[tuple[str, str], DeviceRuleState] = {}

    def get_or_create(self, device_id: str, rule_id: str) -> DeviceRuleState:
        key = (device_id, rule_id)
        if key not in self._states:
            self._states[key] = DeviceRuleState(device_id=device_id, rule_id=rule_id)
        return self._states[key]

    def remove_rule(self, rule_id: str) -> list[DeviceRuleState]:
        """Remove all states for a rule. Returns states that were in ALARM."""
        alarmed = []
        keys_to_remove = [k for k in self._states if k[1] == rule_id]
        for key in keys_to_remove:
            state = self._states.pop(key)
            if state.current_state == AlarmState.ALARM:
                alarmed.append(state)
        return alarmed

    def get_all_for_device(self, device_id: str) -> list[DeviceRuleState]:
        return [s for k, s in self._states.items() if k[0] == device_id]

    @property
    def size(self) -> int:
        return len(self._states)
