"""Pydantic data models — all entities, pipeline results, and security verdicts (SPEC §3)."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


# ── Core Entities ──


class Entity(BaseModel):
    """A node in the knowledge graph."""

    qualified_name: str = Field(description="Unique qualified name, e.g. 'openclaw.gateway.Session'")
    label: Literal["Repository", "Module", "Class", "Function", "Concept"] = Field(
        description="Graph node label"
    )
    properties: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source_path: str | None = Field(default=None)
    source_lines: tuple[int, int] | None = Field(default=None)


class Relationship(BaseModel):
    """An edge in the knowledge graph."""

    from_entity: str = Field(description="Source entity qualified_name")
    to_entity: str = Field(description="Target entity qualified_name")
    rel_type: str = Field(description="Relationship type, e.g. 'CALLS', 'IMPORTS'")
    properties: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


# ── Pipeline Stage Results ──


class CrawlResult(BaseModel):
    """Output of the CRAWL stage."""

    repo: str = Field(description="owner/repo identifier")
    files: dict[str, str] = Field(
        default_factory=dict, description="path -> file content"
    )
    issues: list[dict[str, Any]] = Field(default_factory=list)
    pull_requests: list[dict[str, Any]] = Field(default_factory=list)
    contributors: list[dict[str, Any]] = Field(default_factory=list)
    crawled_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ExtractionResult(BaseModel):
    """Output of the EXTRACT stage."""

    entities: list[Entity] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)
    source_repo: str = ""


class CodeChunk(BaseModel):
    """A chunk of source code or documentation with an optional embedding."""

    text: str
    path: str
    start_line: int = 0
    end_line: int = 0
    language: str = "unknown"
    embedding: list[float] | None = None

    @property
    def id(self) -> str:
        """Deterministic ID from content hash."""
        return hashlib.sha256(f"{self.path}:{self.start_line}:{self.text}".encode()).hexdigest()[:16]


class EmbeddingResult(BaseModel):
    """Output of the EMBED stage."""

    chunks: list[CodeChunk] = Field(default_factory=list)
    source_repo: str = ""


class GraphUpdateResult(BaseModel):
    """Output of the GRAPH_UPDATE stage."""

    nodes_created: int = 0
    nodes_updated: int = 0
    nodes_stale_marked: int = 0
    relationships_created: int = 0
    relationships_updated: int = 0


class CurationAction(BaseModel):
    """A single action taken by the curation agent."""

    action: Literal["approve", "reject", "merge", "flag"] = Field(
        description="Type of curation action"
    )
    entity_ids: list[str] = Field(default_factory=list)
    reasoning: str = Field(description="Chain-of-thought explanation")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class CurationResult(BaseModel):
    """Output of the CURATE stage."""

    actions: list[CurationAction] = Field(default_factory=list)
    reasoning_trace: str = Field(
        default="", description="Full CoT reasoning transcript"
    )


# ── Security ──


class SecurityVerdict(BaseModel):
    """Result of the prompt injection defense pipeline."""

    input_text: str
    sanitized_text: str = ""
    classification: Literal["benign", "suspicious", "malicious"] = "benign"
    classifier_confidence: float = 0.0
    canary_triggered: bool = False
    output_blocked: bool = False
    reason: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── API ──


class QueryRequest(BaseModel):
    """RAG query request."""

    question: str = Field(min_length=1, max_length=2000)


class QueryResponse(BaseModel):
    """RAG query response with CoT."""

    answer: str
    sources: list[dict[str, Any]] = Field(default_factory=list)
    reasoning_trace: str = ""
    security_verdict: SecurityVerdict | None = None


class GraphStats(BaseModel):
    """Knowledge graph statistics."""

    total_nodes: int = 0
    total_relationships: int = 0
    node_counts: dict[str, int] = Field(default_factory=dict)
    last_crawled: datetime | None = None
    last_curated: datetime | None = None


class HealthResponse(BaseModel):
    """Service health check response."""

    status: str = "healthy"
    version: str = "0.1.0"
    graph_backend: str = "memory"
    graph_connected: bool = False
