"""Device dependency manager: in-memory graph index with cycle detection and org isolation."""
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Device, DeviceDependency

logger = logging.getLogger(__name__)

MAX_DEPTH = 3


@dataclass
class DependencyEdge:
    id: str
    org_id: str
    parent_device_id: str
    child_device_id: str
    dependency_type: str
    suppress_derived_notifications: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)


class DependencyManager:
    def __init__(self):
        self._children: dict[str, set[str]] = {}
        self._parents: dict[str, str] = {}
        self._edges: dict[str, DependencyEdge] = {}
        self._edge_by_pair: dict[tuple[str, str], str] = {}
        self._org_edges: dict[str, set[str]] = {}

    async def load_from_db(self, session: AsyncSession):
        result = await session.execute(select(DeviceDependency))
        for row in result.scalars().all():
            edge = DependencyEdge(
                id=row.id,
                org_id=row.org_id,
                parent_device_id=row.parent_device_id,
                child_device_id=row.child_device_id,
                dependency_type=row.dependency_type,
                suppress_derived_notifications=row.suppress_derived_notifications,
                created_at=row.created_at,
            )
            self._index_edge(edge)
        logger.info(f"Loaded {len(self._edges)} device dependencies")

    def _index_edge(self, edge: DependencyEdge):
        self._edges[edge.id] = edge
        self._edge_by_pair[(edge.parent_device_id, edge.child_device_id)] = edge.id
        if edge.parent_device_id not in self._children:
            self._children[edge.parent_device_id] = set()
        self._children[edge.parent_device_id].add(edge.child_device_id)
        self._parents[edge.child_device_id] = edge.parent_device_id
        if edge.org_id not in self._org_edges:
            self._org_edges[edge.org_id] = set()
        self._org_edges[edge.org_id].add(edge.id)

    def _unindex_edge(self, edge: DependencyEdge):
        self._edges.pop(edge.id, None)
        self._edge_by_pair.pop((edge.parent_device_id, edge.child_device_id), None)
        if edge.parent_device_id in self._children:
            self._children[edge.parent_device_id].discard(edge.child_device_id)
            if not self._children[edge.parent_device_id]:
                del self._children[edge.parent_device_id]
        if self._parents.get(edge.child_device_id) == edge.parent_device_id:
            del self._parents[edge.child_device_id]
        if edge.org_id in self._org_edges:
            self._org_edges[edge.org_id].discard(edge.id)

    async def add_dependency(
        self,
        org_id: str,
        parent_device_id: str,
        child_device_id: str,
        dependency_type: str,
        session: AsyncSession,
    ) -> DependencyEdge:
        if parent_device_id == child_device_id:
            raise ValueError("A device cannot depend on itself")

        if (parent_device_id, child_device_id) in self._edge_by_pair:
            raise ValueError("Dependency already exists")

        parent = await session.get(Device, parent_device_id)
        child = await session.get(Device, child_device_id)
        if not parent or not child:
            raise ValueError("Parent or child device not found")
        if parent.org_id != org_id or child.org_id != org_id:
            raise ValueError("Both devices must belong to the same organization")

        if self._detect_cycle(parent_device_id, child_device_id):
            raise ValueError("Adding this dependency would create a cycle")

        depth = self._get_depth(parent_device_id) + 1 + self._max_subtree_depth(child_device_id)
        if depth > MAX_DEPTH:
            raise ValueError(f"Dependency depth would exceed maximum of {MAX_DEPTH} layers")

        edge_id = str(uuid.uuid4())
        db_dep = DeviceDependency(
            id=edge_id,
            org_id=org_id,
            parent_device_id=parent_device_id,
            child_device_id=child_device_id,
            dependency_type=dependency_type,
        )
        session.add(db_dep)
        await session.commit()

        edge = DependencyEdge(
            id=edge_id,
            org_id=org_id,
            parent_device_id=parent_device_id,
            child_device_id=child_device_id,
            dependency_type=dependency_type,
        )
        self._index_edge(edge)
        return edge

    async def remove_dependency(self, edge_id: str, session: AsyncSession) -> DependencyEdge | None:
        edge = self._edges.get(edge_id)
        if not edge:
            return None

        db_dep = await session.get(DeviceDependency, edge_id)
        if db_dep:
            await session.delete(db_dep)
            await session.commit()

        self._unindex_edge(edge)
        return edge

    async def update_dependency(
        self, edge_id: str, suppress: bool | None, session: AsyncSession
    ) -> DependencyEdge | None:
        edge = self._edges.get(edge_id)
        if not edge:
            return None

        if suppress is not None:
            edge.suppress_derived_notifications = suppress
            db_dep = await session.get(DeviceDependency, edge_id)
            if db_dep:
                db_dep.suppress_derived_notifications = suppress
                await session.commit()

        return edge

    def get_children(self, parent_id: str) -> list[str]:
        return list(self._children.get(parent_id, set()))

    def get_parent(self, child_id: str) -> str | None:
        return self._parents.get(child_id)

    def get_edge(self, edge_id: str) -> DependencyEdge | None:
        return self._edges.get(edge_id)

    def get_edge_by_pair(self, parent_id: str, child_id: str) -> DependencyEdge | None:
        edge_id = self._edge_by_pair.get((parent_id, child_id))
        return self._edges.get(edge_id) if edge_id else None

    def get_org_edges(self, org_id: str) -> list[DependencyEdge]:
        edge_ids = self._org_edges.get(org_id, set())
        return [self._edges[eid] for eid in edge_ids if eid in self._edges]

    def is_suppressed(self, parent_id: str, child_id: str) -> bool:
        edge = self.get_edge_by_pair(parent_id, child_id)
        return edge.suppress_derived_notifications if edge else False

    def _detect_cycle(self, proposed_parent: str, proposed_child: str) -> bool:
        visited = set()
        current = proposed_parent
        while current:
            if current == proposed_child:
                return True
            if current in visited:
                break
            visited.add(current)
            current = self._parents.get(current)
        return False

    def _get_depth(self, device_id: str) -> int:
        depth = 0
        current = device_id
        while current in self._parents:
            depth += 1
            current = self._parents[current]
        return depth

    def _max_subtree_depth(self, device_id: str) -> int:
        children = self._children.get(device_id, set())
        if not children:
            return 0
        return 1 + max(self._max_subtree_depth(c) for c in children)

    @property
    def edge_count(self) -> int:
        return len(self._edges)
