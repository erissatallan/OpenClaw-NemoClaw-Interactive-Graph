"""Unified defense pipeline — composes L1-L5 security layers (SPEC §2.5)."""

from __future__ import annotations

import logging
import json
from typing import Any

from knowledgeforge.config import Settings
from knowledgeforge.models import SecurityVerdict
from knowledgeforge.security.audit import AuditLogger
from knowledgeforge.security.canary import CanaryTokenSystem
from knowledgeforge.security.classifier import InjectionClassifier
from knowledgeforge.security.guardrails import check_output as check_output_guardrails
from knowledgeforge.security.sanitizer import sanitize_input

logger = logging.getLogger(__name__)


class DefensePipeline:
    """Unified 5-layer prompt injection defense pipeline.

    L1: Input Sanitizer (rule-based)
    L2: Injection Classifier (Gemini Flash Lite)
    L3: Canary Tokens (UUID-based leak detection)
    L4: Output Guardrails (pattern matching)
    L5: Audit Logger (JSON-lines)
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.classifier = InjectionClassifier(settings=settings)
        self.canary = CanaryTokenSystem(secret=settings.canary_secret)
        self.audit = AuditLogger()

    async def check_input(self, text: str) -> SecurityVerdict:
        """Run L1 (sanitizer) and L2 (classifier) on user input.

        Returns a SecurityVerdict with the classification result.
        """
        verdict = SecurityVerdict(input_text=text)

        # L2: Classify BEFORE sanitization so the classifier sees injection patterns
        classification, confidence, reason = await self.classifier.classify(text)
        verdict.classification = classification
        verdict.classifier_confidence = confidence
        verdict.reason = reason

        if classification != "benign":
            logger.warning(
                "l2_classifier_alert: %s (conf=%.2f) — %s",
                classification, confidence, reason,
            )

        # L1: Sanitize (always, even if already classified)
        sanitized, findings = sanitize_input(text)
        verdict.sanitized_text = sanitized

        if findings:
            logger.info("l1_sanitizer_findings: %s", json.dumps(findings))

        # L5: Audit
        self.audit.log_verdict(verdict)

        return verdict

    async def check_output(self, output: str) -> SecurityVerdict:
        """Run L3 (canary) and L4 (guardrails) on model output.

        Returns a SecurityVerdict — if output_blocked is True, the output should not be sent.
        """
        verdict = SecurityVerdict(input_text="[output check]", sanitized_text=output)

        # L3: Check canary tokens
        leaked, leak_details = self.canary.check_output(output)
        verdict.canary_triggered = leaked
        if leaked:
            verdict.output_blocked = True
            verdict.classification = "malicious"
            verdict.reason = f"Canary leak: {leak_details}"
            logger.warning("l3_canary_triggered: %s", leak_details)

        # L4: Output guardrails
        should_block, block_reason = check_output_guardrails(output)
        if should_block:
            verdict.output_blocked = True
            if not verdict.reason:
                verdict.classification = "malicious"
                verdict.reason = f"Output guardrail: {block_reason}"
            logger.warning("l4_guardrail_triggered: %s", block_reason)

        # L5: Audit (only if something was flagged)
        if verdict.output_blocked or verdict.canary_triggered:
            self.audit.log_verdict(verdict)

        return verdict

    def get_system_prompt_with_canary(self, base_prompt: str) -> str:
        """Inject canary token into a system prompt."""
        return base_prompt + self.canary.canary_instruction

    def get_recent_events(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent security events for the audit API."""
        return self.audit.get_recent_events(limit=limit)
