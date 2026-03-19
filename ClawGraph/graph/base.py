"""Abstract GraphClient interface (SPEC §2.3)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ClawGraph.models import GraphStats


class GraphClient(ABC):
    """Abstract base class for knowledge graph backends.

    Implementations: MemoryGraphClient (NetworkX), Neo4jGraphClient (Neo4j Aura).
    """

    @abstractmethod
    async def upsert_node(self, label: str, properties: dict[str, Any]) -> str:
        """Create or update a node. Returns the node ID.

        Nodes are keyed by 'qualified_name' — if a node with the same
        qualified_name and label exists, it is updated; otherwise created.
        """
        ...

    @abstractmethod
    async def upsert_relationship(
        self,
        from_id: str,
        to_id: str,
        rel_type: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """Create or update a relationship between two nodes."""
        ...

    @abstractmethod
    async def query(self, query_str: str, params: dict[str, Any] | None = None) -> list[dict]:
        """Execute a query (Cypher for Neo4j, dict-match for memory).

        Returns list of result dicts.
        """
        ...

    @abstractmethod
    async def vector_search(
        self,
        embedding: list[float],
        top_k: int = 10,
        label_filter: str | None = None,
    ) -> list[dict]:
        """Find nodes by embedding similarity (cosine).

        Returns list of dicts with 'node', 'score' keys.
        """
        ...

    @abstractmethod
    async def mark_stale(self, node_ids: list[str]) -> int:
        """Mark nodes as stale (not seen in latest crawl). Returns count marked."""
        ...

    @abstractmethod
    async def get_neighbors(
        self, node_id: str, depth: int = 1
    ) -> list[dict]:
        """Get neighboring nodes up to `depth` hops away."""
        ...

    @abstractmethod
    async def get_stats(self) -> GraphStats:
        """Return graph statistics."""
        ...

    async def close(self) -> None:
        """Clean up resources. Override in subclasses if needed."""
        pass
