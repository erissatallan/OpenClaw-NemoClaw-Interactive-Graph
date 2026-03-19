"""L5: Audit Logger — JSON-lines security event log (SPEC §2.5 L5)."""

from __future__ import annotations

import json
import logging
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from knowledgeforge.models import SecurityVerdict

logger = logging.getLogger(__name__)

LOG_DIR = Path("logs")
AUDIT_FILE = LOG_DIR / "security_audit.jsonl"
MAX_MEMORY_EVENTS = 1000


class AuditLogger:
    """Logs security events to JSON-lines file and keeps recent events in memory."""

    def __init__(self, log_path: Path | None = None):
        self._log_path = log_path or AUDIT_FILE
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        self._recent_events: deque[dict[str, Any]] = deque(maxlen=MAX_MEMORY_EVENTS)

    def log_verdict(self, verdict: SecurityVerdict) -> None:
        """Log a security verdict to file and memory."""
        event = {
            "timestamp": verdict.timestamp.isoformat(),
            "input": verdict.input_text[:500],
            "sanitized": verdict.sanitized_text[:500],
            "classification": verdict.classification,
            "confidence": verdict.classifier_confidence,
            "canary_triggered": verdict.canary_triggered,
            "output_blocked": verdict.output_blocked,
            "reason": verdict.reason,
        }

        self._recent_events.appendleft(event)

        try:
            with open(self._log_path, "a") as f:
                f.write(json.dumps(event, default=str) + "\n")
        except Exception as exc:
            logger.warning("audit_log_write_failed", error=str(exc))

    def get_recent_events(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return recent security events from memory."""
        return list(self._recent_events)[:limit]

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate security statistics."""
        events = list(self._recent_events)
        total = len(events)
        if total == 0:
            return {"total_events": 0}

        classifications = {}
        canary_triggers = 0
        blocks = 0

        for event in events:
            cls = event.get("classification", "unknown")
            classifications[cls] = classifications.get(cls, 0) + 1
            if event.get("canary_triggered"):
                canary_triggers += 1
            if event.get("output_blocked"):
                blocks += 1

        return {
            "total_events": total,
            "classifications": classifications,
            "canary_triggers": canary_triggers,
            "output_blocks": blocks,
        }
