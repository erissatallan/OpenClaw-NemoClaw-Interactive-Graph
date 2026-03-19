#!/bin/bash
# ClawGraph CLI — called by the OpenClaw agent to interact with the ClawGraph API.
# Usage:
#   kg.sh query "What is the Gateway in OpenClaw?"
#   kg.sh status
#   kg.sh crawl
#   kg.sh security-report

CLAWGRAPH_URL="${CLAWGRAPH_URL:-http://localhost:8000}"

case "$1" in
  query)
    shift
    QUESTION="$*"
    curl -s -X POST "$CLAWGRAPH_URL/api/query" \
      -H "Content-Type: application/json" \
      -d "{\"question\": \"$QUESTION\"}"
    ;;
  status)
    curl -s "$CLAWGRAPH_URL/api/graph/stats"
    ;;
  crawl)
    curl -s -X POST "$CLAWGRAPH_URL/api/pipeline/run"
    ;;
  security-report)
    curl -s "$CLAWGRAPH_URL/api/security/audit"
    ;;
  health)
    curl -s "$CLAWGRAPH_URL/api/health"
    ;;
  *)
    echo "Usage: kg.sh {query|status|crawl|security-report|health} [args...]"
    exit 1
    ;;
esac
