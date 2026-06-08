import asyncio
import logging
import time
from collections import deque

import aiomqtt
import orjson

from app.config import settings

logger = logging.getLogger(__name__)

DEDUP_WINDOW_SECONDS = 60


class MqttIngestionService:
    def __init__(self, influx_writer, rule_engine, ws_publisher):
        self.influx_writer = influx_writer
        self.rule_engine = rule_engine
        self.ws_publisher = ws_publisher
        self._running = False
        self._seen: dict[tuple[str, int], float] = {}
        self._cleanup_counter = 0

    def _parse_topic(self, topic: str) -> dict | None:
        """Parse topic: edgefleet/{org_id}/{group_id}/{device_id}/{channel}"""
        parts = str(topic).split("/")
        if len(parts) != 5 or parts[0] != "edgefleet":
            return None
        return {
            "org_id": parts[1],
            "group_id": parts[2],
            "device_id": parts[3],
            "channel": parts[4],
        }

    def _is_duplicate(self, device_id: str, seq: int) -> bool:
        key = (device_id, seq)
        now = time.time()
        if key in self._seen:
            return True
        self._seen[key] = now
        self._cleanup_counter += 1
        if self._cleanup_counter >= 1000:
            self._cleanup_counter = 0
            cutoff = now - DEDUP_WINDOW_SECONDS
            self._seen = {k: v for k, v in self._seen.items() if v > cutoff}
        return False

    async def start(self):
        self._running = True
        logger.info(f"Connecting to MQTT broker at {settings.mqtt_broker_host}:{settings.mqtt_broker_port}")

        while self._running:
            try:
                async with aiomqtt.Client(
                    hostname=settings.mqtt_broker_host,
                    port=settings.mqtt_broker_port,
                    username=settings.mqtt_username,
                    password=settings.mqtt_password,
                ) as client:
                    await client.subscribe("edgefleet/+/+/+/telemetry", qos=0)
                    await client.subscribe("edgefleet/+/+/+/status", qos=1)
                    logger.info("Subscribed to telemetry and status topics")

                    async for message in client.messages:
                        await self._handle_message(message)

            except aiomqtt.MqttError as e:
                if self._running:
                    logger.error(f"MQTT connection lost: {e}. Reconnecting in 5s...")
                    await asyncio.sleep(5)

    async def _handle_message(self, message):
        topic_info = self._parse_topic(message.topic)
        if not topic_info:
            return

        try:
            payload = orjson.loads(message.payload)
        except (orjson.JSONDecodeError, TypeError):
            logger.warning(f"Invalid JSON payload on topic {message.topic}")
            return

        channel = topic_info["channel"]

        if channel == "telemetry":
            await self._handle_telemetry(topic_info, payload)
        elif channel == "status":
            await self._handle_status(topic_info, payload)

    async def _handle_telemetry(self, topic_info: dict, payload: dict):
        device_id = payload.get("device_id", topic_info["device_id"])
        seq = payload.get("seq", 0)

        if self._is_duplicate(device_id, seq):
            return

        data_point = {
            "org_id": topic_info["org_id"],
            "group_id": topic_info["group_id"],
            "device_id": device_id,
            "timestamp": payload.get("timestamp", int(time.time() * 1000)),
            "metrics": payload.get("metrics", {}),
        }

        await self.influx_writer.write_point(data_point)

        await self.rule_engine.evaluate(data_point)

        if self.ws_publisher:
            await self.ws_publisher.publish_telemetry(data_point)

    async def _handle_status(self, topic_info: dict, payload: dict):
        status_event = {
            "org_id": topic_info["org_id"],
            "group_id": topic_info["group_id"],
            "device_id": payload.get("device_id", topic_info["device_id"]),
            "status": payload.get("status", "unknown"),
            "timestamp": payload.get("timestamp", int(time.time() * 1000)),
        }

        if self.ws_publisher:
            await self.ws_publisher.publish_status(status_event)

    def stop(self):
        self._running = False
