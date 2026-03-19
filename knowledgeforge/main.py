"""FastAPI application entry point — SPEC §4 API surface."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
import uvicorn
from fastapi import FastAPI, HTTPException

from knowledgeforge.config import Settings, get_settings
from knowledgeforge.graph.base import GraphClient
from knowledgeforge.graph.memory_client import MemoryGraphClient
from knowledgeforge.models import (
    GraphStats,
    HealthResponse,
    QueryRequest,
    QueryResponse,
)
from knowledgeforge.rag.retriever import RAGRetriever
from knowledgeforge.security.defense import DefensePipeline

# ── Structured logging setup ──

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


# ── App state ──

class AppState:
    """Shared application state."""

    def __init__(self):
        self.settings = Settings()
        self.graph: GraphClient = MemoryGraphClient()
        self.rag: RAGRetriever | None = None
        self.defense: DefensePipeline | None = DefensePipeline(settings=self.settings)


state = AppState()


# ── Lifespan ──

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialize and tear down app resources."""
    settings = get_settings()
    state.settings = settings

    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))

    # Initialize graph backend
    if settings.graph_backend == "neo4j" and settings.neo4j_uri:
        try:
            from knowledgeforge.graph.neo4j_client import Neo4jGraphClient

            state.graph = Neo4jGraphClient(
                uri=settings.neo4j_uri,
                username=settings.neo4j_username,
                password=settings.neo4j_password,
            )
            logger.info("graph_backend_initialized", backend="neo4j")
        except Exception as exc:
            logger.warning("neo4j_connection_failed", error=str(exc), fallback="memory")
            state.graph = MemoryGraphClient()
    else:
        state.graph = MemoryGraphClient()
        logger.info("graph_backend_initialized", backend="memory")

    # Initialize RAG retriever
    if settings.gemini_api_key:
        state.rag = RAGRetriever(graph=state.graph, settings=settings)
        logger.info("rag_retriever_initialized")

    # Initialize security pipeline
    state.defense = DefensePipeline(settings=settings)
    logger.info("defense_pipeline_initialized")

    yield

    # Cleanup
    if hasattr(state.graph, "close"):
        await state.graph.close()
    logger.info("app_shutdown_complete")


# ── FastAPI app ──

app = FastAPI(
    title="KnowledgeForge",
    description="AI-powered knowledge graph builder and RAG system for OpenClaw/NemoClaw",
    version="0.1.0",
    lifespan=lifespan,
)


# ── Routes (SPEC §4) ──

@app.get("/api/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Service health check."""
    connected = False
    try:
        stats = await state.graph.get_stats()
        connected = True
    except Exception:
        pass

    return HealthResponse(
        status="healthy",
        version="0.1.0",
        graph_backend=state.settings.graph_backend,
        graph_connected=connected,
    )


@app.post("/api/query", response_model=QueryResponse)
async def query_rag(request: QueryRequest) -> QueryResponse:
    """RAG query with prompt injection defense."""
    if not state.rag:
        raise HTTPException(status_code=503, detail="RAG not initialized — set GEMINI_API_KEY")

    # Run defense pipeline on input
    verdict = await state.defense.check_input(request.question)

    if verdict.classification == "malicious":
        logger.warning("injection_blocked", input=request.question[:100], verdict=verdict.model_dump())
        return QueryResponse(
            answer="⚠️ Your query was flagged by our security system and cannot be processed.",
            security_verdict=verdict,
        )

    # If suspicious, proceed with caution (logged)
    if verdict.classification == "suspicious":
        logger.info("suspicious_query", input=request.question[:100])

    # Run RAG
    response = await state.rag.query(verdict.sanitized_text or request.question)

    # Check output guardrails
    output_verdict = await state.defense.check_output(response.answer)
    if output_verdict.output_blocked:
        logger.warning("output_blocked", reason=output_verdict.reason)
        return QueryResponse(
            answer="⚠️ The response was filtered by our security system.",
            security_verdict=output_verdict,
        )

    response.security_verdict = verdict
    return response


@app.get("/api/graph/stats", response_model=GraphStats)
async def graph_stats() -> GraphStats:
    """Return knowledge graph statistics."""
    return await state.graph.get_stats()


@app.post("/api/pipeline/run")
async def trigger_pipeline():
    """Trigger a manual pipeline run."""
    from knowledgeforge.pipeline.orchestrator import PipelineOrchestrator

    orchestrator = PipelineOrchestrator(
        graph=state.graph,
        settings=state.settings,
    )
    result = await orchestrator.run()
    return {"status": "completed", "result": result}


@app.get("/api/security/audit")
async def security_audit():
    """Return recent security events."""
    if not state.defense:
        return {"events": []}
    return {"events": state.defense.get_recent_events(limit=50)}


# ── Entry point ──

def main():
    """Run the application."""
    settings = get_settings()
    uvicorn.run(
        "knowledgeforge.main:app",
        host=settings.api_host,
        port=settings.api_port,
        log_level=settings.log_level.lower(),
        reload=False,
    )


if __name__ == "__main__":
    main()
