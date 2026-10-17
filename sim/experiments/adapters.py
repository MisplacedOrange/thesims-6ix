"""Thin executor interface implemented by ``sim/core``.

One call runs one isolated world. The runner does not share state between
calls and does not import the kernel.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from sim.behavior.determinism import STREAM_ALGORITHM


@dataclass(frozen=True)
class ExternalShock:
    shock_id: str
    purpose: str
    actor: str
    day_index: int
    value: str


@dataclass(frozen=True)
class ReplicationRequest:
    study_id: str
    cell_id: str
    enabled_policies: tuple[str, ...]
    seed: int
    stream_algorithm: str
    shock_digest: str
    shocks: tuple[ExternalShock, ...]
    parameter_overrides: tuple[tuple[str, str], ...]
    sensitivity_family: str | None
    sensitivity_level: str | None
    agent_policy: str
    gateway_enabled: bool
    outcome_names: tuple[str, ...]

    def request_id(self) -> str:
        level = self.sensitivity_level or "main"
        family = self.sensitivity_family or "main"
        return f"{self.study_id}:{family}:{level}:{self.cell_id}:{self.seed}"


@dataclass(frozen=True)
class HouseholdMetric:
    household_id: str
    income_band: str
    household_size: int
    area_id: str
    mobility: str
    school_eligible: bool
    values: tuple[tuple[str, float], ...]


@dataclass(frozen=True)
class ReplicationResult:
    completed: bool
    failure_reason: str | None
    outcomes: tuple[tuple[str, float], ...]
    households: tuple[HouseholdMetric, ...]
    shock_digest: str
    llm_dispatch_count: int
    economic_hash: str | None = None


class RunExecutor(Protocol):
    def execute(self, request: ReplicationRequest) -> ReplicationResult:
        """Run one seed and one policy cell. Echo ``request.shock_digest``."""


def failed_result(reason: str, shock_digest: str) -> ReplicationResult:
    return ReplicationResult(
        completed=False,
        failure_reason=reason,
        outcomes=(),
        households=(),
        shock_digest=shock_digest,
        llm_dispatch_count=0,
        economic_hash=None,
    )


DEFAULT_STREAM = STREAM_ALGORITHM
