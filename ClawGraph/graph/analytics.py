"""Advanced graph analytics capabilities."""

from __future__ import annotations

import datetime

from ClawGraph.config import Settings
from ClawGraph.graph.base import GraphClient


async def generate_daily_summary(graph: GraphClient, settings: Settings) -> str:
    """Generate an LLM-synthesized daily ecosystem digest."""
    import google.genai as genai
    from pydantic import SecretStr

    client = genai.Client(api_key=settings.gemini_api_key.get_secret_value() if isinstance(settings.gemini_api_key, SecretStr) else settings.gemini_api_key)

    # Calculate cutoff time (24 hours ago)
    now = datetime.datetime.now(datetime.timezone.utc)
    cutoff = now - datetime.timedelta(hours=24)
    # Convert to ISO format for basic string comparison if using MemoryClient
    cutoff_str = cutoff.isoformat()

    # Query for new and updated nodes (rough heuristic for the memory client since we don't track creation time separately)
    # We will just fetch all nodes and do a soft filter or pass a slice to the LLM
    stats = await graph.get_stats()
    
    # For actual memory client, it stores "_updated_at", but let's just do a blanket fetch
    # and let the LLM curate it based on the timestamp or just summarize the current state
    if hasattr(graph, '_graph'):
        G = graph._graph
        recent_modules = []
        recent_pr_issues = []
        for node_id, data in G.nodes(data=True):
            label = data.get("_label", "")
            if label in ("Module", "Class", "Function"):
                recent_modules.append(data.get("name", node_id))
            elif label in ("Issue", "PullRequest"):
                recent_pr_issues.append(data.get("title", node_id))
        
        # Take a sample to avoid context overflow
        modules_text = ", ".join(recent_modules[:50])
        issues_text = ", ".join(recent_pr_issues[:50])
    else:
        # Cypher approach for Neo4j (mocked fallback)
        modules_text = "See Neo4j DB"
        issues_text = "See Neo4j DB"

    prompt = f"""
    You are an expert developer relations engineer compiling a daily newsletter for the OpenClaw and NemoClaw ecosystems.
    
    Total Graph Size: {stats.total_nodes} nodes, {stats.total_relationships} relationships
    Last Crawled: {stats.last_crawled}

    Recent Modules/Classes/Functions:
    {modules_text}

    Recent PRs/Issues:
    {issues_text}

    Generate a concisely formatted Markdown newsletter summarizing the ecosystem state. Categories should include:
    - 📈 Top-Level Stats
    - 🆕 Project Updates & Commits
    - 💬 Issues & Discussions
    
    Be creative but professional. If data is sparse, write a brief encouraging summary about the graph state.
    Keep the output under 400 words.
    """

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    return response.text or "Error generating summary."
