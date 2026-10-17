"""Deterministic economic hash.

The hash is SHA-256 of canonical JSON. Keys are sorted, separators have no
whitespace, and only strings, integers, nulls, and lists are allowed. Object
key order and process hash randomization cannot change the digest.

The hashed document is logistics economic state: orders, queues, carriers,
outstanding actions, postings, and committed events. Camera notes and the
``cosmetic_note`` field are not part of the document.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(value: Any) -> str:
    normalized = _normalize(value)
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def economic_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _normalize(value: Any) -> Any:
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, bool):
        raise TypeError("economic state cannot contain bool")
    if isinstance(value, int):
        return value
    if isinstance(value, dict):
        return {str(key): _normalize(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    raise TypeError(f"economic state cannot contain {type(value).__name__}")
