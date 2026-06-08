"""Async webhook dispatcher with retry logic."""
import asyncio
import logging
from datetime import datetime, timezone

import aiohttp
import orjson

logger = logging.getLogger(__name__)

MAX_CONCURRENT = 50
MAX_RETRIES = 3
RETRY_DELAYS = [1, 2, 4]  # seconds


class WebhookDispatcher:
    def __init__(self):
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT)
        self._session: aiohttp.ClientSession | None = None
        self._dispatch_count = 0
        self._failure_count = 0

    async def start(self):
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=10),
            json_serialize=lambda x: orjson.dumps(x).decode(),
        )

    async def dispatch(self, event):
        """Dispatch alarm event to all configured webhook URLs."""
        from app.services.rule_engine import AlarmEvent

        if not hasattr(event, "rule_id"):
            return

        # Look up webhook URLs from rule (stored in alarm manager context)
        # For now, we get URLs from the engine's rule registry
        urls = self._get_webhook_urls(event)
        if not urls:
            return

        payload = {
            "alarm_id": event.alarm_id,
            "rule_id": event.rule_id,
            "rule_name": event.rule_name,
            "device_id": event.device_id,
            "org_id": event.org_id,
            "group_id": event.group_id,
            "event_type": event.event_type,
            "severity": event.severity,
            "values": event.values,
            "message": f"{event.rule_name} {event.event_type} on {event.device_id}",
            "triggered_at": datetime.fromtimestamp(
                event.timestamp_ms / 1000, tz=timezone.utc
            ).isoformat(),
            "recovered_at": None,
        }

        for url in urls:
            asyncio.create_task(self._dispatch_single(url, payload))

    async def _dispatch_single(self, url: str, payload: dict):
        async with self._semaphore:
            for attempt in range(MAX_RETRIES):
                try:
                    async with self._session.post(
                        url,
                        json=payload,
                        headers={"Content-Type": "application/json"},
                    ) as resp:
                        if resp.status < 300:
                            self._dispatch_count += 1
                            return
                        logger.warning(
                            f"Webhook {url} returned {resp.status} (attempt {attempt+1})"
                        )
                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    logger.warning(f"Webhook {url} failed (attempt {attempt+1}): {e}")

                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAYS[attempt])

            self._failure_count += 1
            logger.error(f"Webhook {url} failed after {MAX_RETRIES} retries")

    def _get_webhook_urls(self, event) -> list[str]:
        # This will be connected to the rule registry
        # For now, return from a class-level registry
        return getattr(event, "_webhook_urls", [])

    def set_rule_urls(self, rule_id: str, urls: list[str]):
        """Store webhook URLs for a rule (called when rules are loaded)."""
        if not hasattr(self, "_rule_urls"):
            self._rule_urls = {}
        self._rule_urls[rule_id] = urls

    async def stop(self):
        if self._session:
            await self._session.close()

    @property
    def stats(self) -> dict:
        return {
            "dispatched": self._dispatch_count,
            "failures": self._failure_count,
        }
