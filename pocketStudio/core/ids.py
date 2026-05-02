from __future__ import annotations

import secrets
import string


DEFAULT_ALPHABET = string.ascii_letters + string.digits + "_-"


def nanoid(size: int = 21, alphabet: str = DEFAULT_ALPHABET) -> str:
    if size <= 0:
        raise ValueError("size must be greater than zero")
    if not alphabet:
        raise ValueError("alphabet must not be empty")
    return "".join(secrets.choice(alphabet) for _ in range(size))


def prefixed_id(prefix: str, size: int = 12) -> str:
    normalized = "".join(ch.lower() if ch.isalnum() else "-" for ch in prefix).strip("-")
    return f"{normalized or 'id'}-{nanoid(size)}"
