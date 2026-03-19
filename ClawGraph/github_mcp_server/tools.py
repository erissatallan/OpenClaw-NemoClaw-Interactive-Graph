"""MCP tool implementations — wraps GitHubClient methods as MCP tools (SPEC §2.1)."""

from __future__ import annotations

from typing import Any

from ClawGraph.github_mcp_server.github_client import GitHubClient


async def get_repo_info(client: GitHubClient, owner: str, repo: str) -> dict[str, Any]:
    """Fetch repository metadata including stars, forks, language, description, and topics."""
    data = await client.get_repo(owner, repo)
    return {
        "name": data.get("full_name", ""),
        "description": data.get("description", ""),
        "url": data.get("html_url", ""),
        "stars": data.get("stargazers_count", 0),
        "forks": data.get("forks_count", 0),
        "language": data.get("language", ""),
        "topics": data.get("topics", []),
        "default_branch": data.get("default_branch", "main"),
        "created_at": data.get("created_at", ""),
        "updated_at": data.get("updated_at", ""),
        "open_issues_count": data.get("open_issues_count", 0),
        "license": (data.get("license") or {}).get("spdx_id", ""),
    }


async def list_repo_files(
    client: GitHubClient,
    owner: str,
    repo: str,
    path: str = "",
    ref: str = "",
) -> list[dict[str, Any]]:
    """List repository file tree with types and sizes."""
    items = await client.list_repo_files(owner, repo, path=path, ref=ref)
    return [
        {
            "name": item.get("name", ""),
            "path": item.get("path", ""),
            "type": item.get("type", ""),
            "size": item.get("size", 0),
            "sha": item.get("sha", ""),
        }
        for item in items
    ]


async def get_file_content(
    client: GitHubClient,
    owner: str,
    repo: str,
    path: str,
    ref: str = "",
) -> dict[str, str]:
    """Fetch raw file content (base64-decoded)."""
    content = await client.get_file_content(owner, repo, path, ref=ref)
    return {"path": path, "content": content}


async def search_code(
    client: GitHubClient,
    query: str,
    owner: str = "",
    repo: str = "",
) -> list[dict[str, Any]]:
    """Search code across repos using GitHub search API."""
    items = await client.search_code(query, owner=owner, repo=repo)
    return [
        {
            "path": item.get("path", ""),
            "repository": item.get("repository", {}).get("full_name", ""),
            "url": item.get("html_url", ""),
            "score": item.get("score", 0),
        }
        for item in items
    ]


async def list_issues(
    client: GitHubClient,
    owner: str,
    repo: str,
    state: str = "open",
    labels: str = "",
    per_page: int = 30,
) -> list[dict[str, Any]]:
    """Fetch issues with title, body, labels, and comments count."""
    issues = await client.list_issues(owner, repo, state=state, labels=labels, per_page=per_page)
    # Filter out pull requests (GitHub API returns PRs as issues too)
    return [
        {
            "number": issue.get("number"),
            "title": issue.get("title", ""),
            "state": issue.get("state", ""),
            "body": (issue.get("body") or "")[:500],
            "labels": [l.get("name", "") for l in issue.get("labels", [])],
            "comments": issue.get("comments", 0),
            "created_at": issue.get("created_at", ""),
            "updated_at": issue.get("updated_at", ""),
            "user": issue.get("user", {}).get("login", ""),
        }
        for issue in issues
        if "pull_request" not in issue
    ]


async def list_pull_requests(
    client: GitHubClient,
    owner: str,
    repo: str,
    state: str = "all",
    per_page: int = 30,
) -> list[dict[str, Any]]:
    """Fetch PRs with title, body, merge status, and diff stats."""
    prs = await client.list_pull_requests(owner, repo, state=state, per_page=per_page)
    return [
        {
            "number": pr.get("number"),
            "title": pr.get("title", ""),
            "state": pr.get("state", ""),
            "body": (pr.get("body") or "")[:500],
            "merged_at": pr.get("merged_at"),
            "user": pr.get("user", {}).get("login", ""),
            "created_at": pr.get("created_at", ""),
            "updated_at": pr.get("updated_at", ""),
        }
        for pr in prs
    ]


async def list_forks(
    client: GitHubClient,
    owner: str,
    repo: str,
    sort: str = "stargazers",
) -> list[dict[str, Any]]:
    """List forks sorted by stargazers/newest/oldest."""
    forks = await client.list_forks(owner, repo, sort=sort)
    return [
        {
            "full_name": fork.get("full_name", ""),
            "owner": fork.get("owner", {}).get("login", ""),
            "stars": fork.get("stargazers_count", 0),
            "forks": fork.get("forks_count", 0),
            "updated_at": fork.get("updated_at", ""),
            "url": fork.get("html_url", ""),
        }
        for fork in forks
    ]


async def get_commit_history(
    client: GitHubClient,
    owner: str,
    repo: str,
    path: str = "",
    per_page: int = 20,
) -> list[dict[str, Any]]:
    """Fetch recent commits with messages, authors, and diffs."""
    commits = await client.get_commit_history(owner, repo, path=path, per_page=per_page)
    return [
        {
            "sha": commit.get("sha", "")[:8],
            "message": (commit.get("commit", {}).get("message") or "")[:200],
            "author": commit.get("commit", {}).get("author", {}).get("name", ""),
            "date": commit.get("commit", {}).get("author", {}).get("date", ""),
            "url": commit.get("html_url", ""),
        }
        for commit in commits
    ]


async def get_contributors(
    client: GitHubClient,
    owner: str,
    repo: str,
) -> list[dict[str, Any]]:
    """List contributors with commit counts."""
    contributors = await client.get_contributors(owner, repo)
    return [
        {
            "username": c.get("login", ""),
            "contributions": c.get("contributions", 0),
            "avatar_url": c.get("avatar_url", ""),
            "url": c.get("html_url", ""),
        }
        for c in contributors
    ]
