"""Shared test fixtures — mock Gemini, mock GitHub, test graph client."""

from __future__ import annotations

import pytest

from ClawGraph.config import Settings
from ClawGraph.graph.memory_client import MemoryGraphClient


@pytest.fixture
def settings() -> Settings:
    """Test settings with no real API keys."""
    return Settings(
        gemini_api_key="test-key-not-real",
        github_token="test-token-not-real",
        graph_backend="memory",
        pipeline_targets="test-owner/test-repo",
        canary_secret="test-canary-uuid-12345678",
        api_host="127.0.0.1",
        api_port=8000,
        log_level="DEBUG",
    )


@pytest.fixture
def graph(tmp_path) -> MemoryGraphClient:
    """In-memory graph client with temp persistence."""
    return MemoryGraphClient(persist_path=tmp_path / "test_graph.json")


@pytest.fixture
async def populated_graph(graph: MemoryGraphClient) -> MemoryGraphClient:
    """Graph pre-populated with test data."""
    # Repository
    await graph.upsert_node("Repository", {
        "qualified_name": "openclaw/openclaw",
        "name": "openclaw",
        "url": "https://github.com/openclaw/openclaw",
        "description": "Personal AI assistant",
    })

    # Modules
    await graph.upsert_node("Module", {
        "qualified_name": "openclaw.gateway",
        "name": "gateway",
        "description": "Gateway control plane module",
        "path": "src/gateway/index.ts",
    })

    await graph.upsert_node("Module", {
        "qualified_name": "openclaw.channels.telegram",
        "name": "telegram",
        "description": "Telegram channel integration",
        "path": "src/channels/telegram.ts",
    })

    # Classes
    await graph.upsert_node("Class", {
        "qualified_name": "openclaw.gateway.Session",
        "name": "Session",
        "description": "Manages chat sessions",
        "path": "src/gateway/session.ts",
    })

    # Functions
    await graph.upsert_node("Function", {
        "qualified_name": "openclaw.gateway.handleMessage",
        "name": "handleMessage",
        "description": "Handles incoming messages",
        "signature": "async handleMessage(msg: Message): Promise<Response>",
        "path": "src/gateway/handler.ts",
    })

    # Relationships
    await graph.upsert_relationship(
        "Repository:openclaw/openclaw", "Module:openclaw.gateway", "CONTAINS"
    )
    await graph.upsert_relationship(
        "Repository:openclaw/openclaw", "Module:openclaw.channels.telegram", "CONTAINS"
    )
    await graph.upsert_relationship(
        "Module:openclaw.gateway", "Class:openclaw.gateway.Session", "DEFINES"
    )
    await graph.upsert_relationship(
        "Module:openclaw.gateway", "Function:openclaw.gateway.handleMessage", "DEFINES"
    )

    return graph
