"""EXTRACT stage — Gemini Flash Lite entity/relationship extraction (SPEC §2.2 Stage: EXTRACT)."""

from __future__ import annotations

import json
import logging
from typing import Any

from google import genai
from google.genai import types

from ClawGraph.config import Settings
from ClawGraph.models import CrawlResult, Entity, ExtractionResult, Relationship

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """You are a code analysis expert. Analyze the following source file and extract structured information.

**File path:** {file_path}
**Language:** {language}
**Repository:** {repo}

**Source code:**
```
{content}
```

Extract ALL of the following and return as JSON:
{{
  "entities": [
    {{
      "qualified_name": "<repo>.<module_path>.<ClassName_or_function_name>",
      "label": "Module" | "Class" | "Function" | "Concept",
      "properties": {{
        "name": "<short name>",
        "description": "<1-2 sentence description>",
        "path": "<file path>",
        "signature": "<function signature if applicable>"
      }},
      "confidence": <0.0-1.0>
    }}
  ],
  "relationships": [
    {{
      "from_entity": "<qualified_name>",
      "to_entity": "<qualified_name>",
      "rel_type": "IMPORTS" | "EXTENDS" | "CALLS" | "HAS_METHOD" | "DEFINES" | "IMPLEMENTS",
      "confidence": <0.0-1.0>
    }}
  ]
}}

Rules:
- Use the repo name as the root namespace for qualified names
- For imports, use the full module path as the target qualified_name
- Set confidence < 0.7 for uncertain extractions
- Include ALL classes, functions, and meaningful constants
- For Markdown files, extract Concept entities for key topics
- Return ONLY valid JSON, no explanations
"""

BATCH_SIZE = 5  # Process files in batches to stay within rate limits


class ExtractStage:
    """Extracts entities and relationships from crawled files using Gemini Flash Lite."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._client: genai.Client | None = None

    def _get_client(self) -> genai.Client:
        if self._client is None:
            self._client = genai.Client(api_key=self.settings.gemini_api_key)
        return self._client

    async def run(self, crawl_result: CrawlResult) -> ExtractionResult:
        """Extract entities and relationships from all crawled files."""
        all_entities: list[Entity] = []
        all_relationships: list[Relationship] = []
        repo = crawl_result.repo

        logger.info("extract_started", repo=repo, files=len(crawl_result.files))

        # Process files in batches
        file_items = list(crawl_result.files.items())
        for i in range(0, len(file_items), BATCH_SIZE):
            batch = file_items[i : i + BATCH_SIZE]

            for file_path, content in batch:
                try:
                    entities, relationships = await self._extract_from_file(
                        repo, file_path, content
                    )
                    all_entities.extend(entities)
                    all_relationships.extend(relationships)
                except Exception as exc:
                    logger.warning("extract_file_failed", file=file_path, error=str(exc))

        # Extract from issues and PRs
        for issue in crawl_result.issues[:20]:  # Limit to avoid rate limits
            try:
                entities = self._extract_from_issue(repo, issue)
                all_entities.extend(entities)
            except Exception:
                pass

        logger.info(
            "extract_completed",
            repo=repo,
            entities=len(all_entities),
            relationships=len(all_relationships),
        )

        return ExtractionResult(
            entities=all_entities,
            relationships=all_relationships,
            source_repo=repo,
        )

    async def _extract_from_file(
        self, repo: str, file_path: str, content: str
    ) -> tuple[list[Entity], list[Relationship]]:
        """Extract entities and relationships from a single file using Gemini."""
        language = self._detect_language(file_path)

        # Truncate very long files
        if len(content) > 15000:
            content = content[:15000] + "\n... [truncated]"

        prompt = EXTRACTION_PROMPT.format(
            file_path=file_path,
            language=language,
            repo=repo,
            content=content,
        )

        client = self._get_client()
        response = client.models.generate_content(
            model="gemini-2.0-flash-lite",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=4096,
                response_mime_type="application/json",
            ),
        )

        text = response.text.strip()
        data = json.loads(text)

        entities = [
            Entity(
                qualified_name=e["qualified_name"],
                label=e["label"],
                properties=e.get("properties", {}),
                confidence=e.get("confidence", 0.8),
                source_path=file_path,
            )
            for e in data.get("entities", [])
        ]

        relationships = [
            Relationship(
                from_entity=r["from_entity"],
                to_entity=r["to_entity"],
                rel_type=r["rel_type"],
                confidence=r.get("confidence", 0.8),
            )
            for r in data.get("relationships", [])
        ]

        return entities, relationships

    @staticmethod
    def _extract_from_issue(repo: str, issue: dict[str, Any]) -> list[Entity]:
        """Extract a Concept entity from an issue."""
        return [
            Entity(
                qualified_name=f"{repo}.issues.{issue.get('number', 0)}",
                label="Concept",
                properties={
                    "name": issue.get("title", ""),
                    "description": issue.get("body", "")[:500],
                    "type": "issue",
                    "number": issue.get("number"),
                    "state": issue.get("state", ""),
                    "labels": issue.get("labels", []),
                },
                confidence=1.0,
            )
        ]

    @staticmethod
    def _detect_language(file_path: str) -> str:
        ext_map = {
            ".py": "python",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".js": "javascript",
            ".jsx": "javascript",
            ".md": "markdown",
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".toml": "toml",
        }
        ext = "." + file_path.rsplit(".", 1)[-1] if "." in file_path else ""
        return ext_map.get(ext, "unknown")
