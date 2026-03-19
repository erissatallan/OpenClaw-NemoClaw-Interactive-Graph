"""Tests for RAG engine (SPEC §2.4)."""

import pytest

from ClawGraph.graph.memory_client import MemoryGraphClient
from ClawGraph.rag.embeddings import cosine_similarity, rank_by_similarity
from ClawGraph.rag.retriever import RAGRetriever


class TestCosineSimilarity:
    def test_identical_vectors(self):
        assert cosine_similarity([1, 0, 0], [1, 0, 0]) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        assert cosine_similarity([1, 0, 0], [0, 1, 0]) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        assert cosine_similarity([1, 0], [-1, 0]) == pytest.approx(-1.0)

    def test_zero_vector(self):
        assert cosine_similarity([0, 0, 0], [1, 2, 3]) == 0.0


class TestRankBySimilarity:
    def test_ranking_order(self):
        query = [1.0, 0.0, 0.0]
        candidates = [
            {"text": "a", "embedding": [0.0, 1.0, 0.0]},
            {"text": "b", "embedding": [1.0, 0.0, 0.0]},
            {"text": "c", "embedding": [0.5, 0.5, 0.0]},
        ]
        ranked = rank_by_similarity(query, candidates, top_k=3)
        assert ranked[0]["text"] == "b"  # Most similar
        assert ranked[0]["similarity_score"] > ranked[1]["similarity_score"]

    def test_top_k_limit(self):
        query = [1.0, 0.0]
        candidates = [
            {"text": str(i), "embedding": [float(i), 0.0]} for i in range(10)
        ]
        ranked = rank_by_similarity(query, candidates, top_k=3)
        assert len(ranked) == 3

    def test_skips_missing_embeddings(self):
        query = [1.0, 0.0]
        candidates = [
            {"text": "a", "embedding": [1.0, 0.0]},
            {"text": "b"},  # No embedding
        ]
        ranked = rank_by_similarity(query, candidates, top_k=10)
        assert len(ranked) == 1


class TestRAGRetrieverTermExtraction:
    def test_extracts_project_terms(self):
        terms = RAGRetriever._extract_terms("How does the OpenClaw Gateway work?")
        assert "openclaw" in terms
        assert "gateway" in terms

    def test_filters_stop_words(self):
        terms = RAGRetriever._extract_terms("What is the purpose of this feature?")
        assert "what" not in terms
        assert "is" not in terms
        assert "the" not in terms

    def test_project_terms_prioritized(self):
        terms = RAGRetriever._extract_terms("Tell me about the sandbox in nemoclaw")
        assert terms.index("nemoclaw") < terms.index("sandbox")

    def test_empty_query(self):
        terms = RAGRetriever._extract_terms("")
        assert terms == []
