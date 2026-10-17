"""Neighbourhood logistics: queues, vans, drones, metrics, and paired runs.

Accounting stays behind ``core_interface.CorePort``. This package does not
import ``sim.core`` and does not own cash balances or gram quantities.
"""

from sim.logistics.compatibility import CompatibilityError, paired_difference
from sim.logistics.engine import LogisticsEngine
from sim.logistics.units import UNIT_SYSTEM

__all__ = [
    "UNIT_SYSTEM",
    "CompatibilityError",
    "LogisticsEngine",
    "paired_difference",
]
