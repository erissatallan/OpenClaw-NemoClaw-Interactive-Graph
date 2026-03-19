"""Tests for in-memory graph client (SPEC §2.3)."""

import pytest

from ClawGraph.graph.memory_client import MemoryGraphClient


@pytest.fixture
def graph(tmp_path):
    return MemoryGraphClient(persist_path=tmp_path / "test_graph.json")


class TestMemoryGraphClient:
    @pytest.mark.asyncio
    async def test_upsert_node(self, graph):
        node_id = await graph.upsert_node("Class", {
            "qualified_name": "test.MyClass",
            "name": "MyClass",
            "description": "A test class",
        })
        assert node_id == "Class:test.MyClass"

    @pytest.mark.asyncio
    async def test_upsert_node_requires_qualified_name(self, graph):
        with pytest.raises(ValueError):
            await graph.upsert_node("Class", {"name": "NoQN"})

    @pytest.mark.asyncio
    async def test_upsert_updates_existing(self, graph):
        await graph.upsert_node("Class", {
            "qualified_name": "test.A",
            "name": "A",
            "description": "first",
        })
        await graph.upsert_node("Class", {
            "qualified_name": "test.A",
            "name": "A",
            "description": "updated",
        })
        results = await graph.query("name:A")
        assert len(results) == 1
        assert results[0]["description"] == "updated"

    @pytest.mark.asyncio
    async def test_upsert_relationship(self, graph):
        await graph.upsert_node("Module", {"qualified_name": "mod.A", "name": "A"})
        await graph.upsert_node("Module", {"qualified_name": "mod.B", "name": "B"})
        await graph.upsert_relationship("Module:mod.A", "Module:mod.B", "IMPORTS")

        neighbors = await graph.get_neighbors("Module:mod.A")
        assert len(neighbors) == 1
        assert neighbors[0]["id"] == "Module:mod.B"

    @pytest.mark.asyncio
    async def test_query_all(self, graph):
        await graph.upsert_node("Class", {"qualified_name": "a", "name": "a"})
        await graph.upsert_node("Function", {"qualified_name": "b", "name": "b"})
        results = await graph.query("*")
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_query_by_label(self, graph):
        await graph.upsert_node("Class", {"qualified_name": "c1", "name": "c1"})
        await graph.upsert_node("Function", {"qualified_name": "f1", "name": "f1"})
        results = await graph.query("label:Class")
        assert len(results) == 1
        assert results[0]["_label"] == "Class"

    @pytest.mark.asyncio
    async def test_query_by_name(self, graph):
        await graph.upsert_node("Class", {"qualified_name": "openclaw.Session", "name": "Session"})
        await graph.upsert_node("Class", {"qualified_name": "openclaw.Gateway", "name": "Gateway"})
        results = await graph.query("name:session")
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_mark_stale(self, graph):
        await graph.upsert_node("Class", {"qualified_name": "old", "name": "old"})
        count = await graph.mark_stale(["Class:old"])
        assert count == 1
        results = await graph.query("*")
        assert results[0]["_stale"] is True

    @pytest.mark.asyncio
    async def test_vector_search(self, graph):
        await graph.upsert_node("CodeChunk", {
            "qualified_name": "chunk:1",
            "name": "chunk1",
            "embedding": [1.0, 0.0, 0.0],
        })
        await graph.upsert_node("CodeChunk", {
            "qualified_name": "chunk:2",
            "name": "chunk2",
            "embedding": [0.0, 1.0, 0.0],
        })
        results = await graph.vector_search([1.0, 0.0, 0.0], top_k=1)
        assert len(results) == 1
        assert results[0]["score"] > 0.99

    @pytest.mark.asyncio
    async def test_get_neighbors_depth(self, graph):
        await graph.upsert_node("Module", {"qualified_name": "a", "name": "a"})
        await graph.upsert_node("Class", {"qualified_name": "b", "name": "b"})
        await graph.upsert_node("Function", {"qualified_name": "c", "name": "c"})
        await graph.upsert_relationship("Module:a", "Class:b", "DEFINES")
        await graph.upsert_relationship("Class:b", "Function:c", "HAS_METHOD")

        # Depth 1 should get b only
        neighbors_1 = await graph.get_neighbors("Module:a", depth=1)
        assert any(n["id"] == "Class:b" for n in neighbors_1)

        # Depth 2 should get b and c
        neighbors_2 = await graph.get_neighbors("Module:a", depth=2)
        ids = {n["id"] for n in neighbors_2}
        assert "Class:b" in ids
        assert "Function:c" in ids

    @pytest.mark.asyncio
    async def test_get_stats(self, graph):
        await graph.upsert_node("Class", {"qualified_name": "c1", "name": "c1"})
        await graph.upsert_node("Function", {"qualified_name": "f1", "name": "f1"})
        await graph.upsert_relationship("Class:c1", "Function:f1", "DEFINES")
        stats = await graph.get_stats()
        assert stats.total_nodes == 2
        assert stats.total_relationships == 1
        assert stats.node_counts["Class"] == 1
        assert stats.node_counts["Function"] == 1

    @pytest.mark.asyncio
    async def test_persistence(self, tmp_path):
        path = tmp_path / "persist_test.json"
        g1 = MemoryGraphClient(persist_path=path)
        await g1.upsert_node("Class", {"qualified_name": "persist", "name": "persist"})
        await g1.close()

        g2 = MemoryGraphClient(persist_path=path)
        results = await g2.query("name:persist")
        assert len(results) == 1
