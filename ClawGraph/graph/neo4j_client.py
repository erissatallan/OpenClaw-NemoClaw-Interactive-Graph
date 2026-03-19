"""Neo4j Aura graph backend (SPEC §2.3 primary)."""

from __future__ import annotations

import logging
from typing import Any

from neo4j import AsyncGraphDatabase, AsyncDriver

from ClawGraph.graph.base import GraphClient
from ClawGraph.models import GraphStats

logger = logging.getLogger(__name__)


class Neo4jGraphClient(GraphClient):
    """Neo4j Aura implementation of GraphClient.

    Uses the neo4j async driver for all operations.
    Schema from SPEC §2.3 is created on first connection.
    """

    def __init__(self, uri: str, username: str, password: str):
        self._driver: AsyncDriver = AsyncGraphDatabase.driver(uri, auth=(username, password))
        self._initialized = False

    async def _ensure_schema(self):
        """Create indexes on first use."""
        if self._initialized:
            return
        async with self._driver.session() as session:
            # Create uniqueness constraints on qualified_name for each label
            for label in ["Repository", "Module", "Class", "Function", "Concept"]:
                try:
                    await session.run(
                        f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) "
                        f"REQUIRE n.qualified_name IS UNIQUE"
                    )
                except Exception as exc:
                    logger.debug("Constraint may already exist: %s", exc)

            # Create index on CodeChunk.id
            try:
                await session.run(
                    "CREATE INDEX IF NOT EXISTS FOR (n:CodeChunk) ON (n.id)"
                )
            except Exception:
                pass

        self._initialized = True
        logger.info("Neo4j schema initialized")

    async def upsert_node(self, label: str, properties: dict[str, Any]) -> str:
        await self._ensure_schema()
        qn = properties.get("qualified_name", "")
        if not qn:
            raise ValueError("Node must have a 'qualified_name' property")

        node_id = f"{label}:{qn}"

        # Remove embedding from properties for Neo4j (stored separately or as list)
        props = {k: v for k, v in properties.items() if k != "embedding"}
        props["_stale"] = False

        # Handle embedding as a float list property
        embedding = properties.get("embedding")
        if embedding is not None:
            props["embedding"] = embedding

        async with self._driver.session() as session:
            await session.run(
                f"MERGE (n:{label} {{qualified_name: $qn}}) "
                f"SET n += $props",
                qn=qn,
                props=props,
            )

        return node_id

    async def upsert_relationship(
        self,
        from_id: str,
        to_id: str,
        rel_type: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        await self._ensure_schema()

        from_label, from_qn = from_id.split(":", 1)
        to_label, to_qn = to_id.split(":", 1)

        props = properties or {}

        async with self._driver.session() as session:
            await session.run(
                f"MATCH (a:{from_label} {{qualified_name: $from_qn}}) "
                f"MATCH (b:{to_label} {{qualified_name: $to_qn}}) "
                f"MERGE (a)-[r:{rel_type}]->(b) "
                f"SET r += $props",
                from_qn=from_qn,
                to_qn=to_qn,
                props=props,
            )

    async def query(self, query_str: str, params: dict[str, Any] | None = None) -> list[dict]:
        await self._ensure_schema()
        async with self._driver.session() as session:
            result = await session.run(query_str, params or {})
            records = await result.data()
            return records

    async def vector_search(
        self,
        embedding: list[float],
        top_k: int = 10,
        label_filter: str | None = None,
    ) -> list[dict]:
        """Cosine similarity search using Cypher (Neo4j Aura Free doesn't have vector index)."""
        await self._ensure_schema()

        label_clause = f":{label_filter}" if label_filter else ""

        cypher = f"""
        MATCH (n{label_clause})
        WHERE n.embedding IS NOT NULL
        WITH n,
             reduce(dot = 0.0, i IN range(0, size(n.embedding)-1) |
                 dot + n.embedding[i] * $embedding[i]) AS dotProduct,
             reduce(norm1 = 0.0, i IN range(0, size(n.embedding)-1) |
                 norm1 + n.embedding[i] * n.embedding[i]) AS norm1,
             reduce(norm2 = 0.0, i IN range(0, size($embedding)-1) |
                 norm2 + $embedding[i] * $embedding[i]) AS norm2
        WITH n, dotProduct / (sqrt(norm1) * sqrt(norm2)) AS score
        ORDER BY score DESC
        LIMIT $top_k
        RETURN n, score
        """

        async with self._driver.session() as session:
            result = await session.run(cypher, embedding=embedding, top_k=top_k)
            records = await result.data()
            return [{"node": dict(r["n"]), "score": r["score"]} for r in records]

    async def mark_stale(self, node_ids: list[str]) -> int:
        await self._ensure_schema()
        count = 0

        for node_id in node_ids:
            label, qn = node_id.split(":", 1)
            async with self._driver.session() as session:
                result = await session.run(
                    f"MATCH (n:{label} {{qualified_name: $qn}}) SET n._stale = true RETURN count(n) AS cnt",
                    qn=qn,
                )
                record = await result.single()
                if record:
                    count += record["cnt"]

        return count

    async def get_neighbors(self, node_id: str, depth: int = 1) -> list[dict]:
        await self._ensure_schema()

        label, qn = node_id.split(":", 1)

        cypher = f"""
        MATCH (start:{label} {{qualified_name: $qn}})
        CALL apoc.neighbors.tohop(start, '>', {depth}) YIELD node
        RETURN node
        """

        # Fallback if APOC not available
        fallback_cypher = f"""
        MATCH (start:{label} {{qualified_name: $qn}})-[r*1..{depth}]-(neighbor)
        RETURN DISTINCT neighbor, type(r[0]) AS rel_type
        """

        async with self._driver.session() as session:
            try:
                result = await session.run(cypher, qn=qn)
                records = await result.data()
                return [{"id": f"{list(r['node'].labels)[0]}:{r['node']['qualified_name']}", **dict(r["node"])} for r in records if r.get("node")]
            except Exception:
                result = await session.run(fallback_cypher, qn=qn)
                records = await result.data()
                return [{"id": str(r.get("neighbor", {}).get("qualified_name", "")), **dict(r.get("neighbor", {}))} for r in records]

    async def get_stats(self) -> GraphStats:
        await self._ensure_schema()
        async with self._driver.session() as session:
            # Total nodes
            result = await session.run("MATCH (n) RETURN count(n) AS cnt")
            record = await result.single()
            total_nodes = record["cnt"] if record else 0

            # Total relationships
            result = await session.run("MATCH ()-[r]->() RETURN count(r) AS cnt")
            record = await result.single()
            total_rels = record["cnt"] if record else 0

            # Node counts by label
            result = await session.run(
                "MATCH (n) RETURN labels(n)[0] AS label, count(n) AS cnt"
            )
            records = await result.data()
            label_counts = {r["label"]: r["cnt"] for r in records if r.get("label")}

            return GraphStats(
                total_nodes=total_nodes,
                total_relationships=total_rels,
                node_counts=label_counts,
            )

    async def close(self) -> None:
        await self._driver.close()
