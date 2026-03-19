"""Tests for pipeline stages (SPEC §2.2)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from knowledgeforge.config import Settings
from knowledgeforge.graph.memory_client import MemoryGraphClient
from knowledgeforge.models import CrawlResult, Entity, ExtractionResult, EmbeddingResult, CodeChunk
from knowledgeforge.pipeline.stages.graph_update import GraphUpdateStage
from knowledgeforge.pipeline.stages.embed import EmbedStage


class TestGraphUpdateStage:
    @pytest.mark.asyncio
    async def test_upserts_entities(self, tmp_path):
        graph = MemoryGraphClient(persist_path=tmp_path / "test.json")
        stage = GraphUpdateStage(graph=graph)

        extraction = ExtractionResult(
            entities=[
                Entity(qualified_name="test.MyClass", label="Class", properties={"name": "MyClass", "description": "Test"}),
                Entity(qualified_name="test.my_func", label="Function", properties={"name": "my_func", "description": "Test"}),
            ],
            relationships=[],
            source_repo="owner/repo",
        )

        result = await stage.run([extraction], [])
        assert result.nodes_created >= 2

        stats = await graph.get_stats()
        assert stats.total_nodes >= 2

    @pytest.mark.asyncio
    async def test_upserts_relationships(self, tmp_path):
        from knowledgeforge.models import Relationship

        graph = MemoryGraphClient(persist_path=tmp_path / "test.json")
        stage = GraphUpdateStage(graph=graph)

        extraction = ExtractionResult(
            entities=[
                Entity(qualified_name="mod.A", label="Module", properties={"name": "A"}),
                Entity(qualified_name="mod.B", label="Module", properties={"name": "B"}),
            ],
            relationships=[
                Relationship(from_entity="mod.A", to_entity="mod.B", rel_type="IMPORTS"),
            ],
            source_repo="owner/repo",
        )

        result = await stage.run([extraction], [])
        assert result.relationships_created >= 1

    @pytest.mark.asyncio
    async def test_upserts_code_chunks(self, tmp_path):
        graph = MemoryGraphClient(persist_path=tmp_path / "test.json")
        stage = GraphUpdateStage(graph=graph)

        embedding = EmbeddingResult(
            chunks=[
                CodeChunk(text="def hello():", path="test.py", start_line=1, end_line=1, language="python", embedding=[0.1, 0.2, 0.3]),
            ],
            source_repo="owner/repo",
        )

        result = await stage.run([], [embedding])
        assert result.nodes_created >= 1


class TestEmbedStageChunking:
    def test_chunk_markdown(self):
        settings = Settings(gemini_api_key="test")
        stage = EmbedStage(settings=settings)

        content = "# Section 1\nContent here\n## Subsection\nMore content\n# Section 2\nFinal"
        chunks = stage._chunk_markdown("test.md", content)
        assert len(chunks) >= 2

    def test_chunk_python(self):
        settings = Settings(gemini_api_key="test")
        stage = EmbedStage(settings=settings)

        content = "import os\n\ndef func_a():\n    pass\n\ndef func_b():\n    pass\n\nclass MyClass:\n    pass\n"
        chunks = stage._chunk_code("test.py", content, "python")
        assert len(chunks) >= 2

    def test_chunk_simple_fallback(self):
        settings = Settings(gemini_api_key="test")
        stage = EmbedStage(settings=settings)

        content = "\n".join(f"line {i}" for i in range(200))
        chunks = stage._chunk_simple("test.txt", content, "text")
        assert len(chunks) >= 2
