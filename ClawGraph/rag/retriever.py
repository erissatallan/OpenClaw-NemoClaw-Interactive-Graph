"""RAG Retriever — graph + vector retrieval pipeline (SPEC §2.4)."""

from __future__ import annotations

import logging

from google import genai

from ClawGraph.config import Settings
from ClawGraph.graph.base import GraphClient
from ClawGraph.models import QueryResponse
from ClawGraph.rag.generator import RAGGenerator

logger = logging.getLogger(__name__)


class RAGRetriever:
    """Orchestrates the full RAG pipeline: entity recognition → graph retrieval → vector search → generation."""

    def __init__(self, graph: GraphClient, settings: Settings):
        self.graph = graph
        self.settings = settings
        self.generator = RAGGenerator(settings=settings)
        self._client: genai.Client | None = None

    def _get_client(self) -> genai.Client:
        if self._client is None:
            self._client = genai.Client(api_key=self.settings.gemini_api_key)
        return self._client

    async def query(self, question: str) -> QueryResponse:
        """Execute the full RAG pipeline for a question."""
        logger.info(f"rag_query_started question={question[:100]}")

        # Step 1: Extract key terms for graph lookup
        terms = self._extract_terms(question)

        # Step 2: Graph retrieval — find matching entities
        entities = []
        for term in terms:
            results = await self.graph.query(f"name:{term}")
            entities.extend(results)

        # Deduplicate
        seen = set()
        unique_entities = []
        for e in entities:
            eid = e.get("id", str(e))
            if eid not in seen:
                seen.add(eid)
                unique_entities.append(e)
        entities = unique_entities[:15]

        # Step 3: Get neighbors for matched entities (1-hop expansion)
        expanded_entities = list(entities)
        for entity in entities[:5]:
            eid = entity.get("id", "")
            if eid:
                neighbors = await self.graph.get_neighbors(eid, depth=1)
                for n in neighbors:
                    nid = n.get("id", str(n))
                    if nid not in seen:
                        seen.add(nid)
                        expanded_entities.append(n)

        # Step 4: Vector retrieval — embed question and search
        code_chunks = []
        try:
            client = self._get_client()
            response = client.models.embed_content(
                model="models/text-embedding-004",
                contents=[question],
            )
            question_embedding = response.embeddings[0].values
            chunk_results = await self.graph.vector_search(
                embedding=question_embedding,
                top_k=10,
                label_filter="CodeChunk",
            )
            code_chunks = [r.get("node", r) for r in chunk_results]
        except Exception as exc:
            logger.warning(f"vector_search_failed error={exc}")

        # Step 5: Generate answer with CoT
        answer_text, reasoning_trace = await self.generator.generate(
            question=question,
            entities=expanded_entities,
            code_chunks=code_chunks,
        )

        # Build source citations
        sources = []
        for chunk in code_chunks[:5]:
            sources.append({
                "path": chunk.get("path", ""),
                "start_line": chunk.get("start_line", 0),
                "end_line": chunk.get("end_line", 0),
                "language": chunk.get("language", ""),
            })

        logger.info(
            f"rag_query_completed entities_found={len(expanded_entities)} "
            f"chunks_found={len(code_chunks)}"
        )

        return QueryResponse(
            answer=answer_text,
            sources=sources,
            reasoning_trace=reasoning_trace,
        )

    @staticmethod
    def _extract_terms(question: str) -> list[str]:
        """Extract key terms from a question for graph lookup.

        Simple heuristic: extract capitalized words, known project terms,
        and filter out common English stop words.
        """
        stop_words = {
            "what", "is", "the", "how", "does", "do", "can", "you", "a", "an",
            "in", "of", "to", "for", "and", "or", "are", "this", "that", "it",
            "with", "from", "by", "on", "at", "be", "as", "was", "were", "been",
            "has", "have", "had", "will", "would", "could", "should", "may",
            "about", "between", "through", "which", "where", "when", "why",
            "tell", "me", "explain", "describe", "show",
        }

        # Known project terms that should always be searched
        project_terms = {
            "openclaw", "nemoclaw", "gateway", "session", "agent", "canvas",
            "webhook", "telegram", "skill", "openshell", "sandbox", "nemotron",
            "channel", "node", "voicewake", "tailscale", "browser", "cron",
        }

        words = question.lower().split()
        terms = []

        for word in words:
            # Clean punctuation
            cleaned = word.strip("?.,!;:'\"()[]{}").lower()
            if not cleaned or cleaned in stop_words:
                continue

            # Prioritize project terms
            if cleaned in project_terms:
                terms.insert(0, cleaned)
            elif len(cleaned) > 2:
                terms.append(cleaned)

        return terms[:10]
