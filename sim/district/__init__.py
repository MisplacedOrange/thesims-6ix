"""Synthetic district baseline.

Import this package for the 250-household run. Shopping, population, and
travel rules live here. Money, food lots, and reservations are settled only
by ``sim.core``. Policy, logistics, behavior, and experiment packages are
separate owners and are not imported here.
"""

from sim.district.baseline import BaselineReport, BaselineResult, Check, Trip, run_baseline
from sim.district.network import Edge, Network, shortest_path
from sim.district.population import (
    Household,
    Member,
    Population,
    Pupil,
    attendance_present,
    build_population,
)
from sim.district.shopping import DayPlan, ScoredOption, choice_noise, choose, plan_household, score_option
from sim.district.snapshot import Snapshot, SnapshotError, load_snapshot

__all__ = (
    "run_baseline",
    "BaselineReport",
    "BaselineResult",
    "Check",
    "Trip",
    "load_snapshot",
    "Snapshot",
    "SnapshotError",
    "build_population",
    "attendance_present",
    "Household",
    "Member",
    "Population",
    "Pupil",
    "shortest_path",
    "Network",
    "Edge",
    "score_option",
    "choice_noise",
    "choose",
    "plan_household",
    "DayPlan",
    "ScoredOption",
)
