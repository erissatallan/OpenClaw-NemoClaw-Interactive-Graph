"""MCP Server entry point — registers all 9 GitHub tools (SPEC §2.1).

Run standalone: python -m knowledgeforge.github_mcp_server.server
"""

from __future__ import annotations

import json
import os

from mcp.server.fastmcp import FastMCP

from knowledgeforge.github_mcp_server.github_client import GitHubClient
from knowledgeforge.github_mcp_server import tools as github_tools

# ── MCP Server ──

mcp = FastMCP(
    "KnowledgeForge GitHub MCP",
    description="Custom MCP server for GitHub API interactions — repos, code, issues, PRs, forks, contributors",
)

_client: GitHubClient | None = None


def _get_client() -> GitHubClient:
    global _client
    if _client is None:
        token = os.environ.get("GITHUB_TOKEN", "")
        _client = GitHubClient(token=token)
    return _client


# ── Tool Registrations ──


@mcp.tool()
async def get_repo_info(owner: str, repo: str) -> str:
    """Fetch repository metadata including stars, forks, language, description, and topics.

    Args:
        owner: Repository owner (e.g., 'openclaw')
        repo: Repository name (e.g., 'openclaw')
    """
    result = await github_tools.get_repo_info(_get_client(), owner, repo)
    return json.dumps(result, indent=2)


@mcp.tool()
async def list_repo_files(owner: str, repo: str, path: str = "", ref: str = "") -> str:
    """List repository file tree with types and sizes.

    Args:
        owner: Repository owner
        repo: Repository name
        path: Optional subdirectory path
        ref: Optional git ref (branch, tag, commit SHA)
    """
    result = await github_tools.list_repo_files(_get_client(), owner, repo, path=path, ref=ref)
    return json.dumps(result, indent=2)


@mcp.tool()
async def get_file_content(owner: str, repo: str, path: str, ref: str = "") -> str:
    """Fetch raw file content (base64-decoded) from a repository.

    Args:
        owner: Repository owner
        repo: Repository name
        path: File path within the repository
        ref: Optional git ref
    """
    result = await github_tools.get_file_content(_get_client(), owner, repo, path, ref=ref)
    return json.dumps(result, indent=2)


@mcp.tool()
async def search_code(query: str, owner: str = "", repo: str = "") -> str:
    """Search code across repositories using GitHub search API.

    Args:
        query: Search query string
        owner: Optional — filter to repos owned by this user/org
        repo: Optional — filter to this specific repo
    """
    result = await github_tools.search_code(_get_client(), query, owner=owner, repo=repo)
    return json.dumps(result, indent=2)


@mcp.tool()
async def list_issues(
    owner: str, repo: str, state: str = "open", labels: str = "", per_page: int = 30
) -> str:
    """Fetch issues with title, body, labels, and comments count.

    Args:
        owner: Repository owner
        repo: Repository name
        state: Issue state filter — 'open', 'closed', or 'all'
        labels: Comma-separated label names to filter by
        per_page: Number of results per page (max 100)
    """
    result = await github_tools.list_issues(
        _get_client(), owner, repo, state=state, labels=labels, per_page=per_page
    )
    return json.dumps(result, indent=2)


@mcp.tool()
async def list_pull_requests(
    owner: str, repo: str, state: str = "all", per_page: int = 30
) -> str:
    """Fetch pull requests with title, body, merge status.

    Args:
        owner: Repository owner
        repo: Repository name
        state: PR state filter — 'open', 'closed', or 'all'
        per_page: Number of results per page
    """
    result = await github_tools.list_pull_requests(
        _get_client(), owner, repo, state=state, per_page=per_page
    )
    return json.dumps(result, indent=2)


@mcp.tool()
async def list_forks(owner: str, repo: str, sort: str = "stargazers") -> str:
    """List repository forks sorted by stargazers, newest, or oldest.

    Args:
        owner: Repository owner
        repo: Repository name
        sort: Sort order — 'stargazers', 'newest', 'oldest'
    """
    result = await github_tools.list_forks(_get_client(), owner, repo, sort=sort)
    return json.dumps(result, indent=2)


@mcp.tool()
async def get_commit_history(
    owner: str, repo: str, path: str = "", per_page: int = 20
) -> str:
    """Fetch recent commits with messages, authors, and dates.

    Args:
        owner: Repository owner
        repo: Repository name
        path: Optional — filter commits affecting this file path
        per_page: Number of commits to return
    """
    result = await github_tools.get_commit_history(
        _get_client(), owner, repo, path=path, per_page=per_page
    )
    return json.dumps(result, indent=2)


@mcp.tool()
async def get_contributors(owner: str, repo: str) -> str:
    """List repository contributors with commit counts.

    Args:
        owner: Repository owner
        repo: Repository name
    """
    result = await github_tools.get_contributors(_get_client(), owner, repo)
    return json.dumps(result, indent=2)


# ── Entry point ──

if __name__ == "__main__":
    mcp.run()
