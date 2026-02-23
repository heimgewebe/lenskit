import re
from typing import Tuple

class Redactor:
    """
    Heuristic-based secret redaction.
    """
    # Simple regex patterns for common secrets
    PATTERNS = [
        (r"(?i)(api[_-]?key|access[_-]?token|secret[_-]?key)[\s:=]+([\"']?)([\w-]{20,})", r"\1\2[REDACTED]"),
        (r"(?i)(password|passwd|pwd)[\s:=]+([\"']?)([\w-]{6,})", r"\1\2[REDACTED]"),
        # AWS Key ID (AKIA...)
        (r"(AKIA[0-9A-Z]{16})", "[AWS_KEY_REDACTED]"),
        # Private Key block (multiline match)
        (r"-----BEGIN PRIVATE KEY-----[\s\S]*?-----END PRIVATE KEY-----", "[PRIVATE_KEY_BLOCK_REDACTED]"),
    ]

    def redact(self, content: str) -> Tuple[str, bool]:
        """
        Redacts secrets from content.
        Returns (redacted_content, was_modified).
        """
        modified = False
        redacted = content

        for pattern, replacement in self.PATTERNS:
            new_content = re.sub(pattern, replacement, redacted)
            if new_content != redacted:
                modified = True
                redacted = new_content

        return redacted, modified
