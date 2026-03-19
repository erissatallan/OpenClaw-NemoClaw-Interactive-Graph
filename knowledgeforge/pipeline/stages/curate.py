"""CURATE stage — agent reviews graph with CoT reasoning (SPEC §2.2 Stage: CURATE)."""

from __future__ import annotations

import json
import logging

from google import genai
from google.genai import types

from knowledgeforge.config import Settings
from knowledgeforge.graph.base import GraphClient
from knowledgeforge.models import CurationAction, CurationResult

logger = logging.getLogger(__name__)

CURATION_PROMPT = """You are a knowledge graph curation agent. Your job is to review recent additions to a code knowledge graph and ensure quality.

**Current graph statistics:**
{stats}

**Recent entities added (sample):**
{entities_sample}

**Your tasks:**
1. Review the entities for quality. Reject any that are low-quality or nonsensical.
2. Identify potential duplicates that should be merged.
3. Flag any contradictions or issues.
4. Assess whether the graph should be extended to include forks of the tracked repositories.

**You MUST think step by step (chain of thought).** For each decision, explain your reasoning.

Return your analysis as JSON:
{{
  "actions": [
    {{
      "action": "approve" | "reject" | "merge" | "flag",
      "entity_ids": ["<qualified_name>", ...],
      "reasoning": "<detailed explanation of why this action is taken>",
      "confidence": <0.0-1.0>
    }}
  ],
  "overall_assessment": "<1-2 paragraph assessment of graph quality>",
  "should_expand_to_forks": {{
    "recommendation": true | false,
    "reasoning": "<why or why not>"
  }}
}}

Think carefully. Explain each decision.
"""


class CurateStage:
    """Curation agent that reviews graph quality using Gemini 2.5 Flash with CoT."""

    def __init__(self, graph: GraphClient, settings: Settings):
        self.graph = graph
        self.settings = settings
        self._client: genai.Client | None = None

    def _get_client(self) -> genai.Client:
        if self._client is None:
            self._client = genai.Client(api_key=self.settings.gemini_api_key)
        return self._client

    async def run(self) -> CurationResult:
        """Run the curation agent over the current graph state."""
        logger.info("curate_started")

        # Gather graph context
        stats = await self.graph.get_stats()
        entities_sample = await self.graph.query("*")
        sample = entities_sample[:30]  # Limit sample size

        # Format for prompt
        stats_str = json.dumps(stats.model_dump(), default=str, indent=2)
        entities_str = json.dumps(
            [
                {
                    "id": e.get("id", ""),
                    "label": e.get("_label", ""),
                    "name": e.get("name", e.get("qualified_name", "")),
                    "description": e.get("description", "")[:200],
                    "confidence": e.get("confidence", 1.0),
                }
                for e in sample
            ],
            indent=2,
        )

        prompt = CURATION_PROMPT.format(stats=stats_str, entities_sample=entities_str)

        try:
            client = self._get_client()
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=4096,
                    response_mime_type="application/json",
                ),
            )

            text = response.text.strip()
            data = json.loads(text)

            actions = [
                CurationAction(
                    action=a["action"],
                    entity_ids=a.get("entity_ids", []),
                    reasoning=a.get("reasoning", ""),
                    confidence=a.get("confidence", 0.8),
                )
                for a in data.get("actions", [])
            ]

            overall = data.get("overall_assessment", "")
            fork_rec = data.get("should_expand_to_forks", {})
            reasoning_trace = (
                f"## Overall Assessment\n{overall}\n\n"
                f"## Fork Expansion\n"
                f"Recommendation: {'Expand' if fork_rec.get('recommendation') else 'Do not expand'}\n"
                f"Reasoning: {fork_rec.get('reasoning', 'N/A')}\n\n"
                f"## Actions Taken\n"
            )
            for action in actions:
                reasoning_trace += (
                    f"- **{action.action.upper()}** {', '.join(action.entity_ids)}: "
                    f"{action.reasoning}\n"
                )

            result = CurationResult(actions=actions, reasoning_trace=reasoning_trace)
            logger.info("curate_completed", actions=len(actions))
            return result

        except Exception as exc:
            logger.error("curate_failed", error=str(exc))
            return CurationResult(
                actions=[],
                reasoning_trace=f"Curation failed: {exc}",
            )
