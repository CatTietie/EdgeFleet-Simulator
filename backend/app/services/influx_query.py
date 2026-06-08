import logging
from datetime import datetime

from influxdb_client.client.influxdb_client_async import InfluxDBClientAsync

from app.config import settings

logger = logging.getLogger(__name__)


class InfluxQueryService:
    def __init__(self):
        self._client: InfluxDBClientAsync | None = None
        self._query_api = None

    async def start(self):
        self._client = InfluxDBClientAsync(
            url=settings.influxdb_url,
            token=settings.influxdb_token,
            org=settings.influxdb_org,
        )
        self._query_api = self._client.query_api()

    async def get_latest(self, org_id: str, device_id: str) -> dict | None:
        query = f'''
from(bucket: "{settings.influxdb_bucket}")
  |> range(start: -5m)
  |> filter(fn: (r) => r.org_id == "{org_id}")
  |> filter(fn: (r) => r.device_id == "{device_id}")
  |> last()
'''
        tables = await self._query_api.query(query)
        if not tables:
            return None

        metrics = {}
        timestamp = None
        for table in tables:
            for record in table.records:
                metrics[record.get_field()] = record.get_value()
                if timestamp is None:
                    timestamp = record.get_time()

        return {
            "device_id": device_id,
            "timestamp": timestamp.isoformat() if timestamp else None,
            "metrics": metrics,
        }

    async def get_time_series(
        self,
        org_id: str,
        device_id: str,
        metric: str = "temperature",
        range_start: str = "-1h",
        aggregate_window: str = "1m",
    ) -> list[dict]:
        query = f'''
from(bucket: "{settings.influxdb_bucket}")
  |> range(start: {range_start})
  |> filter(fn: (r) => r.org_id == "{org_id}")
  |> filter(fn: (r) => r.device_id == "{device_id}")
  |> filter(fn: (r) => r._field == "{metric}")
  |> aggregateWindow(every: {aggregate_window}, fn: mean, createEmpty: false)
  |> yield(name: "mean")
'''
        tables = await self._query_api.query(query)
        results = []
        for table in tables:
            for record in table.records:
                results.append({
                    "timestamp": record.get_time().isoformat(),
                    "value": record.get_value(),
                })
        return results

    async def get_group_summary(
        self,
        org_id: str,
        group_id: str,
        range_start: str = "-5m",
    ) -> list[dict]:
        query = f'''
from(bucket: "{settings.influxdb_bucket}")
  |> range(start: {range_start})
  |> filter(fn: (r) => r.org_id == "{org_id}")
  |> filter(fn: (r) => r.group_id == "{group_id}")
  |> last()
  |> group(columns: ["device_id"])
'''
        tables = await self._query_api.query(query)
        devices = {}
        for table in tables:
            for record in table.records:
                did = record.values.get("device_id", "unknown")
                if did not in devices:
                    devices[did] = {"device_id": did, "metrics": {}}
                devices[did]["metrics"][record.get_field()] = record.get_value()
        return list(devices.values())

    async def stop(self):
        if self._client:
            await self._client.close()
