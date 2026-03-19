"""Tests for Pydantic data models (SPEC §3)."""

import pytest

from ClawGraph.models import (
    CodeChunk,
    CrawlResult,
    CurationAction,
    Entity,
    ExtractionResult,
    QueryRequest,
    Relationship,
    SecurityVerdict,
)


class TestEntity:
    def test_create_entity(self):
        entity = Entity(
            qualified_name="openclaw.gateway.Session",
            label="Class",
            properties={"name": "Session", "description": "Session manager"},
        )
        assert entity.qualified_name == "openclaw.gateway.Session"
        assert entity.label == "Class"
        assert entity.confidence == 1.0

    def test_entity_confidence_bounds(self):
        with pytest.raises(Exception):
            Entity(qualified_name="test", label="Class", confidence=1.5)

    def test_entity_with_source(self):
        entity = Entity(
            qualified_name="test.func",
            label="Function",
            source_path="src/test.py",
            source_lines=(10, 25),
        )
        assert entity.source_path == "src/test.py"
        assert entity.source_lines == (10, 25)


class TestRelationship:
    def test_create_relationship(self):
        rel = Relationship(
            from_entity="mod.A",
            to_entity="mod.B",
            rel_type="IMPORTS",
        )
        assert rel.rel_type == "IMPORTS"
        assert rel.confidence == 1.0


class TestCodeChunk:
    def test_deterministic_id(self):
        chunk = CodeChunk(text="def hello():", path="src/main.py", start_line=1, end_line=1)
        assert chunk.id == chunk.id  # Same input → same ID

    def test_different_chunks_different_ids(self):
        c1 = CodeChunk(text="def foo():", path="a.py", start_line=1, end_line=1)
        c2 = CodeChunk(text="def bar():", path="a.py", start_line=2, end_line=2)
        assert c1.id != c2.id


class TestCrawlResult:
    def test_defaults(self):
        result = CrawlResult(repo="test/repo")
        assert result.files == {}
        assert result.issues == []
        assert result.crawled_at is not None


class TestExtractionResult:
    def test_empty(self):
        result = ExtractionResult()
        assert result.entities == []
        assert result.relationships == []


class TestCurationAction:
    def test_valid_action(self):
        action = CurationAction(
            action="merge",
            entity_ids=["a", "b"],
            reasoning="These are duplicates because...",
        )
        assert action.action == "merge"


class TestSecurityVerdict:
    def test_defaults(self):
        verdict = SecurityVerdict(input_text="hello")
        assert verdict.classification == "benign"
        assert verdict.canary_triggered is False
        assert verdict.output_blocked is False


class TestQueryRequest:
    def test_min_length(self):
        with pytest.raises(Exception):
            QueryRequest(question="")

    def test_valid(self):
        req = QueryRequest(question="What is OpenClaw?")
        assert req.question == "What is OpenClaw?"
