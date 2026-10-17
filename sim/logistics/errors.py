"""Errors raised by the logistics model.

These are scenario and contract failures, not accounting failures. The core
adapter raises ``CoreRejection`` when a reservation or posting violates the
ledger contract.
"""


class LogisticsError(ValueError):
    """The logistics engine refused a call or reached an impossible state."""


class UnitError(LogisticsError):
    """A quantity was not an integer in the declared unit."""
