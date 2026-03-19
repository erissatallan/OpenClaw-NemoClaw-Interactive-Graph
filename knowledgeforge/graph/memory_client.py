"""In-memory graph backend using NetworkX (SPEC §2.3 fallback)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import networkx as nx
import numpy as np

from ClawGraph.graph.base import GraphClient
from ClawGraph.models import GraphStats

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")


class MemoryGraphClient(GraphClient):
    """NetworkX-backed in-memory knowledge graph with JSON persistence.

    - Nodes are keyed by `qualified_name`.
    - Embeddings stored as node attributes for vector search.
    - Graph is saved/loaded from `data/graph.json`.
    """

    def __init__(self, persist_path: str | Path | None = None):
        self._graph = nx.DiGraph()
        self._persist_path = Path(persist_path) if persist_path else DATA_DIR / "graph.json"
        self._load()

    def _load(self):
        """Load graph from disk if it exists."""
        if self._persist_path.exists():
            try:
                data = json.loads(self._persist_path.read_text())
                self._graph = nx.node_link_graph(data, directed=True)
                logger.info("Loaded graph from %s (%d nodes)", self._persist_path, len(self._graph))
            except Exception as exc:
                logger.warning("Failed to load graph: %s", exc)

    def _save(self):
        """Persist graph to disk."""
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        data = nx.node_link_data(self._graph)
        # Convert numpy arrays to lists for JSON serialization
        for node in data.get("nodes", []):
            for key, val in node.items():
                if isinstance(val, np.ndarray):
                    node[key] = val.tolist()
        self._persist_path.write_text(json.dumps(data, default=str))

    async def upsert_node(self, label: str, properties: dict[str, Any]) -> str:
        qn = properties.get("qualified_name", "")
        if not qn:
            raise ValueError("Node must have a 'qualified_name' property")

        node_id = f"{label}:{qn}"

        if self._graph.has_node(node_id):
            self._graph.nodes[node_id].update(properties)
            self._graph.nodes[node_id]["_label"] = label
            self._graph.nodes[node_id]["_stale"] = False
        else:
            self._graph.add_node(node_id, _label=label, _stale=False, **properties)

        self._save()
        return node_id

    async def upsert_relationship(
        self,
        from_id: str,
        to_id: str,
        rel_type: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        # Ensure both nodes exist (create stub if missing)
        if not self._graph.has_node(from_id):
            self._graph.add_node(from_id, _label="Unknown", _stale=False)
        if not self._graph.has_node(to_id):
            self._graph.add_node(to_id, _label="Unknown", _stale=False)

        self._graph.add_edge(from_id, to_id, _rel_type=rel_type, **(properties or {}))
        self._save()

    async def query(self, query_str: str, params: dict[str, Any] | None = None) -> list[dict]:
        """Simple query — supports 'label:X' filter or '*' for all nodes."""
        results = []

        if query_str == "*":
            for node_id, data in self._graph.nodes(data=True):
                results.append({"id": node_id, **data})
        elif query_str.startswith("label:"):
            target_label = query_str.split(":", 1)[1]
            for node_id, data in self._graph.nodes(data=True):
                if data.get("_label") == target_label:
                    results.append({"id": node_id, **data})
        elif query_str.startswith("name:"):
            target_name = query_str.split(":", 1)[1].lower()
            for node_id, data in self._graph.nodes(data=True):
                qn = data.get("qualified_name", "").lower()
                name = data.get("name", "").lower()
                if target_name in qn or target_name in name:
                    results.append({"id": node_id, **data})

        return results

    async def vector_search(
        self,
        embedding: list[float],
        top_k: int = 10,
        label_filter: str | None = None,
    ) -> list[dict]:
        """Cosine similarity search over node embeddings."""
        query_vec = np.array(embedding, dtype=np.float32)
        query_norm = np.linalg.norm(query_vec)
        if query_norm == 0:
            return []

        scored = []
        for node_id, data in self._graph.nodes(data=True):
            if label_filter and data.get("_label") != label_filter:
                continue

            node_emb = data.get("embedding")
            if node_emb is None:
                continue

            node_vec = np.array(node_emb, dtype=np.float32)
            node_norm = np.linalg.norm(node_vec)
            if node_norm == 0:
                continue

            cosine_sim = float(np.dot(query_vec, node_vec) / (query_norm * node_norm))
            scored.append({"node": {"id": node_id, **data}, "score": cosine_sim})

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    async def mark_stale(self, node_ids: list[str]) -> int:
        count = 0
        for node_id in node_ids:
            if self._graph.has_node(node_id):
                self._graph.nodes[node_id]["_stale"] = True
                count += 1
        self._save()
        return count

    async def get_neighbors(self, node_id: str, depth: int = 1) -> list[dict]:
        if not self._graph.has_node(node_id):
            return []

        visited = set()
        frontier = {node_id}
        results = []

        for _ in range(depth):
            next_frontier = set()
            for nid in frontier:
                if nid in visited:
                    continue
                visited.add(nid)
                # Outgoing neighbors
                for successor in self._graph.successors(nid):
                    if successor not in visited:
                        next_frontier.add(successor)
                        edge_data = self._graph.edges[nid, successor]
                        results.append({
                            "id": successor,
                            "rel_type": edge_data.get("_rel_type", "RELATED"),
                            "direction": "outgoing",
                            **self._graph.nodes[successor],
                        })
                # Incoming neighbors
                for predecessor in self._graph.predecessors(nid):
                    if predecessor not in visited:
                        next_frontier.add(predecessor)
                        edge_data = self._graph.edges[predecessor, nid]
                        results.append({
                            "id": predecessor,
                            "rel_type": edge_data.get("_rel_type", "RELATED"),
                            "direction": "incoming",
                            **self._graph.nodes[predecessor],
                        })
            frontier = next_frontier

        return results

    async def get_stats(self) -> GraphStats:
        label_counts: dict[str, int] = {}
        for _, data in self._graph.nodes(data=True):
            label = data.get("_label", "Unknown")
            label_counts[label] = label_counts.get(label, 0) + 1

        return GraphStats(
            total_nodes=self._graph.number_of_nodes(),
            total_relationships=self._graph.number_of_edges(),
            node_counts=label_counts,
        )

    async def close(self) -> None:
        self._save()
