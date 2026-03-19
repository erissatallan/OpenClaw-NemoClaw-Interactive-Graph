"""EMBED stage — Gemini embedding generation with smart chunking (SPEC §2.2 Stage: EMBED)."""

from __future__ import annotations

import logging
import re

from google import genai

from knowledgeforge.config import Settings
from knowledgeforge.models import CodeChunk, CrawlResult, EmbeddingResult

logger = logging.getLogger(__name__)

MAX_CHUNK_CHARS = 4000  # ~2000 tokens
EMBEDDING_MODEL = "models/text-embedding-004"


class EmbedStage:
    """Generates embeddings for code and documentation chunks."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._client: genai.Client | None = None

    def _get_client(self) -> genai.Client:
        if self._client is None:
            self._client = genai.Client(api_key=self.settings.gemini_api_key)
        return self._client

    async def run(self, crawl_result: CrawlResult) -> EmbeddingResult:
        """Chunk files and generate embeddings."""
        chunks: list[CodeChunk] = []

        logger.info("embed_started", repo=crawl_result.repo, files=len(crawl_result.files))

        for file_path, content in crawl_result.files.items():
            language = self._detect_language(file_path)
            file_chunks = self._chunk_file(file_path, content, language)
            chunks.extend(file_chunks)

        # Generate embeddings in batches
        for i in range(0, len(chunks), 20):
            batch = chunks[i : i + 20]
            texts = [c.text for c in batch]

            try:
                client = self._get_client()
                response = client.models.embed_content(
                    model=EMBEDDING_MODEL,
                    contents=texts,
                )

                for j, embedding_obj in enumerate(response.embeddings):
                    batch[j].embedding = embedding_obj.values

            except Exception as exc:
                logger.warning("embed_batch_failed", batch_start=i, error=str(exc))

        embedded_count = sum(1 for c in chunks if c.embedding is not None)
        logger.info(
            "embed_completed",
            repo=crawl_result.repo,
            total_chunks=len(chunks),
            embedded=embedded_count,
        )

        return EmbeddingResult(chunks=chunks, source_repo=crawl_result.repo)

    def _chunk_file(self, path: str, content: str, language: str) -> list[CodeChunk]:
        """Split a file into chunks based on language."""
        if language == "markdown":
            return self._chunk_markdown(path, content)
        elif language in ("python", "typescript", "javascript"):
            return self._chunk_code(path, content, language)
        else:
            return self._chunk_simple(path, content, language)

    def _chunk_markdown(self, path: str, content: str) -> list[CodeChunk]:
        """Chunk markdown by headings."""
        chunks: list[CodeChunk] = []
        sections = re.split(r"(?=^#{1,3}\s)", content, flags=re.MULTILINE)

        line_offset = 0
        for section in sections:
            section = section.strip()
            if not section:
                continue

            lines = section.split("\n")
            if len(section) > MAX_CHUNK_CHARS:
                section = section[:MAX_CHUNK_CHARS]

            chunks.append(
                CodeChunk(
                    text=section,
                    path=path,
                    start_line=line_offset + 1,
                    end_line=line_offset + len(lines),
                    language="markdown",
                )
            )
            line_offset += len(lines)

        return chunks

    def _chunk_code(self, path: str, content: str, language: str) -> list[CodeChunk]:
        """Chunk code by class/function definitions."""
        chunks: list[CodeChunk] = []
        lines = content.split("\n")

        # Pattern for function/class definitions
        if language == "python":
            pattern = re.compile(r"^(class |def |async def )", re.MULTILINE)
        else:
            # TypeScript/JavaScript
            pattern = re.compile(
                r"^(export |)(class |function |const |interface |type |async function )",
                re.MULTILINE,
            )

        # Find definition boundaries
        matches = list(pattern.finditer(content))

        if not matches:
            return self._chunk_simple(path, content, language)

        # Create chunks between definitions
        for i, match in enumerate(matches):
            start_pos = match.start()
            end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(content)

            chunk_text = content[start_pos:end_pos].strip()
            if not chunk_text:
                continue

            start_line = content[:start_pos].count("\n") + 1
            end_line = content[:end_pos].count("\n") + 1

            if len(chunk_text) > MAX_CHUNK_CHARS:
                chunk_text = chunk_text[:MAX_CHUNK_CHARS]

            chunks.append(
                CodeChunk(
                    text=chunk_text,
                    path=path,
                    start_line=start_line,
                    end_line=end_line,
                    language=language,
                )
            )

        return chunks

    def _chunk_simple(self, path: str, content: str, language: str) -> list[CodeChunk]:
        """Fall-back: chunk by line count."""
        chunks: list[CodeChunk] = []
        lines = content.split("\n")
        chunk_size = 60  # lines per chunk

        for i in range(0, len(lines), chunk_size):
            chunk_lines = lines[i : i + chunk_size]
            text = "\n".join(chunk_lines).strip()
            if not text:
                continue

            chunks.append(
                CodeChunk(
                    text=text[:MAX_CHUNK_CHARS],
                    path=path,
                    start_line=i + 1,
                    end_line=i + len(chunk_lines),
                    language=language,
                )
            )

        return chunks

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
