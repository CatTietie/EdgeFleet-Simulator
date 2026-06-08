import asyncio
import logging
import time
from dataclasses import dataclass, field

from influxdb_client import Point
from influxdb_client.client.influxdb_client_async import InfluxDBClientAsync

from app.config import settings

logger = logging.getLogger(__name__)


class InfluxWriter:
    def __init__(self):
        self._client: InfluxDBClientAsync | None = None
        self._write_api = None
        self._buffer: list[Point] = []
        self._flush_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    async def start(self):
        self._client = InfluxDBClientAsync(
            url=settings.influxdb_url,
            token=settings.influxdb_token,
            org=settings.influxdb_org,
        )
        self._write_api = self._client.write_api()
        self._flush_task = asyncio.create_task(self._periodic_flush())
        logger.info("InfluxDB writer started")

    async def write_point(self, data_point: dict):
        point = (
            Point("sensor_data")
            .tag("org_id", data_point["org_id"])
            .tag("group_id", data_point["group_id"])
            .tag("device_id", data_point["device_id"])
            .time(data_point["timestamp"] * 1_000_000)  # ms to ns
        )
        for metric_name, value in data_point["metrics"].items():
            point = point.field(metric_name, float(value))

        async with self._lock:
            self._buffer.append(point)
            if len(self._buffer) >= settings.influx_batch_size:
                await self._flush()

    async def _periodic_flush(self):
        while True:
            await asyncio.sleep(settings.influx_flush_interval_ms / 1000.0)
            async with self._lock:
                if self._buffer:
                    await self._flush()

    async def _flush(self):
        if not self._buffer:
            return
        points = self._buffer[:]
        self._buffer.clear()
        try:
            await self._write_api.write(
                bucket=settings.influxdb_bucket,
                record=points,
            )
        except Exception as e:
            logger.error(f"InfluxDB write failed ({len(points)} points): {e}")
            # Re-add points to buffer for retry (with a cap)
            async with self._lock:
                self._buffer = points[:1000] + self._buffer

    async def stop(self):
        if self._flush_task:
            self._flush_task.cancel()
        async with self._lock:
            if self._buffer:
                await self._flush()
        if self._client:
            await self._client.close()
