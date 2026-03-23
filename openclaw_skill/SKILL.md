---
name: ClawGraph
description: Query the OpenClaw/NemoClaw knowledge graph, trigger pipeline runs, and view security reports.
---

# ClawGraph Skill

ClawGraph is an AI-powered knowledge graph built from the OpenClaw and NemoClaw open-source ecosystems.
It provides graph-grounded RAG answers about the codebase, architecture, and community.

## Available Tools

You have access to a shell script at `./scripts/kg.sh` that communicates with the ClawGraph API running at `http://localhost:8000`.

### Querying the Knowledge Graph

When users ask questions about OpenClaw or NemoClaw (code, architecture, features, etc.), run:

```bash
bash ./scripts/kg.sh query "their question here"
```

The response is JSON with an `answer` field and a `sources` array. Format the answer nicely for the user and include source citations.

### Checking Graph Status

To show knowledge graph statistics (total nodes, relationships, last crawl time):

```bash
bash ./scripts/kg.sh status
```

### Visualizing the Knowledge Graph

To generate a graphical PNG layout of all the components and relationships in the knowledge graph:

```bash
bash ./scripts/kg.sh visualize
```
Wait for the command to finish and it will return the file path of the saved PNG snapshot. You can then provide the file path to the user or send the image.

### Triggering a Crawl

To refresh the knowledge graph by crawling the latest code from GitHub:

```bash
bash ./scripts/kg.sh crawl
```

### Security Report

To show recent prompt injection attempts detected by the security pipeline:

```bash
bash ./scripts/kg.sh security-report
```

### Health Check

To verify the ClawGraph service is running:

```bash
bash ./scripts/kg.sh health
```

## When to Use This Skill

- When users ask about OpenClaw or NemoClaw source code, architecture, or features
- When users want to search the codebase
- When users use the `/kg` prefix (e.g., `/kg query ...`, `/kg status`, `/kg crawl`)
- When users ask you to update or refresh the knowledge graph
- When users ask about security events or injection attempts

## Important Notes

- The ClawGraph service must be running at `http://localhost:8000`
- Queries go through a 5-layer prompt injection defense pipeline
- Answers include chain-of-thought reasoning and source code citations
