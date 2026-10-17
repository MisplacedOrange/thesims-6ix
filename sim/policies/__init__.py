"""Neighbourhood food-policy mechanisms for weeks 6 to 8.

The authoritative accounts and lots live behind ``core_interface``. This
package decides who is served, which price is charged, and which costs are
reported. It does not persist runs, call providers, or draw random numbers.
"""

from sim.policies.compose import JointResult, apply_joint
from sim.policies.groceries import GroceryCommand, GroceryResult, apply_grocery
from sim.policies.processing import ProcessingCommand, ProcessingResult, apply_processing
from sim.policies.procurement import (
    ArmResult,
    DecentralizedArm,
    PooledArm,
    run_decentralized,
    run_pooled,
)
from sim.policies.school_meals import (
    SchoolCommand,
    SchoolDayResult,
    apply_school_day,
    settle_home_purchases,
)

__all__ = [
    "ArmResult",
    "DecentralizedArm",
    "GroceryCommand",
    "GroceryResult",
    "JointResult",
    "PooledArm",
    "ProcessingCommand",
    "ProcessingResult",
    "SchoolCommand",
    "SchoolDayResult",
    "apply_grocery",
    "apply_joint",
    "apply_processing",
    "apply_school_day",
    "run_decentralized",
    "run_pooled",
    "settle_home_purchases",
]
