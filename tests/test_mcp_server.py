"""Tests for GitHub MCP server tools (SPEC §2.1)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from knowledgeforge.github_mcp_server.github_client import GitHubClient, GitHubClientError
from knowledgeforge.github_mcp_server import tools


@pytest.fixture
def mock_client():
    """Create a mock GitHub client."""
    client = AsyncMock(spec=GitHubClient)
    return client


class TestGetRepoInfo:
    @pytest.mark.asyncio
    async def test_returns_normalized_data(self, mock_client):
        mock_client.get_repo.return_value = {
            "full_name": "openclaw/openclaw",
            "description": "Personal AI assistant",
            "html_url": "https://github.com/openclaw/openclaw",
            "stargazers_count": 1500,
            "forks_count": 200,
            "language": "TypeScript",
            "topics": ["ai", "assistant"],
            "default_branch": "main",
            "created_at": "2024-01-01",
            "updated_at": "2024-06-01",
            "open_issues_count": 42,
            "license": {"spdx_id": "MIT"},
        }

        result = await tools.get_repo_info(mock_client, "openclaw", "openclaw")
        assert result["name"] == "openclaw/openclaw"
        assert result["stars"] == 1500
        assert result["language"] == "TypeScript"
        assert result["license"] == "MIT"


class TestListRepoFiles:
    @pytest.mark.asyncio
    async def test_lists_files(self, mock_client):
        mock_client.list_repo_files.return_value = [
            {"name": "README.md", "path": "README.md", "type": "file", "size": 500, "sha": "abc"},
            {"name": "src", "path": "src", "type": "dir", "size": 0, "sha": "def"},
        ]

        result = await tools.list_repo_files(mock_client, "openclaw", "openclaw")
        assert len(result) == 2
        assert result[0]["name"] == "README.md"
        assert result[0]["type"] == "file"


class TestGetFileContent:
    @pytest.mark.asyncio
    async def test_returns_content(self, mock_client):
        mock_client.get_file_content.return_value = "# README\nHello world"

        result = await tools.get_file_content(mock_client, "openclaw", "openclaw", "README.md")
        assert result["path"] == "README.md"
        assert "Hello world" in result["content"]


class TestSearchCode:
    @pytest.mark.asyncio
    async def test_search_results(self, mock_client):
        mock_client.search_code.return_value = [
            {
                "path": "src/gateway.ts",
                "repository": {"full_name": "openclaw/openclaw"},
                "html_url": "https://github.com/...",
                "score": 1.0,
            }
        ]

        result = await tools.search_code(mock_client, "gateway", owner="openclaw")
        assert len(result) == 1
        assert result[0]["path"] == "src/gateway.ts"


class TestListIssues:
    @pytest.mark.asyncio
    async def test_filters_out_prs(self, mock_client):
        mock_client.list_issues.return_value = [
            {"number": 1, "title": "Bug", "state": "open", "body": "fix this", "labels": [], "comments": 2, "created_at": "", "updated_at": "", "user": {"login": "dev"}},
            {"number": 2, "title": "PR", "state": "open", "pull_request": {}, "body": "", "labels": [], "comments": 0, "created_at": "", "updated_at": "", "user": {"login": "dev"}},
        ]

        result = await tools.list_issues(mock_client, "openclaw", "openclaw")
        assert len(result) == 1
        assert result[0]["number"] == 1


class TestListPullRequests:
    @pytest.mark.asyncio
    async def test_returns_prs(self, mock_client):
        mock_client.list_pull_requests.return_value = [
            {"number": 10, "title": "Feature", "state": "closed", "body": "Adds X", "merged_at": "2024-01-01", "user": {"login": "dev"}, "created_at": "", "updated_at": ""},
        ]

        result = await tools.list_pull_requests(mock_client, "openclaw", "openclaw")
        assert len(result) == 1
        assert result[0]["merged_at"] == "2024-01-01"


class TestListForks:
    @pytest.mark.asyncio
    async def test_returns_forks(self, mock_client):
        mock_client.list_forks.return_value = [
            {"full_name": "user/fork", "owner": {"login": "user"}, "stargazers_count": 5, "forks_count": 0, "updated_at": "", "html_url": ""},
        ]

        result = await tools.list_forks(mock_client, "openclaw", "openclaw")
        assert len(result) == 1
        assert result[0]["stars"] == 5


class TestGetCommitHistory:
    @pytest.mark.asyncio
    async def test_returns_commits(self, mock_client):
        mock_client.get_commit_history.return_value = [
            {
                "sha": "abcdef1234567890",
                "commit": {"message": "Fix bug", "author": {"name": "dev", "date": "2024-01-01"}},
                "html_url": "",
            }
        ]

        result = await tools.get_commit_history(mock_client, "openclaw", "openclaw")
        assert len(result) == 1
        assert result[0]["sha"] == "abcdef12"
        assert "Fix bug" in result[0]["message"]


class TestGetContributors:
    @pytest.mark.asyncio
    async def test_returns_contributors(self, mock_client):
        mock_client.get_contributors.return_value = [
            {"login": "dev1", "contributions": 100, "avatar_url": "", "html_url": ""},
        ]

        result = await tools.get_contributors(mock_client, "openclaw", "openclaw")
        assert len(result) == 1
        assert result[0]["username"] == "dev1"
        assert result[0]["contributions"] == 100


class TestGitHubClientRateLimit:
    @pytest.mark.asyncio
    async def test_handles_404(self):
        with patch("httpx.AsyncClient.request") as mock_request:
            mock_response = AsyncMock()
            mock_response.status_code = 404
            mock_response.text = "Not Found"
            mock_request.return_value = mock_response

            client = GitHubClient(token="test")
            with pytest.raises(GitHubClientError) as exc_info:
                await client.get("/repos/nonexistent/repo")
            assert exc_info.value.status_code == 404
