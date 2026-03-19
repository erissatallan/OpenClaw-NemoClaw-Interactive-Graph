"""GRAPH_UPDATE stage — upserts entities/relationships into graph (SPEC §2.2 Stage: GRAPH_UPDATE)."""

from __future__ import annotations

import logging
from typing import Any

from ClawGraph.graph.base import GraphClient
from ClawGraph.models import (
    EmbeddingResult,
    ExtractionResult,
    GraphUpdateResult,
)

logger = logging.getLogger(__name__)


class GraphUpdateStage:
    """Merges extracted entities and embeddings into the knowledge graph."""

    def __init__(self, graph: GraphClient):
        self.graph = graph

    async def run(
        self,
        extraction_results: list[ExtractionResult],
        embedding_results: list[EmbeddingResult],
    ) -> GraphUpdateResult:
        """Upsert all entities, relationships, and embeddings into the graph."""
        result = GraphUpdateResult()
        seen_node_ids: set[str] = set()

        logger.info("graph_update_started")

        # ── Upsert entities ──
        for extraction in extraction_results:
            repo = extraction.source_repo

            # Add repository node
            repo_id = await self.graph.upsert_node(
                "Repository",
                {"qualified_name": repo, "name": repo, "url": f"https://github.com/{repo}"},
            )
            seen_node_ids.add(repo_id)
            result.nodes_created += 1

            for entity in extraction.entities:
                try:
                    props: dict[str, Any] = {
                        "qualified_name": entity.qualified_name,
                        **entity.properties,
                    }
                    if entity.source_path:
                        props["path"] = entity.source_path

                    node_id = await self.graph.upsert_node(entity.label, props)
                    seen_node_ids.add(node_id)
                    result.nodes_created += 1

                    # Link to repository
                    if entity.label == "Module":
                        await self.graph.upsert_relationship(
                            repo_id, node_id, "CONTAINS"
                        )
                        result.relationships_created += 1

                except Exception as exc:
                    logger.debug(
                        "entity_upsert_failed",
                        entity=entity.qualified_name,
                        error=str(exc),
                    )

            # ── Upsert relationships ──
            for rel in extraction.relationships:
                try:
                    from_label = self._guess_label(rel.from_entity, extraction.entities)
                    to_label = self._guess_label(rel.to_entity, extraction.entities)
                    from_id = f"{from_label}:{rel.from_entity}"
                    to_id = f"{to_label}:{rel.to_entity}"

                    await self.graph.upsert_relationship(
                        from_id,
                        to_id,
                        rel.rel_type,
                        {"confidence": rel.confidence},
                    )
                    result.relationships_created += 1
                except Exception as exc:
                    logger.debug(
                        "relationship_upsert_failed",
                        rel=f"{rel.from_entity}-[{rel.rel_type}]->{rel.to_entity}",
                        error=str(exc),
                    )

        # ── Upsert code chunks with embeddings ──
        for embedding_result in embedding_results:
            for chunk in embedding_result.chunks:
                if chunk.embedding is None:
                    continue
                try:
                    props = {
                        "qualified_name": f"chunk:{chunk.id}",
                        "text": chunk.text[:2000],
                        "path": chunk.path,
                        "start_line": chunk.start_line,
                        "end_line": chunk.end_line,
                        "language": chunk.language,
                        "embedding": chunk.embedding,
                    }
                    node_id = await self.graph.upsert_node("CodeChunk", props)
                    seen_node_ids.add(node_id)
                    result.nodes_created += 1
                except Exception as exc:
                    logger.debug("chunk_upsert_failed", chunk_id=chunk.id, error=str(exc))

        logger.info(
            "graph_update_completed",
            nodes_created=result.nodes_created,
            relationships_created=result.relationships_created,
        )

        return result

    @staticmethod
    def _guess_label(qualified_name: str, entities: list) -> str:
        """Guess the label for an entity from the extraction context."""
        for entity in entities:
            if entity.qualified_name == qualified_name:
                return entity.label

        # Heuristics
        parts = qualified_name.split(".")
        last = parts[-1] if parts else ""
        if last and last[0].isupper():
            return "Class"
        return "Function"
