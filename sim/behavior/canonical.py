"""Stable JSON for observation hashes."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from sim.behavior.errors import BehaviorError


def canon_float(value: float) -> str:
    if type(value) is bool or not isinstance(value, (int, float)):
        raise BehaviorError("expected a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise BehaviorError("non-finite number")
    return format(number, ".12g")


def observation_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
