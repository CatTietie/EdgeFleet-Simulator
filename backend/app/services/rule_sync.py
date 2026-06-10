"""Redis Pub/Sub-based rule sync for multi-instance deployments."""
import asyncio
import logging

import orjson
import redis.asyncio as aioredis

from app.rule_dsl.parser import parse_rule, RuleParseError

logger = logging.getLogger(__name__)


class RuleSyncService:
    def __init__(self, redis_client: aioredis.Redis | None, rule_engine, state_persistence, instance_id: str):
        self._redis = redis_client
        self._rule_engine = rule_engine
        self._state_persistence = state_persistence
        self._instance_id = instance_id

    async def publish_rule_change(self, org_id: str, rule_id: str, action: str, rule_data: dict | None, old_rule_data: dict | None = None):
        if not self._redis:
            return
        try:
            payload = orjson.dumps({
                "instance_id": self._instance_id,
                "action": action,
                "rule_id": rule_id,
                "org_id": org_id,
                "rule_data": rule_data,
                "old_rule_data": old_rule_data,
            })
            await self._redis.publish(f"rule:org:{org_id}", payload)
        except Exception as e:
            logger.warning(f"Rule sync publish failed: {e}")

    async def start_subscriber(self):
        if not self._redis:
            return
        while True:
            try:
                pubsub = self._redis.pubsub()
                await pubsub.psubscribe("rule:org:*")
                logger.info("Rule sync subscriber started")
                async for message in pubsub.listen():
                    if message["type"] != "pmessage":
                        continue
                    try:
                        data = orjson.loads(message["data"])
                        if data.get("instance_id") == self._instance_id:
                            continue
                        await self._handle_change(data)
                    except Exception as e:
                        logger.error(f"Rule sync message handling error: {e}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Rule sync subscriber error: {e}, reconnecting in 5s...")
                await asyncio.sleep(5)

    async def _handle_change(self, data: dict):
        action = data["action"]
        rule_id = data["rule_id"]
        org_id = data.get("org_id", "")
        rule_data = data.get("rule_data")

        if action == "deleted":
            self._rule_engine.unregister_rule(rule_id)
            if org_id:
                await self._state_persistence.clear_rule(org_id, rule_id)
            logger.info(f"Rule sync: deleted rule {rule_id}")

        elif action == "created" and rule_data:
            try:
                parsed = parse_rule(rule_data)
                self._rule_engine.register_rule(parsed)
                logger.info(f"Rule sync: created rule {rule_id}")
            except RuleParseError as e:
                logger.error(f"Rule sync: failed to parse created rule {rule_id}: {e}")

        elif action == "updated" and rule_data:
            try:
                parsed = parse_rule(rule_data)
                old_rule_data = data.get("old_rule_data")
                new_rule_data = {
                    "trigger_condition": rule_data["trigger_condition"],
                    "recovery_condition": rule_data.get("recovery_condition"),
                    "target": rule_data["target"],
                }
                if old_rule_data:
                    await self._rule_engine.hot_reload_rule(old_rule_data, new_rule_data, parsed, org_id)
                else:
                    # Fallback: no old data available, do silent replace
                    self._rule_engine._remove_rule_silent(rule_id)
                    await self._state_persistence.clear_rule(org_id, rule_id)
                    self._rule_engine.register_rule(parsed)
                logger.info(f"Rule sync: updated rule {rule_id}")
            except RuleParseError as e:
                logger.error(f"Rule sync: failed to parse updated rule {rule_id}: {e}")
