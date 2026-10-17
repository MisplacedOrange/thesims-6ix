"""Policy mechanisms. Each one posts kernel commands and reads costs back from the ledger.

School meals, groceries, processing, and procurement are illustrative.
They do not claim a measured Toronto effect.
"""

from sim.policies.groceries import GroceryResult, run_municipal_grocery
from sim.policies.meals import MealDay, run_school_day
from sim.policies.processing import ProcessingResult, run_processing
from sim.policies.procurement import ProcurementResult, run_procurement

__all__ = (
    "run_municipal_grocery",
    "GroceryResult",
    "run_processing",
    "ProcessingResult",
    "run_school_day",
    "MealDay",
    "run_procurement",
    "ProcurementResult",
)
