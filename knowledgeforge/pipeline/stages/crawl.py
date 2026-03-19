"""CRAWL stage — fetches repo data via GitHub API (SPEC §2.2 Stage: CRAWL)."""

from __future__ import annotations

import logging
from typing import Any

from knowledgeforge.config import Settings
from knowledgeforge.github_mcp_server.github_client import GitHubClient
from knowledgeforge.models import CrawlResult

logger = logging.getLogger(__name__)

# File extensions we care about for knowledge extraction
SOURCE_EXTENSIONS = {".py", ".ts", ".js", ".tsx", ".jsx", ".md", ".json", ".yaml", ".yml", ".toml"}
# Max file size to fetch (100KB)
MAX_FILE_SIZE = 100_000


class CrawlStage:
    """Crawl stage: fetches README, source files, issues, PRs, and contributors."""

    def __init__(self, settings: Settings):
        self.settings = settings

    async def run(self, owner: str, repo: str) -> CrawlResult:
        """Crawl a single repository."""
        client = GitHubClient(token=self.settings.github_token)

        try:
            logger.info("crawl_started", owner=owner, repo=repo)
            result = CrawlResult(repo=f"{owner}/{repo}")

            # Fetch file tree and content
            files = await self._crawl_files(client, owner, repo)
            result.files = files

            # Fetch issues (last 50 open)
            try:
                issues = await client.list_issues(owner, repo, state="open", per_page=50)
                result.issues = [
                    self._normalize_issue(i) for i in issues if "pull_request" not in i
                ]
            except Exception as exc:
                logger.warning("crawl_issues_failed", error=str(exc))

            # Fetch PRs (last 30 merged)
            try:
                prs = await client.list_pull_requests(owner, repo, state="closed", per_page=30)
                result.pull_requests = [self._normalize_pr(pr) for pr in prs if pr.get("merged_at")]
            except Exception as exc:
                logger.warning("crawl_prs_failed", error=str(exc))

            # Fetch contributors
            try:
                contributors = await client.get_contributors(owner, repo)
                result.contributors = [
                    {"username": c.get("login", ""), "contributions": c.get("contributions", 0)}
                    for c in contributors
                ]
            except Exception as exc:
                logger.warning("crawl_contributors_failed", error=str(exc))

            logger.info(
                "crawl_completed",
                repo=f"{owner}/{repo}",
                files=len(result.files),
                issues=len(result.issues),
                prs=len(result.pull_requests),
            )
            return result

        finally:
            await client.close()

    async def _crawl_files(
        self, client: GitHubClient, owner: str, repo: str, path: str = ""
    ) -> dict[str, str]:
        """Recursively crawl the file tree and fetch source file content."""
        files: dict[str, str] = {}

        try:
            items = await client.list_repo_files(owner, repo, path=path)
        except Exception as exc:
            logger.warning("crawl_files_failed", path=path, error=str(exc))
            return files

        for item in items:
            item_path = item.get("path", "")
            item_type = item.get("type", "")
            item_size = item.get("size", 0)

            if item_type == "dir":
                # Recurse into directories (skip node_modules, .git, etc.)
                dirname = item.get("name", "")
                if dirname in {"node_modules", ".git", "dist", "build", "__pycache__", ".next"}:
                    continue
                sub_files = await self._crawl_files(client, owner, repo, path=item_path)
                files.update(sub_files)

            elif item_type == "file":
                # Check extension and size
                ext = "." + item_path.rsplit(".", 1)[-1] if "." in item_path else ""
                if ext not in SOURCE_EXTENSIONS:
                    continue
                if item_size > MAX_FILE_SIZE:
                    continue

                try:
                    content = await client.get_file_content(owner, repo, item_path)
                    files[item_path] = content
                except Exception as exc:
                    logger.debug("crawl_file_content_failed", path=item_path, error=str(exc))

        return files

    @staticmethod
    def _normalize_issue(issue: dict[str, Any]) -> dict[str, Any]:
        return {
            "number": issue.get("number"),
            "title": issue.get("title", ""),
            "body": (issue.get("body") or "")[:1000],
            "state": issue.get("state", ""),
            "labels": [l.get("name", "") for l in issue.get("labels", [])],
            "user": issue.get("user", {}).get("login", ""),
        }

    @staticmethod
    def _normalize_pr(pr: dict[str, Any]) -> dict[str, Any]:
        return {
            "number": pr.get("number"),
            "title": pr.get("title", ""),
            "body": (pr.get("body") or "")[:1000],
            "merged_at": pr.get("merged_at"),
            "user": pr.get("user", {}).get("login", ""),
        }
