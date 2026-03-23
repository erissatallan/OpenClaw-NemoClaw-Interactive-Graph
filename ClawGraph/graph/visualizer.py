"""Graph visualization — generates a force-directed PNG from knowledge graph data."""

from __future__ import annotations

import math
import random
import tempfile
from pathlib import Path


# ─── Color scheme ───
COLORS = {
    "Repository": "#00d4ff",
    "Module": "#a855f7",
    "Class": "#22c55e",
    "Function": "#f97316",
    "Concept": "#ec4899",
    "CodeChunk": "#3b82f6",
    "Unknown": "#6b7280",
}

SIZES = {
    "Repository": 500,
    "Module": 200,
    "Class": 180,
    "Function": 100,
    "Concept": 140,
    "CodeChunk": 40,
    "Unknown": 60,
}

EDGE_COLORS = {
    "CONTAINS": "#4a5568",
    "IMPORTS": "#a855f7",
    "EXTENDS": "#22c55e",
    "CALLS": "#f97316",
    "HAS_METHOD": "#ec4899",
    "DEFINES": "#3b82f6",
    "IMPLEMENTS": "#eab308",
    "RELATED": "#374151",
}


def _force_directed_layout(
    nodes: list[dict],
    edges: list[dict],
    iterations: int = 300,
    seed: int = 42,
) -> dict[str, list[float]]:
    """Compute a 2D force-directed layout and return {node_id: [x, y]}."""
    random.seed(seed)
    pos: dict[str, list[float]] = {}
    for n in nodes:
        pos[n["id"]] = [random.uniform(-10, 10), random.uniform(-10, 10)]

    node_ids = list(pos.keys())

    for iteration in range(iterations):
        forces: dict[str, list[float]] = {nid: [0.0, 0.0] for nid in node_ids}

        # Repulsion between all node pairs
        for i, a in enumerate(node_ids):
            for j in range(i + 1, len(node_ids)):
                b = node_ids[j]
                dx = pos[a][0] - pos[b][0]
                dy = pos[a][1] - pos[b][1]
                dist = max(math.sqrt(dx * dx + dy * dy), 0.1)
                repulsion = 8.0 / (dist * dist)
                fx = dx / dist * repulsion
                fy = dy / dist * repulsion
                forces[a][0] += fx
                forces[a][1] += fy
                forces[b][0] -= fx
                forces[b][1] -= fy

        # Attraction along edges
        for e in edges:
            a, b = e["from"], e["to"]
            if a not in pos or b not in pos:
                continue
            dx = pos[b][0] - pos[a][0]
            dy = pos[b][1] - pos[a][1]
            dist = max(math.sqrt(dx * dx + dy * dy), 0.1)
            attraction = dist * 0.01
            fx = dx / dist * attraction
            fy = dy / dist * attraction
            forces[a][0] += fx
            forces[a][1] += fy
            forces[b][0] -= fx
            forces[b][1] -= fy

        # Center gravity
        for nid in node_ids:
            forces[nid][0] -= pos[nid][0] * 0.002
            forces[nid][1] -= pos[nid][1] * 0.002

        # Apply forces with cooling
        cooling = 1.0 - (iteration / iterations) * 0.8
        for nid in node_ids:
            pos[nid][0] += forces[nid][0] * 0.5 * cooling
            pos[nid][1] += forces[nid][1] * 0.5 * cooling

    return pos


def generate_graph_image(
    nodes: list[dict],
    edges: list[dict],
    output_path: str | None = None,
) -> str:
    """Render a knowledge graph PNG and return the output file path.

    Args:
        nodes: List of node dicts with keys ``id``, ``label``, ``name``.
        edges: List of edge dicts with keys ``from``, ``to``, ``rel_type``.
        output_path: Where to save the PNG. Defaults to a temporary file.

    Returns:
        Absolute path to the generated PNG file.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: E402
    import matplotlib.patches as mpatches  # noqa: E402
    from matplotlib.colors import to_rgba  # noqa: E402

    if output_path is None:
        fd, output_path = tempfile.mkstemp(suffix=".png", prefix="clawgraph_")
        import os
        os.close(fd)

    # Filter out CodeChunks (too many, clutters viz)
    filtered_nodes = [n for n in nodes if n.get("label") != "CodeChunk"]
    filtered_ids = {n["id"] for n in filtered_nodes}
    filtered_edges = [
        e for e in edges if e["from"] in filtered_ids and e["to"] in filtered_ids
    ]

    if not filtered_nodes:
        # Produce an empty-state image
        fig, ax = plt.subplots(figsize=(12, 8), dpi=150)
        fig.patch.set_facecolor("#0a0a0f")
        ax.set_facecolor("#0a0a0f")
        ax.text(
            0.5, 0.5, "No entities to visualize.\nRun a crawl first.",
            transform=ax.transAxes, ha="center", va="center",
            fontsize=18, color="#8888aa", fontfamily="sans-serif",
        )
        ax.axis("off")
        plt.savefig(output_path, dpi=150, facecolor="#0a0a0f", bbox_inches="tight")
        plt.close()
        return str(Path(output_path).resolve())

    # Layout
    pos = _force_directed_layout(filtered_nodes, filtered_edges)

    # Render
    fig, ax = plt.subplots(figsize=(24, 16), dpi=150)
    fig.patch.set_facecolor("#0a0a0f")
    ax.set_facecolor("#0a0a0f")

    # Draw edges
    for e in filtered_edges:
        a, b = e["from"], e["to"]
        if a not in pos or b not in pos:
            continue
        color = EDGE_COLORS.get(e.get("rel_type", "RELATED"), "#374151")
        ax.plot(
            [pos[a][0], pos[b][0]], [pos[a][1], pos[b][1]],
            color=color, alpha=0.25, linewidth=0.6, zorder=1,
        )

    # Draw nodes
    for n in filtered_nodes:
        nid = n["id"]
        if nid not in pos:
            continue
        label_type = n.get("label", "Unknown")
        color = COLORS.get(label_type, COLORS["Unknown"])
        size = SIZES.get(label_type, 60)
        x, y = pos[nid]

        # Glow effect
        glow_color = to_rgba(color, 0.15)
        ax.scatter(x, y, s=size * 3, color=glow_color, edgecolors="none", zorder=2)
        # Main node
        ax.scatter(x, y, s=size, color=color, edgecolors="white", linewidths=0.3, zorder=3, alpha=0.9)

        # Label for larger nodes
        if label_type in ("Repository", "Module", "Class"):
            short_name = (n.get("name") or nid).split(".")[-1].split(":")[-1]
            if len(short_name) > 20:
                short_name = short_name[:18] + "…"
            ax.text(
                x, y - 0.6, short_name,
                color="#c8c8d8", fontsize=5, ha="center", va="top",
                fontfamily="sans-serif", fontweight="light", zorder=4,
            )

    # Legend
    legend_items = []
    for label, color in COLORS.items():
        if label == "CodeChunk":
            continue
        count = sum(1 for n in filtered_nodes if n.get("label") == label)
        if count > 0:
            legend_items.append(
                mpatches.Patch(
                    facecolor=color, edgecolor="white", linewidth=0.5,
                    label=f"{label} ({count})",
                )
            )

    ax.legend(
        handles=legend_items, loc="lower left", fontsize=8,
        facecolor="#12121a", edgecolor="#333355", labelcolor="#c8c8d8",
        framealpha=0.9, borderpad=1.0, handlelength=1.5,
    )

    # Title
    ax.text(
        0.5, 0.97, "ClawGraph — Knowledge Graph",
        transform=ax.transAxes, ha="center", va="top",
        fontsize=20, color="#e8e8f0", fontfamily="sans-serif", fontweight="bold",
    )
    ax.text(
        0.5, 0.94, "OpenClaw & NemoClaw Interactive Repository Graph",
        transform=ax.transAxes, ha="center", va="top",
        fontsize=11, color="#8888aa", fontfamily="sans-serif",
    )

    # Stats
    repo_count = sum(1 for n in filtered_nodes if n.get("label") == "Repository")
    stats_text = f"{len(filtered_nodes)} entities  •  {len(filtered_edges)} relationships  •  {repo_count} repos"
    ax.text(
        0.5, 0.91, stats_text,
        transform=ax.transAxes, ha="center", va="top",
        fontsize=9, color="#555577", fontfamily="sans-serif",
    )

    ax.set_xlim(min(p[0] for p in pos.values()) - 2, max(p[0] for p in pos.values()) + 2)
    ax.set_ylim(min(p[1] for p in pos.values()) - 2, max(p[1] for p in pos.values()) + 2)
    ax.axis("off")

    plt.tight_layout(pad=1.0)
    plt.savefig(output_path, dpi=150, facecolor="#0a0a0f", edgecolor="none", bbox_inches="tight")
    plt.close()

    return str(Path(output_path).resolve())
