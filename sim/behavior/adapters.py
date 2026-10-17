"""Thin interfaces for the kernel and for Person 2's gateway.

The behaviour package calls these protocols. It does not import a provider SDK,
a database, or ``sim.core``.
"""

from __future__ import annotations

from typing import Protocol

from sim.behavior.draft import GatewayRequest, GatewayResponse


class ChoiceGateway(Protocol):
    """Start every request in one barrier together. Do not retry."""

    def dispatch_barrier(
        self,
        requests: tuple[GatewayRequest, ...],
        *,
        deadline_seconds: float,
    ) -> tuple[GatewayResponse, ...]:
        """Return one response per dispatched decision. Extra ids are ignored."""


class DisabledGateway:
    """Gateway stand-in for rule-only runs.

    The coordinator must not call ``dispatch_barrier`` while the gateway is
    disabled. A call raises so tests can see a leak.
    """

    enabled = False

    def dispatch_barrier(
        self,
        requests: tuple[GatewayRequest, ...],
        *,
        deadline_seconds: float,
    ) -> tuple[GatewayResponse, ...]:
        raise RuntimeError("LLM gateway is disabled; the coordinator must not dispatch")
