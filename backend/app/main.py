"""FastAPI application entry point."""
import asyncio
import logging
import uuid
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.config import settings
from app.dependencies import engine, async_session, set_services
from app.models import Base, AlarmRule
from app.services.influx_writer import InfluxWriter
from app.services.influx_query import InfluxQueryService
from app.services.mqtt_ingestion import MqttIngestionService
from app.services.rule_engine import RuleEngine
from app.services.alarm_manager import AlarmManager
from app.services.webhook_dispatcher import WebhookDispatcher
from app.services.state_persistence import StatePersistence
from app.services.rule_sync import RuleSyncService
from app.services.dependency_manager import DependencyManager
from app.services.propagation_engine import PropagationEngine
from app.rule_dsl.parser import parse_rule
from app.websocket.manager import WebSocketManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting EdgeFleet backend...")

    # Create DB tables (retry on connection failure during startup)
    for attempt in range(5):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created/verified")
            break
        except Exception as e:
            if attempt < 4:
                logger.warning(f"DB not ready (attempt {attempt+1}/5): {e}. Retrying in 2s...")
                await asyncio.sleep(2)
            else:
                logger.error(f"Failed to connect to database after 5 attempts: {e}")
                raise

    # Redis
    redis_client = aioredis.from_url(settings.redis_url)

    # Services
    webhook_dispatcher = WebhookDispatcher()
    await webhook_dispatcher.start()

    alarm_manager = AlarmManager(webhook_dispatcher, redis_client)
    state_persistence = StatePersistence(redis_client)
    rule_engine = RuleEngine(alarm_manager, state_persistence)

    influx_writer = InfluxWriter()
    await influx_writer.start()

    influx_query = InfluxQueryService()
    await influx_query.start()

    ws_manager = WebSocketManager(redis_client)
    app.state.ws_manager = ws_manager

    # Load rules from DB and restore persisted states
    async with async_session() as db:
        result = await db.execute(select(AlarmRule).where(AlarmRule.enabled == True))
        for db_rule in result.scalars().all():
            rule_data = {
                "rule_id": db_rule.id,
                "org_id": db_rule.org_id,
                "name": db_rule.name,
                "enabled": db_rule.enabled,
                "target": db_rule.target,
                "trigger_condition": db_rule.trigger_condition,
                "recovery_condition": db_rule.recovery_condition,
                "severity": db_rule.severity,
                "actions": db_rule.actions,
            }
            try:
                parsed = parse_rule(rule_data)
                rule_engine.register_rule(parsed)
                await rule_engine.restore_states_for_rule(db_rule.org_id, db_rule.id)
            except Exception as e:
                logger.error(f"Failed to load rule {db_rule.id}: {e}")

    logger.info(f"Loaded {rule_engine.rule_count} alarm rules (states restored from Redis)")

    # Device dependency manager
    dependency_manager = DependencyManager()
    async with async_session() as db:
        await dependency_manager.load_from_db(db)
    logger.info(f"Loaded {dependency_manager.edge_count} device dependencies")

    # Propagation engine (observer on alarm events)
    propagation_engine = PropagationEngine(dependency_manager, alarm_manager)
    alarm_manager.add_listener(propagation_engine.on_alarm_event)

    # Rule sync service for multi-instance coordination
    instance_id = str(uuid.uuid4())
    rule_sync = RuleSyncService(redis_client, rule_engine, state_persistence, instance_id)

    # Register service singletons
    set_services(rule_engine, alarm_manager, influx_query, dependency_manager, propagation_engine, rule_sync)

    # MQTT ingestion
    ingestion = MqttIngestionService(influx_writer, rule_engine, ws_manager)
    mqtt_task = asyncio.create_task(ingestion.start())

    # WebSocket Redis subscriber
    ws_task = asyncio.create_task(ws_manager.start_subscriber())

    # Rule sync subscriber
    rule_sync_task = asyncio.create_task(rule_sync.start_subscriber())

    yield

    # Shutdown
    logger.info("Shutting down...")
    ingestion.stop()
    mqtt_task.cancel()
    ws_task.cancel()
    rule_sync_task.cancel()
    await influx_writer.stop()
    await influx_query.stop()
    await webhook_dispatcher.stop()
    await redis_client.close()
    await engine.dispose()


app = FastAPI(
    title="EdgeFleet Simulator API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
from app.api.v1.auth import router as auth_router
from app.api.v1.devices import router as devices_router
from app.api.v1.rules import router as rules_router
from app.api.v1.alarms import router as alarms_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.tenants import router as tenants_router
from app.api.v1.dependencies import router as dependencies_router
from app.websocket.manager import router as ws_router

app.include_router(auth_router, prefix="/api/v1")
app.include_router(devices_router, prefix="/api/v1")
app.include_router(rules_router, prefix="/api/v1")
app.include_router(alarms_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(tenants_router, prefix="/api/v1")
app.include_router(dependencies_router, prefix="/api/v1")
app.include_router(ws_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
