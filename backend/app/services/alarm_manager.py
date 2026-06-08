"""Alarm manager: handles alarm events, persists history, dispatches webhooks."""
import asyncio
import logging

import redis.asyncio as aioredis
import orjson

from app.config import settings

logger = logging.getLogger(__name__)


class AlarmManager:
    def __init__(self, webhook_dispatcher, redis_client: aioredis.Redis | None = None):
        self.webhook_dispatcher = webhook_dispatcher
        self.redis = redis_client
        self._event_history: list[dict] = []

    async def handle_event(self, event):
        """Process an alarm event: persist, publish to Redis, dispatch webhook."""
        event_dict = {
            "alarm_id": event.alarm_id,
            "rule_id": event.rule_id,
            "rule_name": event.rule_name,
            "device_id": event.device_id,
            "org_id": event.org_id,
            "group_id": event.group_id,
            "event_type": event.event_type,
            "severity": event.severity,
            "values": event.values,
            "timestamp_ms": event.timestamp_ms,
        }

        self._event_history.append(event_dict)
        if len(self._event_history) > 10000:
            self._event_history = self._event_history[-5000:]

        logger.info(
            f"Alarm {event.event_type}: rule={event.rule_id} "
            f"device={event.device_id} severity={event.severity}"
        )

        # Publish to Redis for WebSocket fan-out
        if self.redis:
            channel = f"ws:org:{event.org_id}"
            payload = orjson.dumps({
                "type": "alarm_event",
                "data": event_dict,
            })
            try:
                await self.redis.publish(channel, payload)
            except Exception as e:
                logger.error(f"Redis publish failed: {e}")

        # Dispatch webhooks
        await self.webhook_dispatcher.dispatch(event)

    def get_recent_events(self, org_id: str, limit: int = 50) -> list[dict]:
        events = [e for e in self._event_history if e["org_id"] == org_id]
        return events[-limit:]

    def get_active_alarms(self, org_id: str) -> list[dict]:
        # Track triggered events without matching recovery
        active = {}
        for event in self._event_history:
            if event["org_id"] != org_id:
                continue
            key = (event["rule_id"], event["device_id"])
            if event["event_type"] == "triggered":
                active[key] = event
            elif event["event_type"] == "recovered":
                active.pop(key, None)
        return list(active.values())
