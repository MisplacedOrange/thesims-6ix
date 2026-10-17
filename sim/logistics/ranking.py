"""Seeded admission order.

Contested logistics capacity is ordered by a hash of the scenario seed, the
decision opportunity, and the actor. The hash does not draw from a kernel
random stream, so a delivery queue cannot shift weather or income draws.
Stable actor-id ordering alone is not the rank: the same household must not
win every opportunity merely because its id sorts first. Ties in the hash
break by actor id, then by order id, both ascending.
"""

from __future__ import annotations

import hashlib

from sim.logistics.units import require_int, require_nonnegative


def admission_rank(seed: int, opportunity: str, actor_id: str) -> int:
    """Return a nonnegative rank. Smaller ranks are admitted first."""

    require_int("seed", seed)
    if not opportunity or not actor_id:
        raise ValueError("admission rank requires an opportunity and an actor")
    material = f"sim6ix-logistics-admission-v1|{seed}|{opportunity}|{actor_id}"
    digest = hashlib.sha256(material.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def require_seed(seed: int) -> int:
    return require_nonnegative("seed", seed)
