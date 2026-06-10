"""Integration tests for device dependency API endpoints."""
import pytest
import time
import jwt

from app.services.dependency_manager import DependencyManager

FAKE_SECRET = "test-secret"
FAKE_ALGORITHM = "HS256"


def make_token(org_id: str, role: str = "admin", user_id: str = "user-1"):
    payload = {
        "sub": user_id,
        "org_id": org_id,
        "group_ids": [],
        "role": role,
        "exp": int(time.time()) + 3600,
    }
    return jwt.encode(payload, FAKE_SECRET, algorithm=FAKE_ALGORITHM)


class TestDependencyValidation:
    """Tests for dependency creation validation logic (unit-level, no HTTP)."""

    @pytest.fixture
    def dep_mgr(self):
        return DependencyManager()

    def test_cycle_detection_direct(self, dep_mgr):
        """A->B then B->A should detect cycle."""
        # Manually index edges for unit testing
        from app.services.dependency_manager import DependencyEdge

        edge1 = DependencyEdge(
            id="e1", org_id="org-1",
            parent_device_id="A", child_device_id="B",
            dependency_type="gateway_sensor",
        )
        dep_mgr._index_edge(edge1)

        assert dep_mgr._detect_cycle("B", "A") is True

    def test_cycle_detection_indirect(self, dep_mgr):
        """A->B->C then C->A should detect cycle."""
        from app.services.dependency_manager import DependencyEdge

        dep_mgr._index_edge(DependencyEdge(
            id="e1", org_id="org-1",
            parent_device_id="A", child_device_id="B",
            dependency_type="gateway_sensor",
        ))
        dep_mgr._index_edge(DependencyEdge(
            id="e2", org_id="org-1",
            parent_device_id="B", child_device_id="C",
            dependency_type="gateway_sensor",
        ))

        assert dep_mgr._detect_cycle("C", "A") is True

    def test_no_false_cycle(self, dep_mgr):
        """A->B, adding A->C should NOT detect a cycle."""
        from app.services.dependency_manager import DependencyEdge

        dep_mgr._index_edge(DependencyEdge(
            id="e1", org_id="org-1",
            parent_device_id="A", child_device_id="B",
            dependency_type="gateway_sensor",
        ))

        assert dep_mgr._detect_cycle("A", "C") is False

    def test_max_depth_calculation(self, dep_mgr):
        """Verify depth calculation through parent chain."""
        from app.services.dependency_manager import DependencyEdge

        dep_mgr._index_edge(DependencyEdge(
            id="e1", org_id="org-1",
            parent_device_id="A", child_device_id="B",
            dependency_type="gateway_sensor",
        ))
        dep_mgr._index_edge(DependencyEdge(
            id="e2", org_id="org-1",
            parent_device_id="B", child_device_id="C",
            dependency_type="gateway_sensor",
        ))

        assert dep_mgr._get_depth("A") == 0
        assert dep_mgr._get_depth("B") == 1
        assert dep_mgr._get_depth("C") == 2

    def test_max_subtree_depth(self, dep_mgr):
        """Verify subtree depth calculation."""
        from app.services.dependency_manager import DependencyEdge

        dep_mgr._index_edge(DependencyEdge(
            id="e1", org_id="org-1",
            parent_device_id="A", child_device_id="B",
            dependency_type="gateway_sensor",
        ))
        dep_mgr._index_edge(DependencyEdge(
            id="e2", org_id="org-1",
            parent_device_id="B", child_device_id="C",
            dependency_type="gateway_sensor",
        ))

        assert dep_mgr._max_subtree_depth("A") == 2
        assert dep_mgr._max_subtree_depth("B") == 1
        assert dep_mgr._max_subtree_depth("C") == 0

    def test_org_isolation_index(self, dep_mgr):
        """Edges from different orgs stay isolated in org index."""
        from app.services.dependency_manager import DependencyEdge

        dep_mgr._index_edge(DependencyEdge(
            id="e1", org_id="org-1",
            parent_device_id="A", child_device_id="B",
            dependency_type="gateway_sensor",
        ))
        dep_mgr._index_edge(DependencyEdge(
            id="e2", org_id="org-2",
            parent_device_id="X", child_device_id="Y",
            dependency_type="gateway_sensor",
        ))

        org1_edges = dep_mgr.get_org_edges("org-1")
        org2_edges = dep_mgr.get_org_edges("org-2")
        assert len(org1_edges) == 1
        assert len(org2_edges) == 1
        assert org1_edges[0].parent_device_id == "A"
        assert org2_edges[0].parent_device_id == "X"
