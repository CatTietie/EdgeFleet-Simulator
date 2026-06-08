import asyncio
import time
import logging
from contextlib import asynccontextmanager

import aiomqtt
import orjson

from .device_factory import VirtualDevice

logger = logging.getLogger(__name__)


class MqttPublisher:
    def __init__(
        self,
        broker_host: str,
        broker_port: int,
        username: str,
        password: str,
        interval: float = 5.0,
    ):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.username = username
        self.password = password
        self.interval = interval
        self._running = False

    def _build_topic(self, device: VirtualDevice) -> str:
        return f"edgefleet/{device.org_id}/{device.group_id}/{device.device_id}/telemetry"

    async def publish_loop(self, devices: list[VirtualDevice]):
        """Continuously publish telemetry for all devices."""
        self._running = True
        logger.info(
            f"Starting publish loop for {len(devices)} devices "
            f"to {self.broker_host}:{self.broker_port} every {self.interval}s"
        )

        async with aiomqtt.Client(
            hostname=self.broker_host,
            port=self.broker_port,
            username=self.username,
            password=self.password,
        ) as client:
            # Send initial status for all devices
            for device in devices:
                status_topic = f"edgefleet/{device.org_id}/{device.group_id}/{device.device_id}/status"
                status_payload = orjson.dumps({
                    "device_id": device.device_id,
                    "timestamp": int(time.time() * 1000),
                    "status": "online",
                })
                await client.publish(status_topic, status_payload, qos=1, retain=True)

            logger.info("All devices reported online status")

            while self._running:
                start = time.time()
                tasks = []
                for device in devices:
                    reading = device.read()
                    reading["timestamp"] = int(time.time() * 1000)
                    topic = self._build_topic(device)
                    payload = orjson.dumps(reading)
                    tasks.append(client.publish(topic, payload, qos=0))

                await asyncio.gather(*tasks)
                elapsed = time.time() - start
                sleep_time = max(0, self.interval - elapsed)
                if elapsed > self.interval:
                    logger.warning(
                        f"Publish cycle took {elapsed:.2f}s, exceeding interval {self.interval}s"
                    )
                await asyncio.sleep(sleep_time)

    def stop(self):
        self._running = False
