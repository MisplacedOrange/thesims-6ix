"""Minimal ledger seam for policy mechanisms.

Policies depend on this package, not on ``sim.core``. ``InMemoryCore`` is the
stand-in adapter. A later wiring replaces it with the authoritative core
without changing the policy modules.
"""

from sim.policies.core_interface.allocate import largest_remainder, partial_acquisition
from sim.policies.core_interface.draw import plan_draw, quote_acquisition
from sim.policies.core_interface.ledger import (
    Conservation,
    CoreLedger,
    InMemoryCore,
    JournalEntry,
    LedgerError,
    LotView,
    OutputDraft,
    WasteRecord,
)

__all__ = [
    "Conservation",
    "CoreLedger",
    "InMemoryCore",
    "JournalEntry",
    "LedgerError",
    "LotView",
    "OutputDraft",
    "WasteRecord",
    "largest_remainder",
    "partial_acquisition",
    "plan_draw",
    "quote_acquisition",
]
