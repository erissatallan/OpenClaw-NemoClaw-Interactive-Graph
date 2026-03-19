"""RAG answer generator — Gemini 2.5 Flash with chain-of-thought (SPEC §2.4)."""

from __future__ import annotations

import logging

from google import genai
from google.genai import types

from knowledgeforge.config import Settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are KnowledgeForge, an expert AI assistant that answers questions about the OpenClaw and NemoClaw open-source projects using a knowledge graph.

You MUST follow this response format:

🔍 **Retrieved context:**
- List the key entities and code chunks you are using to answer

💭 **Reasoning:**
- Explain your chain of thought step by step
- Reference specific code, functions, or architectural patterns
- If you are uncertain, say so explicitly

📝 **Answer:**
- Provide a clear, direct answer
- Include source citations in [file:line] format where applicable

Rules:
- Only use information from the provided context
- If you cannot answer from the context, say "I don't have enough information in the knowledge graph to answer this."
- Never fabricate code or file paths
- Be specific — reference actual class names, function signatures, and file locations
"""

RAG_PROMPT = """Using the following knowledge graph context, answer the user's question.

**Relevant entities from the knowledge graph:**
{entities}

**Relevant code chunks:**
{code_chunks}

**User question:** {question}

Remember: Think step by step. Show your reasoning. Cite sources.
"""


class RAGGenerator:
    """Generates grounded answers using Gemini 2.5 Flash with CoT."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._client: genai.Client | None = None

    def _get_client(self) -> genai.Client:
        if self._client is None:
            self._client = genai.Client(api_key=self.settings.gemini_api_key)
        return self._client

    async def generate(
        self,
        question: str,
        entities: list[dict],
        code_chunks: list[dict],
    ) -> tuple[str, str]:
        """Generate a RAG answer with CoT.

        Returns (answer_text, reasoning_trace).
        """
        # Format entities
        entities_str = "\n".join(
            f"- **{e.get('_label', 'Entity')}:** `{e.get('qualified_name', e.get('id', 'unknown'))}` "
            f"— {e.get('description', e.get('name', ''))}"
            for e in entities[:15]
        )
        if not entities_str:
            entities_str = "(No matching entities found)"

        # Format code chunks
        chunks_str = ""
        for chunk in code_chunks[:10]:
            path = chunk.get("path", "unknown")
            start = chunk.get("start_line", "?")
            end = chunk.get("end_line", "?")
            text = chunk.get("text", "")[:1500]
            lang = chunk.get("language", "")
            chunks_str += f"\n**[{path}:{start}-{end}]**\n```{lang}\n{text}\n```\n"
        if not chunks_str:
            chunks_str = "(No matching code chunks found)"

        prompt = RAG_PROMPT.format(
            entities=entities_str,
            code_chunks=chunks_str,
            question=question,
        )

        try:
            client = self._get_client()
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.3,
                    max_output_tokens=4096,
                ),
            )

            full_text = response.text.strip()

            # Extract reasoning trace and answer
            reasoning = ""
            answer = full_text

            if "💭" in full_text and "📝" in full_text:
                parts = full_text.split("📝")
                reasoning = parts[0].strip()
                answer = full_text

            return answer, reasoning

        except Exception as exc:
            logger.error("rag_generation_failed", error=str(exc))
            return (
                f"❌ Failed to generate answer: {exc}",
                f"Generation error: {exc}",
            )
