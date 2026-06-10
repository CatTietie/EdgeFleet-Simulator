"""Dependency injection: DB sessions, service singletons."""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.config import settings

engine = create_async_engine(settings.database_url, echo=False, pool_size=20, max_overflow=10)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Service singletons (initialized in main.py lifespan)
_rule_engine = None
_alarm_manager = None
_influx_query = None
_dependency_manager = None
_propagation_engine = None


async def get_db():
    async with async_session() as session:
        yield session


def get_rule_engine():
    return _rule_engine


def get_alarm_manager():
    return _alarm_manager


def get_influx_query():
    return _influx_query


def get_dependency_manager():
    return _dependency_manager


def get_propagation_engine():
    return _propagation_engine


def set_services(
    rule_engine,
    alarm_manager,
    influx_query,
    dependency_manager=None,
    propagation_engine=None,
):
    global _rule_engine, _alarm_manager, _influx_query, _dependency_manager, _propagation_engine
    _rule_engine = rule_engine
    _alarm_manager = alarm_manager
    _influx_query = influx_query
    _dependency_manager = dependency_manager
    _propagation_engine = propagation_engine
