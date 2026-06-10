"""Unit tests for DependencyManager: cycle detection, max depth, org isolation, index correctness."""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.dependency_manager import DependencyManager, DependencyEdge, MAX_DEPTH


class FakeDevice:
    def __init__(self, id, org_id):
        self.id = id
        self.org_id = org_id


class FakeSession:
    """Minimal mock of an AsyncSession."""

    def __init__(self, devices=None):
        self._devices = {d.id: d for d in (devices or [])}
        self._added = []
        self._deleted = []

    async def get(self, model, id):
        return self._devices.get(id)

    def add(self, obj):
        self._added.append(obj)

    async def delete(self, obj):
        self._deleted.append(obj)

    async def commit(self):
        pass


@pytest.fixture
def dep_mgr():
    return DependencyManager()


@pytest.fixture
def session_with_devices():
    devices = [
        FakeDevice("gw-1", "org-1"),
        FakeDevice("sensor-1", "org-1"),
        FakeDevice("sensor-2", "org-1"),
        FakeDevice("sensor-3", "org-1"),
        FakeDevice("sensor-4", "org-1"),
        FakeDevice("other-device", "org-2"),
    ]
    return FakeSession(devices)


@pytest.mark.asyncio
async def test_add_dependency_basic(dep_mgr, session_with_devices):
    edge = await dep_mgr.add_dependency(
        "org-1", "gw-1", "sensor-1", "gateway_sensor", session_with_devices
    )
    assert edge.parent_device_id == "gw-1"
    assert edge.child_device_id == "sensor-1"
    assert dep_mgr.get_children("gw-1") == ["sensor-1"]
    assert dep_mgr.get_parent("sensor-1") == "gw-1"
    assert dep_mgr.edge_count == 1


@pytest.mark.asyncio
async def test_self_dependency_rejected(dep_mgr, session_with_devices):
    with pytest.raises(ValueError, match="cannot depend on itself"):
        await dep_mgr.add_dependency(
            "org-1", "gw-1", "gw-1", "gateway_sensor", session_with_devices
        )


@pytest.mark.asyncio
async def test_duplicate_dependency_rejected(dep_mgr, session_with_devices):
    await dep_mgr.add_dependency("org-1", "gw-1", "sensor-1", "gateway_sensor", session_with_devices)
    with pytest.raises(ValueError, match="already exists"):
        await dep_mgr.add_dependency("org-1", "gw-1", "sensor-1", "gateway_sensor", session_with_devices)


@pytest.mark.asyncio
async def test_cycle_detection_direct(dep_mgr, session_with_devices):
    await dep_mgr.add_dependency("org-1", "gw-1", "sensor-1", "gateway_sensor", session_with_devices)
    with pytest.raises(ValueError, match="cycle"):
        await dep_mgr.add_dependency("org-1", "sensor-1", "gw-1", "gateway_sensor", session_with_devices)


@pytest.mark.asyncio
async def test_cycle_detection_indirect(dep_mgr, session_with_devices):
    await dep_mgr.add_dependency("org-1", "gw-1", "sensor-1", "gateway_sensor", session_with_devices)
    await dep_mgr.add_dependency("org-1", "sensor-1", "sensor-2", "gateway_sensor", session_with_devices)
    with pytest.raises(ValueError, match="cycle"):
        await dep_mgr.add_dependency("org-1", "sensor-2", "gw-1", "gateway_sensor", session_with_devices)


@pytest.mark.asyncio
async def test_max_depth_enforcement(dep_mgr, session_with_devices):
    # Build a chain: gw-1 -> sensor-1 -> sensor-2 -> sensor-3 (depth 3 from root)
    await dep_mgr.add_dependency("org-1", "gw-1", "sensor-1", "gateway_sensor", session_with_devices)
    await dep_mgr.add_dependency("org-1", "sensor-1", "sensor-2", "gateway_sensor", session_with_devices)
    await dep_mgr.add_dependency("org-1", "sensor-2", "sensor-3", "gateway_sensor", session_with_devices)
    # Adding a 4th level should be rejected
    with pytest.raises(ValueError, match="exceed maximum"):
        await dep_mgr.add_dependency("org-1", "sensor-3", "sensor-4", "gateway_sensor", session_with_devices)


@pytest.mark.asyncio
async def test_org_isolation_rejected(dep_mgr, session_with_devices):
    with pytest.raises(ValueError, match="same organization"):
        await dep_mgr.add_dependency("org-1", "gw-1", "other-device", "gateway_sensor", session_with_devices)


@pytest.mark.asyncio
async def test_device_not_found_rejected(dep_mgr, session_with_devices):
    with pytest.raises(ValueError, match="not found"):
        await dep_mgr.add_dependency("org-1", "gw-1", "nonexistent", "gateway_sensor", session_with_devices)


@pytest.mark.asyncio
async def test_remove_dependency(dep_mgr, session_with_devices):
    edge = await dep_mgr.add_dependency("org-1", "gw-1", "sensor-1", "gateway_sensor", session_with_devices)

    # Mock the session.get for DeviceDependency
    mock_db_dep = MagicMock()
    session_with_devices._devices[edge.id] = mock_db_dep

    removed = await dep_mgr.remove_dependency(edge.id, session_with_devices)
    assert removed is not None
    assert dep_mgr.get_children("gw-1") == []
    assert dep_mgr.get_parent("sensor-1") is None
    assert dep_mgr.edge_count == 0


@pytest.mark.asyncio
async def test_get_org_edges(dep_mgr, session_with_devices):
    await dep_mgr.add_dependency("org-1", "gw-1", "sensor-1", "gateway_sensor", session_with_devices)
    await dep_mgr.add_dependency("org-1", "gw-1", "sensor-2", "gateway_sensor", session_with_devices)

    edges = dep_mgr.get_org_edges("org-1")
    assert len(edges) == 2

    edges_other = dep_mgr.get_org_edges("org-2")
    assert len(edges_other) == 0


@pytest.mark.asyncio
async def test_is_suppressed(dep_mgr, session_with_devices):
    edge = await dep_mgr.add_dependency("org-1", "gw-1", "sensor-1", "gateway_sensor", session_with_devices)
    assert dep_mgr.is_suppressed("gw-1", "sensor-1") is False

    edge.suppress_derived_notifications = True
    assert dep_mgr.is_suppressed("gw-1", "sensor-1") is True
