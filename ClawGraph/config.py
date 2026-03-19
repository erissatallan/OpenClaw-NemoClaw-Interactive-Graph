"""Application configuration — loaded from environment variables (SPEC §5)."""

from __future__ import annotations

import uuid

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Twelve-factor app configuration via environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Required ──
    gemini_api_key: str = Field(default="", description="Google AI Studio API key")
    github_token: str = Field(default="", description="GitHub PAT for API access")

    # ── Graph backend ──
    graph_backend: str = Field(default="memory", description="'neo4j' or 'memory'")
    neo4j_uri: str = Field(default="", description="Neo4j Aura connection URI")
    neo4j_username: str = Field(default="neo4j")
    neo4j_password: str = Field(default="")

    # ── Pipeline ──
    pipeline_schedule: str = Field(default="0 3 * * *", description="Cron schedule")
    pipeline_targets: str = Field(
        default="openclaw/openclaw,NVIDIA/NemoClaw",
        description="Comma-separated owner/repo targets",
    )

    # ── Security ──
    canary_secret: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Canary token for prompt injection detection",
    )

    # ── Server ──
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    log_level: str = Field(default="INFO")

    @property
    def target_repos(self) -> list[tuple[str, str]]:
        """Parse PIPELINE_TARGETS into list of (owner, repo) tuples."""
        pairs = []
        for target in self.pipeline_targets.split(","):
            target = target.strip()
            if "/" in target:
                owner, repo = target.split("/", 1)
                pairs.append((owner.strip(), repo.strip()))
        return pairs


def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
