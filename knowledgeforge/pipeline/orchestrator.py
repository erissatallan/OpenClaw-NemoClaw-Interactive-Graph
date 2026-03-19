"""DAG orchestrator — runs pipeline stages sequentially with retry and error isolation (SPEC §2.2)."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from knowledgeforge.config import Settings
from knowledgeforge.graph.base import GraphClient
from knowledgeforge.models import CrawlResult, ExtractionResult, EmbeddingResult, GraphUpdateResult, CurationResult
from knowledgeforge.pipeline.stages.crawl import CrawlStage
from knowledgeforge.pipeline.stages.extract import ExtractStage
from knowledgeforge.pipeline.stages.embed import EmbedStage
from knowledgeforge.pipeline.stages.graph_update import GraphUpdateStage
from knowledgeforge.pipeline.stages.curate import CurateStage

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Result of a complete pipeline run."""

    status: str = "pending"
    duration_seconds: float = 0.0
    stages_completed: list[str] = field(default_factory=list)
    stages_failed: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    crawl_results: list[CrawlResult] = field(default_factory=list)
    extraction_results: list[ExtractionResult] = field(default_factory=list)
    graph_update_result: GraphUpdateResult | None = None
    curation_result: CurationResult | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "duration_seconds": self.duration_seconds,
            "stages_completed": self.stages_completed,
            "stages_failed": self.stages_failed,
            "errors": self.errors,
        }


class PipelineOrchestrator:
    """Orchestrates the CRAWL→EXTRACT→EMBED→GRAPH_UPDATE→CURATE pipeline.

    Each stage runs sequentially with per-stage retry (max 3 attempts).
    Stage failures are isolated — a failed stage is logged but doesn't halt the pipeline.
    """

    MAX_RETRIES = 3

    def __init__(self, graph: GraphClient, settings: Settings):
        self.graph = graph
        self.settings = settings
        self.crawl_stage = CrawlStage(settings=settings)
        self.extract_stage = ExtractStage(settings=settings)
        self.embed_stage = EmbedStage(settings=settings)
        self.graph_update_stage = GraphUpdateStage(graph=graph)
        self.curate_stage = CurateStage(graph=graph, settings=settings)

    async def run(self) -> dict[str, Any]:
        """Execute the full pipeline."""
        result = PipelineResult()
        start_time = time.time()

        logger.info("pipeline_started", targets=self.settings.pipeline_targets)

        # ── Stage 1: CRAWL ──
        crawl_results = await self._run_stage(
            "crawl",
            self._crawl,
            result,
        )

        if not crawl_results:
            result.status = "failed"
            result.duration_seconds = time.time() - start_time
            return result.to_dict()

        result.crawl_results = crawl_results

        # ── Stage 2: EXTRACT ──
        extraction_results = await self._run_stage(
            "extract",
            lambda: self._extract(crawl_results),
            result,
        )

        if not extraction_results:
            extraction_results = []
        result.extraction_results = extraction_results

        # ── Stage 3: EMBED ──
        embedding_results = await self._run_stage(
            "embed",
            lambda: self._embed(crawl_results),
            result,
        )

        # ── Stage 4: GRAPH_UPDATE ──
        if extraction_results or embedding_results:
            graph_result = await self._run_stage(
                "graph_update",
                lambda: self._graph_update(extraction_results, embedding_results or []),
                result,
            )
            result.graph_update_result = graph_result

        # ── Stage 5: CURATE ──
        curation_result = await self._run_stage(
            "curate",
            self._curate,
            result,
        )
        result.curation_result = curation_result

        result.status = "completed" if not result.stages_failed else "partial"
        result.duration_seconds = time.time() - start_time

        logger.info(
            "pipeline_completed",
            status=result.status,
            duration=result.duration_seconds,
            completed=result.stages_completed,
            failed=result.stages_failed,
        )

        return result.to_dict()

    async def _run_stage(self, name: str, fn, result: PipelineResult):
        """Run a stage with retry and error isolation."""
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                logger.info("stage_started", stage=name, attempt=attempt)
                output = await fn()
                result.stages_completed.append(name)
                logger.info("stage_completed", stage=name)
                return output
            except Exception as exc:
                logger.error(
                    "stage_failed",
                    stage=name,
                    attempt=attempt,
                    error=str(exc),
                )
                if attempt == self.MAX_RETRIES:
                    result.stages_failed.append(name)
                    result.errors.append(f"{name}: {exc}")
                    return None

    async def _crawl(self) -> list[CrawlResult]:
        """Run crawl stage for all target repos."""
        results = []
        for owner, repo in self.settings.target_repos:
            crawl_result = await self.crawl_stage.run(owner, repo)
            results.append(crawl_result)
        return results

    async def _extract(self, crawl_results: list[CrawlResult]) -> list[ExtractionResult]:
        """Run extract stage on all crawl results."""
        results = []
        for crawl_result in crawl_results:
            extraction = await self.extract_stage.run(crawl_result)
            results.append(extraction)
        return results

    async def _embed(self, crawl_results: list[CrawlResult]) -> list[EmbeddingResult]:
        """Run embed stage on all crawl results."""
        results = []
        for crawl_result in crawl_results:
            embedding = await self.embed_stage.run(crawl_result)
            results.append(embedding)
        return results

    async def _graph_update(
        self,
        extraction_results: list[ExtractionResult],
        embedding_results: list[EmbeddingResult],
    ) -> GraphUpdateResult:
        """Run graph update stage."""
        return await self.graph_update_stage.run(extraction_results, embedding_results)

    async def _curate(self) -> CurationResult:
        """Run curation stage."""
        return await self.curate_stage.run()
