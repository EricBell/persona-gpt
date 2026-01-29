# Copyright Polymorph Corporation (2026)

"""Email detection and validation for extension requests."""

import re
from typing import Optional

EMAIL_REGEX = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'

def extract_email(text: str) -> Optional[str]:
    """Extract first valid email address from text."""
    matches = re.findall(EMAIL_REGEX, text)
    return matches[0] if matches else None

def is_valid_email(email: str) -> bool:
    """Validate email format."""
    return bool(re.match(EMAIL_REGEX, email))
