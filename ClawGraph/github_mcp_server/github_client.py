"""Async GitHub REST API client with rate-limit handling (SPEC §2.1)."""

from __future__ import annotations

import asyncio
import base64
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"


class GitHubClientError(Exception):
    """Raised when a GitHub API call fails."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class GitHubClient:
    """Async HTTP client for the GitHub REST API.

    Handles authentication, rate limiting (HTTP 429), and pagination.
    """

    def __init__(self, token: str = ""):
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"

        self._client = httpx.AsyncClient(
            base_url=GITHUB_API_BASE,
            headers=headers,
            timeout=30.0,
        )

    async def close(self):
        await self._client.aclose()

    async def _request(
        self, method: str, path: str, params: dict | None = None, max_retries: int = 3
    ) -> Any:
        """Make an API request with retry on rate limits."""
        for attempt in range(max_retries):
            resp = await self._client.request(method, path, params=params)

            if resp.status_code == 200:
                return resp.json()

            if resp.status_code == 429 or (
                resp.status_code == 403 and "rate limit" in resp.text.lower()
            ):
                retry_after = int(resp.headers.get("Retry-After", "60"))
                wait_time = min(retry_after, 120)
                logger.warning(
                    "Rate limited by GitHub API, waiting %ds (attempt %d/%d)",
                    wait_time, attempt + 1, max_retries,
                )
                await asyncio.sleep(wait_time)
                continue

            if resp.status_code == 404:
                raise GitHubClientError(f"Not found: {path}", status_code=404)

            raise GitHubClientError(
                f"GitHub API error: {resp.status_code} — {resp.text[:200]}",
                status_code=resp.status_code,
            )

        raise GitHubClientError("Max retries exceeded for rate-limited request")

    async def get(self, path: str, params: dict | None = None) -> Any:
        return await self._request("GET", path, params=params)

    # ── High-level methods ──

    async def get_repo(self, owner: str, repo: str) -> dict:
        """Fetch repository metadata."""
        return await self.get(f"/repos/{owner}/{repo}")

    async def list_repo_files(
        self, owner: str, repo: str, path: str = "", ref: str = ""
    ) -> list[dict]:
        """List files in a repository directory."""
        params = {}
        if ref:
            params["ref"] = ref
        endpoint = f"/repos/{owner}/{repo}/contents/{path}"
        result = await self.get(endpoint, params=params)
        if isinstance(result, dict):
            return [result]
        return result

    async def get_file_content(
        self, owner: str, repo: str, path: str, ref: str = ""
    ) -> str:
        """Fetch and decode file content (base64 → UTF-8)."""
        params = {}
        if ref:
            params["ref"] = ref
        data = await self.get(f"/repos/{owner}/{repo}/contents/{path}", params=params)
        if isinstance(data, dict) and data.get("encoding") == "base64":
            return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
        if isinstance(data, dict) and "content" in data:
            return data["content"]
        raise GitHubClientError(f"Unexpected content format for {path}")

    async def search_code(
        self, query: str, owner: str = "", repo: str = ""
    ) -> list[dict]:
        """Search code across repositories."""
        q = query
        if owner and repo:
            q += f" repo:{owner}/{repo}"
        elif owner:
            q += f" user:{owner}"
        data = await self.get("/search/code", params={"q": q, "per_page": 20})
        return data.get("items", [])

    async def list_issues(
        self,
        owner: str,
        repo: str,
        state: str = "open",
        labels: str = "",
        per_page: int = 30,
    ) -> list[dict]:
        """Fetch issues from a repository."""
        params: dict[str, Any] = {"state": state, "per_page": per_page, "sort": "updated"}
        if labels:
            params["labels"] = labels
        return await self.get(f"/repos/{owner}/{repo}/issues", params=params)

    async def list_pull_requests(
        self, owner: str, repo: str, state: str = "all", per_page: int = 30
    ) -> list[dict]:
        """Fetch pull requests from a repository."""
        params = {"state": state, "per_page": per_page, "sort": "updated"}
        return await self.get(f"/repos/{owner}/{repo}/pulls", params=params)

    async def list_forks(
        self, owner: str, repo: str, sort: str = "stargazers", per_page: int = 30
    ) -> list[dict]:
        """List forks sorted by stargazers, newest, or oldest."""
        params = {"sort": sort, "per_page": per_page}
        return await self.get(f"/repos/{owner}/{repo}/forks", params=params)

    async def get_commit_history(
        self, owner: str, repo: str, path: str = "", per_page: int = 20
    ) -> list[dict]:
        """Fetch recent commits."""
        params: dict[str, Any] = {"per_page": per_page}
        if path:
            params["path"] = path
        return await self.get(f"/repos/{owner}/{repo}/commits", params=params)

    async def get_contributors(
        self, owner: str, repo: str, per_page: int = 30
    ) -> list[dict]:
        """List contributors with commit counts."""
        params = {"per_page": per_page}
        return await self.get(f"/repos/{owner}/{repo}/contributors", params=params)
