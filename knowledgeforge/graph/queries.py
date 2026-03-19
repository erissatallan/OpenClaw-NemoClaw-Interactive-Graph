"""Cypher query templates for common graph operations (SPEC §2.3)."""

from __future__ import annotations

# ── Node queries ──

FIND_NODE_BY_NAME = """
MATCH (n {qualified_name: $qn})
RETURN n, labels(n) AS labels
"""

FIND_NODES_BY_LABEL = """
MATCH (n:{label})
RETURN n
ORDER BY n.qualified_name
LIMIT $limit
"""

FIND_NODES_MATCHING = """
MATCH (n)
WHERE toLower(n.qualified_name) CONTAINS toLower($pattern)
   OR toLower(n.name) CONTAINS toLower($pattern)
   OR toLower(n.description) CONTAINS toLower($pattern)
RETURN n, labels(n) AS labels
LIMIT $limit
"""

# ── Relationship queries ──

FIND_CALLERS = """
MATCH (caller)-[:CALLS]->(target {qualified_name: $qn})
RETURN caller, labels(caller) AS labels
"""

FIND_CALLEES = """
MATCH (source {qualified_name: $qn})-[:CALLS]->(callee)
RETURN callee, labels(callee) AS labels
"""

FIND_IMPORTERS = """
MATCH (importer)-[:IMPORTS]->(target {qualified_name: $qn})
RETURN importer, labels(importer) AS labels
"""

FIND_SUBCLASSES = """
MATCH (child)-[:EXTENDS]->(parent {qualified_name: $qn})
RETURN child, labels(child) AS labels
"""

# ── Repository queries ──

REPO_MODULES = """
MATCH (r:Repository {qualified_name: $repo})-[:CONTAINS]->(m:Module)
RETURN m
ORDER BY m.path
"""

REPO_CONTRIBUTORS = """
MATCH (c:Contributor)-[:CONTRIBUTES_TO]->(r:Repository {qualified_name: $repo})
RETURN c
ORDER BY c.contributions DESC
"""

# ── Aggregation ──

STALE_NODES = """
MATCH (n {_stale: true})
RETURN n, labels(n) AS labels
LIMIT $limit
"""

GRAPH_STATS = """
MATCH (n)
WITH labels(n)[0] AS label, count(n) AS cnt
RETURN label, cnt
ORDER BY cnt DESC
"""

# ── Code chunks ──

CODE_CHUNKS_FOR_ENTITY = """
MATCH (chunk:CodeChunk)-[:BELONGS_TO]->({qualified_name: $qn})
RETURN chunk
ORDER BY chunk.start_line
"""
