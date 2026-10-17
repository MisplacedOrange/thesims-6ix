"""Reproducible experiment reports. The gateway stays disabled.

The screening study declares 480 planned runs and executes the cells it is
given. Limitations are part of the report.
"""

from sim.experiments.drones import MODES, DroneResult, run_drones
from sim.experiments.screening import (
    PLANNED_RUNS,
    CellResult,
    ExperimentReport,
    all_cells,
    run_screening,
)
from sim.experiments.sensitivity import SweepPoint, grocery_price_sweep, procurement_spoilage_sweep
from sim.experiments.subgroups import SubgroupReport, population_subgroups

__all__ = (
    "run_drones",
    "DroneResult",
    "MODES",
    "run_screening",
    "ExperimentReport",
    "CellResult",
    "all_cells",
    "PLANNED_RUNS",
    "grocery_price_sweep",
    "procurement_spoilage_sweep",
    "SweepPoint",
    "population_subgroups",
    "SubgroupReport",
)
