"""Evidence labels carried on policy parameters and results.

Fixture values are illustrative. A label does not become an observation
because a mechanism ran.
"""

from __future__ import annotations

EVIDENCE_STATES = ("observed", "announced", "estimated", "illustrative")


def require_evidence(state: str) -> str:
    if state not in EVIDENCE_STATES:
        raise ValueError(f"unknown evidence state: {state}")
    return state
