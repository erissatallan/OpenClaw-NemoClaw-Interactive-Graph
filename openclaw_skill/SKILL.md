---
name: ClawGraph
description: Query the OpenClaw/NemoClaw knowledge graph, trigger pipeline runs, and view security reports.
---

# ClawGraph Skill

ClawGraph is an AI-powered knowledge graph built from the OpenClaw and NemoClaw open-source ecosystems.
It provides graph-grounded RAG answers about the codebase, architecture, and community.

## Commands

### `/kg query <question>`
Ask a question about OpenClaw or NemoClaw. The answer is grounded in the knowledge graph with source citations.

**Examples:**
- `/kg query What is the Gateway in OpenClaw?`
- `/kg query How does NemoClaw sandbox agent execution?`
- `/kg query What channels does OpenClaw support?`

### `/kg status`
Show knowledge graph statistics: node counts, relationship counts, last crawl time.

### `/kg crawl`
Trigger a manual pipeline run to refresh the knowledge graph from GitHub.

### `/kg security-report`
Show recent prompt injection attempts detected by the security pipeline.

## How It Works
1. A **pipeline** crawls OpenClaw/NemoClaw repos from GitHub
2. **Gemini Flash Lite** extracts entities and relationships into a **knowledge graph**
3. When you ask a question, the **RAG engine** searches the graph + code embeddings
4. **Gemini 2.5 Flash** generates a grounded answer with chain-of-thought reasoning
5. All queries pass through a **5-layer prompt injection defense**

## Setup
The ClawGraph service must be running (default: `http://localhost:8000`).
Set `ClawGraph_URL` in your OpenClaw config to point to the service.

## Environment Variables
- `ClawGraph_URL` — URL of the ClawGraph API (default: `http://localhost:8000`)
