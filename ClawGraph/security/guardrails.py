"""L4: Output Guardrails — verify outputs don't contain unauthorized content (SPEC §2.5 L4)."""

from __future__ import annotations

import re


# Patterns that should never appear in outputs
OUTPUT_BLOCKLIST = [
    # System prompt fragments
    r"(?i)system\s+prompt\s*:",
    r"(?i)my\s+instructions\s+are",
    r"(?i)I\s+was\s+told\s+to",
    r"(?i)my\s+system\s+message",
    r"(?i)here\s+(is|are)\s+my\s+instructions",
    r"(?i)I\s+am\s+programmed\s+to",
    # Code execution / file system indicators
    r"(?i)os\.system\s*\(",
    r"(?i)subprocess\.(?:run|call|Popen)\s*\(",
    r"(?i)eval\s*\(\s*input",
    r"(?i)exec\s*\(\s*input",
    r"(?i)__import__\s*\(",
    # Credential patterns  
    r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*['\"][^'\"]{8,}['\"]",
]

_compiled_output_patterns = [re.compile(p) for p in OUTPUT_BLOCKLIST]


def check_output(output: str) -> tuple[bool, str]:
    """Check if the model output contains blocked patterns.

    Returns (should_block: bool, reason: str).
    """
    for pattern in _compiled_output_patterns:
        match = pattern.search(output)
        if match:
            return True, f"Blocked pattern found: {match.group(0)[:50]}"

    # Check for suspiciously long base64 strings (data exfiltration)
    base64_pattern = re.compile(r"[A-Za-z0-9+/]{100,}={0,2}")
    if base64_pattern.search(output):
        return True, "Suspicious base64 blob in output"

    return False, ""
