# 🔥 ClawGraph: OpenClaw & NemoClaw Interactive Graph

**AI-powered knowledge graph builder and RAG system for the OpenClaw/NemoClaw ecosystem**

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

ClawGraph automatically crawls open-source repositories, extracts entities and relationships into a knowledge graph, and serves grounded answers via RAG — all secured with a 5-layer prompt injection defense.

## 🎯 Conceptual Components

| Conceptual Component | Implementation |
|---|---|
| **Orchestration Pipeline** | Directed Acyclic Graph-based crawl→extract→embed→graph→curate pipeline with retry and scheduling |
| **Custom MCP Server** | Python MCP server exposing 9 GitHub API tools via the Model Context Protocol |
| **AI Pipeline** | Gemini Flash Lite (extraction/classification) + Gemini 2.5 Flash (reasoning/curation) |
| **Knowledge Graph & RAG** | Neo4j/NetworkX graph + embedding search → graph-grounded answer generation with Chain of Thought reasoning |
| **Prompt Injection Prevention** | 5-layer defense: sanitizer → classifier → canary tokens → output guardrails → audit |

## 🏗️ Architecture

```
GitHub Repos ──▶ [GitHub MCP Server] ──▶ [Orchestration Pipeline] ──▶ [Knowledge Graph]
                  (9 Python tools)        crawl→extract→embed→         (Neo4j / NetworkX)
                                          graph_update→curate                │
                                                                             ▼
Telegram Bot ◀── [OpenClaw Skill] ◀── [RAG Engine] ◀── [Graph + Vector Retrieval]
                                        (Gemini 2.5 Flash + CoT)
                                             │
                                    [5-Layer Security Defense]
                                    L1: Input Sanitizer
                                    L2: Injection Classifier (Flash Lite)
                                    L3: Canary Tokens
                                    L4: Output Guardrails
                                    L5: Audit Logger
```

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- [Gemini API key](https://aistudio.google.com/apikey) (free tier)
- [GitHub PAT](https://github.com/settings/tokens) (no scope needed for public repos)
- Docker (optional, for containerized deployment)

### Install

```bash
git clone https://github.com/YOUR_USERNAME/ClawGraph.git
cd ClawGraph
pip install -e ".[dev]"
cp .env.example .env
# Edit .env with your API keys
```

### Run Tests

```bash
python -m pytest tests/ -v
```

### Start the Server

```bash
python -m ClawGraph.main
# API available at http://localhost:8000
```

### Run the Pipeline

```bash
# Via API
curl -X POST http://localhost:8000/api/pipeline/run

# Query the knowledge graph
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the Gateway in OpenClaw?"}'
```

### Docker Deployment

```bash
docker compose build
docker compose up -d
# Health check: curl http://localhost:8000/api/health
```

## 📁 Project Structure

```
ClawGraph/
├── github_mcp_server/    # Custom Python MCP Server (9 GitHub tools)
├── pipeline/             # Orchestration Pipeline (5 stages + scheduler)
│   └── stages/           # crawl, extract, embed, graph_update, curate
├── graph/                # Knowledge Graph (Neo4j + NetworkX backends)
├── rag/                  # RAG Engine (retriever, generator, embeddings)
├── security/             # 5-Layer Prompt Injection Defense
├── config.py             # 12-factor app configuration
├── models.py             # Pydantic data models
└── main.py               # FastAPI application
openclaw_skill/           # OpenClaw integration (SKILL.md + tool)
tests/                    # 50+ tests including red-team security suite
```

## 🔐 Security Model

All user queries pass through a 5-layer defense pipeline:

1. **L1 — Input Sanitizer**: Strips injection delimiters, Unicode confusables, control characters
2. **L2 — Injection Classifier**: Gemini Flash Lite classifies input as benign/suspicious/malicious
3. **L3 — Canary Tokens**: Hidden UUID tokens in system prompts detect prompt leaks
4. **L4 — Output Guardrails**: Blocks system prompt fragments, credentials, and code execution patterns
5. **L5 — Audit Logger**: JSON-lines log of all security events for monitoring

## 🤖 GitHub MCP Server

Custom Python MCP server with 9 tools:

| Tool | Description |
|---|---|
| `get_repo_info` | Repository metadata (stars, forks, language, topics) |
| `list_repo_files` | File tree with types and sizes |
| `get_file_content` | Raw file content (base64-decoded) |
| `search_code` | Code search across repositories |
| `list_issues` | Issues with labels and comments |
| `list_pull_requests` | PRs with merge status |
| `list_forks` | Forks sorted by stars/activity |
| `get_commit_history` | Recent commits with messages |
| `get_contributors` | Contributors with commit counts |

Run standalone: `python -m ClawGraph.github_mcp_server.server`

## 📊 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/query` | RAG query with prompt injection defense |
| `GET` | `/api/graph/stats` | Knowledge graph statistics |
| `POST` | `/api/pipeline/run` | Trigger manual pipeline run |
| `GET` | `/api/security/audit` | Recent security events |
| `GET` | `/api/health` | Service health check |

## 🧩 OpenClaw Integration

Install as an OpenClaw skill to use via Telegram:

```
/kg query What is the Gateway in OpenClaw?
/kg status
/kg crawl
/kg security-report
```

## ⚙️ Configuration

All configuration via environment variables ([12-factor app](https://12factor.net/)):

| Variable | Required | Default | Description |
|---|---|---|---|
| `GEMINI_API_KEY` | Yes | — | Google AI Studio API key |
| `GITHUB_TOKEN` | Yes | — | GitHub PAT |
| `GRAPH_BACKEND` | No | `memory` | `neo4j` or `memory` |
| `NEO4J_URI` | If neo4j | — | Neo4j Aura connection URI |
| `PIPELINE_SCHEDULE` | No | `0 3 * * *` | Cron schedule for auto-crawl |
| `PIPELINE_TARGETS` | No | `openclaw/openclaw,NVIDIA/NemoClaw` | Repos to crawl |

## 📄 License

MIT
