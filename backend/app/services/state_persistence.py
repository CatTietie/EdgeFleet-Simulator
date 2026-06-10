"""Redis-backed checkpoint for alert state persistence."""
import logging

import orjson
import redis.asyncio as aioredis

from app.rule_dsl.state_machine import DeviceRuleState

logger = logging.getLogger(__name__)


class StatePersistence:
    def __init__(self, redis_client: aioredis.Redis | None):
        self._redis = redis_client

    def _key(self, org_id: str, rule_id: str) -> str:
        return f"alert_state:{org_id}:{rule_id}"

    async def checkpoint(self, org_id: str, rule_id: str, device_id: str, state: DeviceRuleState):
        if not self._redis:
            return
        try:
            data = orjson.dumps(state.to_checkpoint_dict())
            await self._redis.hset(self._key(org_id, rule_id), device_id, data)
        except Exception as e:
            logger.warning(f"State checkpoint failed for {rule_id}/{device_id}: {e}")

    async def restore_rule(self, org_id: str, rule_id: str) -> dict[str, DeviceRuleState]:
        if not self._redis:
            return {}
        try:
            raw = await self._redis.hgetall(self._key(org_id, rule_id))
            states = {}
            for device_id_bytes, data_bytes in raw.items():
                device_id = device_id_bytes.decode() if isinstance(device_id_bytes, bytes) else device_id_bytes
                data = orjson.loads(data_bytes)
                states[device_id] = DeviceRuleState.from_checkpoint_dict(device_id, rule_id, data)
            return states
        except Exception as e:
            logger.warning(f"State restore failed for rule {rule_id}: {e}")
            return {}

    async def clear_rule(self, org_id: str, rule_id: str):
        if not self._redis:
            return
        try:
            await self._redis.delete(self._key(org_id, rule_id))
        except Exception as e:
            logger.warning(f"State clear failed for rule {rule_id}: {e}")
