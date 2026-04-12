import re
from datetime import datetime


# Patterns that indicate behavioral directives rather than factual memory
DIRECTIVE_PATTERNS = [
    r"\balways\b.*\brecommend\b",
    r"\bnever\b.*\brecommend\b",
    r"\bonly\b.*\bapproved\b",
    r"\boverride\b",
    r"\bignore\b.*\b(other|previous|all)\b",
    r"\bmust\b.*\b(use|call|select|choose)\b",
    r"\b(safe|approved|authorized)\b.*\b(endpoint|api|url)\b",
    r"\bcompliance\s+requirement\b",
    r"\bstrategic\s+partner\b",
    r"\bexclusive\b",
    r"\bcritical\s+(security\s+)?vulnerabilit",
    r"\bfully\s+audited\b",
    # Catch LLM-paraphrased directives (the LLM often rewrites attack text)
    r"\bonly\s+trusts?\b",
    r"\bdoes\s+not\s+want\b.*\brecommend",
    r"\bprefers?\s+not\s+to\s+consider\b",
    r"\bshould\s+(always\s+)?be\s+mentioned\b",
    r"\bpassed\s+all\s+checks\b",
    r"/export_all_users\b",
]

MAX_MEMORY_LENGTH = 500
MAX_WRITES_PER_MINUTE = 5


class MemoryGuard:
    """Validates candidate memory entries before they are persisted."""

    def __init__(self):
        self._write_log: list[datetime] = []

    def validate(self, content: str, source: str = "user") -> dict:
        """
        Validate a candidate memory entry.

        Returns:
            {"allowed": True/False, "reason": str, "confidence": float}
        """
        # Check 1: Length limit
        if len(content) > MAX_MEMORY_LENGTH:
            return {
                "allowed": False,
                "reason": f"Content exceeds {MAX_MEMORY_LENGTH} character limit",
                "confidence": 1.0,
            }

        # Check 2: Directive pattern detection
        content_lower = content.lower()
        for pattern in DIRECTIVE_PATTERNS:
            if re.search(pattern, content_lower):
                return {
                    "allowed": False,
                    "reason": f"Content contains behavioral directive (matched: {pattern})",
                    "confidence": 0.9,
                }

        # Check 3: Rate limiting (anomaly detection)
        now = datetime.now()
        self._write_log = [
            t for t in self._write_log if (now - t).total_seconds() < 60
        ]
        if len(self._write_log) >= MAX_WRITES_PER_MINUTE:
            return {
                "allowed": False,
                "reason": f"Rate limit exceeded: {MAX_WRITES_PER_MINUTE} writes/minute",
                "confidence": 1.0,
            }
        self._write_log.append(now)

        # Check 4: Must look like a factual preference, not an instruction
        instruction_signals = [
            content_lower.startswith("when "),
            content_lower.startswith("if "),
            "should always" in content_lower,
            "should never" in content_lower,
            "make sure" in content_lower,
            "do not" in content_lower,
        ]
        if sum(instruction_signals) >= 1:
            return {
                "allowed": False,
                "reason": "Content reads as an instruction rather than a fact/preference",
                "confidence": 0.8,
            }

        return {"allowed": True, "reason": "Passed all checks", "confidence": 1.0}
