import re
from typing import Dict, Any, List


class KnowledgeSecurityFilter:
    """Sanitizes technical documents and enforces deterministic security boundaries against prompt injection."""

    PROMPT_INJECTION_PATTERNS = [
        r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions",
        r"disregard\s+(?:all\s+)?rules",
        r"you\s+are\s+now\s+(?:dan|developer\s+mode|unrestricted)",
        r"system\s*:\s*override",
        r"bypass\s+safety\s+checks",
        r"drop\s+database",
        r"delete\s+from\s+",
        r"cmd\.exe",
        r"/bin/sh",
    ]

    @classmethod
    def sanitize_passage(cls, text: str) -> str:
        """Sanitizes text passage to prevent prompt injection or delimiter breakout."""
        sanitized = text
        for pattern in cls.PROMPT_INJECTION_PATTERNS:
            sanitized = re.sub(pattern, "[FILTERED_SUSPICIOUS_CONTENT]", sanitized, flags=re.IGNORECASE)

        # Escape Markdown control delimiters that could break parsing
        sanitized = sanitized.replace("```json", "'''json").replace("```", "'''")
        return sanitized.strip()

    @classmethod
    def sanitize_text(cls, text: str):
        sanitized = cls.sanitize_passage(text)
        is_safe = bool(sanitized == text.strip())
        return is_safe, sanitized

    @classmethod
    def validate_tenant_access(
        cls,
        organization_id: str,
        document_organization_id: str,
        is_standard: bool = False,
    ) -> bool:
        """Strict tenant isolation check before returning knowledge passages."""
        if is_standard:
            return True  # Standard pharmaceutical knowledge is shared across approved tenants
        return organization_id == document_organization_id
