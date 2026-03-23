#!/usr/bin/env python3
"""Generate a stunning knowledge graph PNG from ClawGraph's export API."""

import json
import math
import subprocess
import sys

# Fetch data from local API
import urllib.request

API_URL = "http://localhost:8000/api/graph/export"
OUTPUT_PATH = "/root/clawgraph_snapshot.png"

print("📡 Fetching graph data from ClawGraph API...")
try:
    with urllib.request.urlopen(API_URL, timeout=15) as resp:
        data = json.loads(resp.read().decode())
except Exception as e:
    print(f"❌ Failed to fetch graph data: {e}")
    print("   Make sure ClawGraph is running: docker compose up -d")
    sys.exit(1)

nodes = data.get("nodes", [])
edges = data.get("edges", [])
print(f"   Found {len(nodes)} nodes, {len(edges)} edges")

if not nodes:
    print("⚠️  Graph is empty — run a crawl first: curl -X POST http://localhost:8000/api/pipeline/run")
    sys.exit(1)

# Install matplotlib if missing
try:
    import matplotlib
except ImportError:
    print("📦 Installing matplotlib...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "matplotlib", "-q"])

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import to_rgba
import random

# ─── Color scheme ───
COLORS = {
    'Repository': '#00d4ff',
    'Module':     '#a855f7',
    'Class':      '#22c55e',
    'Function':   '#f97316',
    'Concept':    '#ec4899',
    'CodeChunk':  '#3b82f6',
    'Unknown':    '#6b7280',
}

SIZES = {
    'Repository': 500,
    'Module':     200,
    'Class':      180,
    'Function':   100,
    'Concept':    140,
    'CodeChunk':  40,
    'Unknown':    60,
}

EDGE_COLORS = {
    'CONTAINS':   '#4a5568',
    'IMPORTS':    '#a855f7',
    'EXTENDS':    '#22c55e',
    'CALLS':      '#f97316',
    'HAS_METHOD': '#ec4899',
    'DEFINES':    '#3b82f6',
    'IMPLEMENTS': '#eab308',
    'RELATED':    '#374151',
}

# ─── Filter out CodeChunks (too many, clutters viz) ───
filtered_nodes = [n for n in nodes if n.get("label") != "CodeChunk"]
filtered_ids = {n["id"] for n in filtered_nodes}
filtered_edges = [e for e in edges if e["from"] in filtered_ids and e["to"] in filtered_ids]

print(f"   Rendering {len(filtered_nodes)} nodes, {len(filtered_edges)} edges (CodeChunks filtered)")

# ─── Layout: force-directed simulation ───
random.seed(42)
pos = {}
for n in filtered_nodes:
    pos[n["id"]] = [random.uniform(-10, 10), random.uniform(-10, 10)]

# Simple spring layout simulation
node_ids = list(pos.keys())
id_to_idx = {nid: i for i, nid in enumerate(node_ids)}

for iteration in range(300):
    forces = {nid: [0.0, 0.0] for nid in node_ids}

    # Repulsion (all pairs, sampled for perf)
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
    for e in filtered_edges:
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
    cooling = 1.0 - (iteration / 300) * 0.8
    for nid in node_ids:
        pos[nid][0] += forces[nid][0] * 0.5 * cooling
        pos[nid][1] += forces[nid][1] * 0.5 * cooling

# ─── Render ───
print("🎨 Rendering graph...")

fig, ax = plt.subplots(figsize=(24, 16), dpi=150)
fig.patch.set_facecolor('#0a0a0f')
ax.set_facecolor('#0a0a0f')

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

    # Glow effect (larger translucent circle behind)
    glow_color = to_rgba(color, 0.15)
    ax.scatter(x, y, s=size * 3, color=glow_color, edgecolors='none', zorder=2)

    # Main node
    ax.scatter(x, y, s=size, color=color, edgecolors='white', linewidths=0.3, zorder=3, alpha=0.9)

    # Label (only for larger nodes)
    if label_type in ('Repository', 'Module', 'Class'):
        short_name = (n.get("name") or nid).split(".")[-1].split(":")[-1]
        if len(short_name) > 20:
            short_name = short_name[:18] + "…"
        ax.text(
            x, y - 0.6, short_name,
            color='#c8c8d8', fontsize=5, ha='center', va='top',
            fontfamily='sans-serif', fontweight='light', zorder=4,
        )

# Legend
legend_items = []
for label, color in COLORS.items():
    if label == 'CodeChunk':
        continue
    count = sum(1 for n in filtered_nodes if n.get("label") == label)
    if count > 0:
        legend_items.append(
            mpatches.Patch(facecolor=color, edgecolor='white', linewidth=0.5,
                           label=f'{label} ({count})')
        )

legend = ax.legend(
    handles=legend_items, loc='lower left', fontsize=8,
    facecolor='#12121a', edgecolor='#333355', labelcolor='#c8c8d8',
    framealpha=0.9, borderpad=1.0, handlelength=1.5,
)

# Title
ax.text(
    0.5, 0.97, 'ClawGraph — Knowledge Graph',
    transform=ax.transAxes, ha='center', va='top',
    fontsize=20, color='#e8e8f0', fontfamily='sans-serif', fontweight='bold',
)
ax.text(
    0.5, 0.94, 'OpenClaw & NemoClaw Interactive Repository Graph',
    transform=ax.transAxes, ha='center', va='top',
    fontsize=11, color='#8888aa', fontfamily='sans-serif',
)

# Stats text
stats_text = f"{len(filtered_nodes)} entities  •  {len(filtered_edges)} relationships  •  {sum(1 for n in filtered_nodes if n.get('label') == 'Repository')} repos"
ax.text(
    0.5, 0.91, stats_text,
    transform=ax.transAxes, ha='center', va='top',
    fontsize=9, color='#555577', fontfamily='sans-serif',
)

ax.set_xlim(min(p[0] for p in pos.values()) - 2, max(p[0] for p in pos.values()) + 2)
ax.set_ylim(min(p[1] for p in pos.values()) - 2, max(p[1] for p in pos.values()) + 2)
ax.axis('off')

plt.tight_layout(pad=1.0)
plt.savefig(OUTPUT_PATH, dpi=150, facecolor='#0a0a0f', edgecolor='none', bbox_inches='tight')
plt.close()

print(f"✅ Snapshot saved to {OUTPUT_PATH}")
print(f"   Download with: scp root@77.68.100.188:{OUTPUT_PATH} ./clawgraph_snapshot.png")
