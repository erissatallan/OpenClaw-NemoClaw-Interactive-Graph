"""Pipeline scheduler — cron-based scheduling via APScheduler (SPEC §2.2)."""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from knowledgeforge.config import Settings
from knowledgeforge.graph.base import GraphClient

logger = logging.getLogger(__name__)


class PipelineScheduler:
    """Manages scheduled pipeline runs using APScheduler."""

    def __init__(self, graph: GraphClient, settings: Settings):
        self.graph = graph
        self.settings = settings
        self._scheduler = AsyncIOScheduler()

    def start(self):
        """Start the scheduler with the configured cron schedule."""
        cron_expr = self.settings.pipeline_schedule
        parts = cron_expr.split()

        if len(parts) != 5:
            logger.error("Invalid cron expression: %s", cron_expr)
            return

        trigger = CronTrigger(
            minute=parts[0],
            hour=parts[1],
            day=parts[2],
            month=parts[3],
            day_of_week=parts[4],
        )

        self._scheduler.add_job(
            self._run_pipeline,
            trigger=trigger,
            id="knowledge_pipeline",
            name="KnowledgeForge Pipeline",
            replace_existing=True,
        )

        self._scheduler.start()
        logger.info("scheduler_started", schedule=cron_expr)

    async def _run_pipeline(self):
        """Execute the pipeline."""
        from knowledgeforge.pipeline.orchestrator import PipelineOrchestrator

        logger.info("scheduled_pipeline_run_started")
        orchestrator = PipelineOrchestrator(graph=self.graph, settings=self.settings)
        result = await orchestrator.run()
        logger.info("scheduled_pipeline_run_completed", result=result)

    def stop(self):
        """Stop the scheduler."""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("scheduler_stopped")
