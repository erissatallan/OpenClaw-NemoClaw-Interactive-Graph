"""L1: Input Sanitizer — rule-based pattern stripping (SPEC §2.5 L1)."""

from __future__ import annotations

import re
import unicodedata


# Known injection delimiters and markers
INJECTION_PATTERNS = [
    # System/role override markers
    r"<\|system\|>",
    r"<\|user\|>",
    r"<\|assistant\|>",
    r"<\|im_start\|>",
    r"<\|im_end\|>",
    r"\[INST\]",
    r"\[/INST\]",
    r"<<SYS>>",
    r"<</SYS>>",
    r"\[SYSTEM\]",
    r"\[/SYSTEM\]",
    # Common injection prefixes
    r"(?i)ignore\s+(all\s+)?previous\s+instructions",
    r"(?i)forget\s+(all\s+)?previous\s+instructions",
    r"(?i)disregard\s+(all\s+)?previous\s+instructions",
    r"(?i)you\s+are\s+now\s+(a\s+)?DAN",
    r"(?i)new\s+instruction[s]?\s*:",
    r"(?i)system\s+prompt\s*:",
    r"(?i)override\s+mode",
    r"(?i)developer\s+mode\s+(enabled|activated|on)",
    r"(?i)jailbreak",
    # Markdown/format injection
    r"```system",
    r"```instruction",
]

# Unicode confusable characters that might be used to bypass filters
CONFUSABLE_MAP = {
    "\u0410": "A",  # Cyrillic A
    "\u0412": "B",  # Cyrillic V
    "\u0421": "C",  # Cyrillic S
    "\u0415": "E",  # Cyrillic Ye
    "\u041d": "H",  # Cyrillic En
    "\u041a": "K",  # Cyrillic Ka
    "\u041c": "M",  # Cyrillic Em
    "\u041e": "O",  # Cyrillic O
    "\u0420": "P",  # Cyrillic Er
    "\u0422": "T",  # Cyrillic Te
    "\u0425": "X",  # Cyrillic Kha
    "\u0430": "a",  # Cyrillic a
    "\u0435": "e",  # Cyrillic ye
    "\u043e": "o",  # Cyrillic o
    "\u0440": "p",  # Cyrillic er
    "\u0441": "c",  # Cyrillic es
    "\u0443": "y",  # Cyrillic u
    "\u0445": "x",  # Cyrillic kha
    "\u2028": " ",  # Line separator
    "\u2029": " ",  # Paragraph separator
    "\u200b": "",   # Zero-width space
    "\u200c": "",   # Zero-width non-joiner
    "\u200d": "",   # Zero-width joiner
    "\ufeff": "",   # BOM
}

_compiled_patterns = [re.compile(p) for p in INJECTION_PATTERNS]


def sanitize_input(text: str) -> tuple[str, list[str]]:
    """Sanitize user input by stripping known injection patterns.

    Returns (sanitized_text, list_of_findings).
    Findings indicate what was stripped — used for logging/audit.
    """
    findings: list[str] = []
    sanitized = text

    # 1. Normalize Unicode confusables
    original = sanitized
    for confusable, replacement in CONFUSABLE_MAP.items():
        sanitized = sanitized.replace(confusable, replacement)
    if sanitized != original:
        findings.append("unicode_confusables_normalized")

    # 2. Normalize Unicode categories (strip control chars except newline/tab)
    cleaned = []
    for char in sanitized:
        cat = unicodedata.category(char)
        if cat.startswith("C") and char not in ("\n", "\t", "\r"):
            findings.append(f"control_char_stripped:{repr(char)}")
            continue
        cleaned.append(char)
    sanitized = "".join(cleaned)

    # 3. Strip known injection patterns
    for pattern in _compiled_patterns:
        match = pattern.search(sanitized)
        if match:
            findings.append(f"pattern_stripped:{pattern.pattern}")
            sanitized = pattern.sub("", sanitized)

    # 4. Strip excessive whitespace/newlines (potential formatting attacks)
    if sanitized.count("\n") > 20:
        findings.append("excessive_newlines_collapsed")
        lines = sanitized.split("\n")
        sanitized = "\n".join(line for line in lines[:20])

    sanitized = sanitized.strip()

    return sanitized, findings
