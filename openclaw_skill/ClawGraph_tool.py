"""OpenClaw skill tool — HTTP client for ClawGraph API (SPEC §2.6)."""

from __future__ import annotations

import os

import httpx

DEFAULT_URL = "http://localhost:8000"


class ClawGraphTool:
    """HTTP client that OpenClaw's skill system uses to call the ClawGraph API."""

    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or os.environ.get("ClawGraph_URL", DEFAULT_URL)
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=60.0)

    async def query(self, question: str) -> str:
        """Ask the knowledge graph a question. Returns formatted answer."""
        resp = await self._client.post("/api/query", json={"question": question})
        resp.raise_for_status()
        data = resp.json()

        answer = data.get("answer", "No answer generated.")
        sources = data.get("sources", [])

        # Format response for chat
        result = answer
        if sources:
            result += "\n\n📎 **Sources:**\n"
            for src in sources[:5]:
                path = src.get("path", "")
                start = src.get("start_line", "")
                end = src.get("end_line", "")
                result += f"- `{path}:{start}-{end}`\n"

        return result

    async def status(self) -> str:
        """Get knowledge graph statistics."""
        resp = await self._client.get("/api/graph/stats")
        resp.raise_for_status()
        data = resp.json()

        lines = ["📊 **Knowledge Graph Status**\n"]
        lines.append(f"- **Total nodes:** {data.get('total_nodes', 0)}")
        lines.append(f"- **Total relationships:** {data.get('total_relationships', 0)}")

        node_counts = data.get("node_counts", {})
        if node_counts:
            lines.append("- **By type:**")
            for label, count in sorted(node_counts.items()):
                lines.append(f"  - {label}: {count}")

        last = data.get("last_crawled")
        if last:
            lines.append(f"- **Last crawled:** {last}")

        return "\n".join(lines)

    async def visualize(self) -> str:
        """Generate a PNG visualization of the knowledge graph."""
        import time
        output_path = f"/tmp/clawgraph_snapshot_{int(time.time())}.png"
        
        # We use a streaming request to download the large image file
        async with self._client.stream("GET", "/api/graph/visualize") as resp:
            resp.raise_for_status()
            with open(output_path, "wb") as f:
                async for chunk in resp.aiter_bytes():
                    f.write(chunk)
                    
        return f"🖼️ Snapshot saved to {output_path}"

    async def crawl(self) -> str:
        """Trigger a pipeline run."""
        resp = await self._client.post("/api/pipeline/run")
        resp.raise_for_status()
        data = resp.json()
        return f"🔄 Pipeline {data.get('status', 'unknown')}: {data.get('result', {})}"

    async def security_report(self) -> str:
        """Get recent security events."""
        resp = await self._client.get("/api/security/audit")
        resp.raise_for_status()
        data = resp.json()

        events = data.get("events", [])
        if not events:
            return "🛡️ No security events recorded."

        lines = ["🛡️ **Recent Security Events**\n"]
        for event in events[:10]:
            ts = event.get("timestamp", "")
            cls = event.get("classification", "")
            conf = event.get("confidence", 0)
            reason = event.get("reason", "")
            icon = {"benign": "✅", "suspicious": "⚠️", "malicious": "🚫"}.get(cls, "❓")
            lines.append(f"- {icon} [{ts}] **{cls}** (conf: {conf:.1%}) — {reason}")

        return "\n".join(lines)

    async def close(self):
        await self._client.aclose()
