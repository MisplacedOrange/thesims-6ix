"""Household choice behaviour for the Toronto food-policy simulator.

This package builds legal offers, applies household knowledge, selects the
fixed LLM panel, and scores rule-based choices. It does not settle ledgers,
call a model provider, or store runs. Those belong to ``sim/core`` and to the
gateway and persistence work.

The choice-offer and choice-receipt records are draft ``0-draft`` and are
marked ``DRAFT_JOINT_REVIEW_PERSON_2``.
"""

from sim.behavior.draft import (
    CHOICE_FORMAT_STATUS,
    SCHEMA_VERSION,
    ChoiceOffer,
    ChoiceReceipt,
    GatewayObservation,
    GatewayRequest,
    GatewayResponse,
)

__all__ = [
    "CHOICE_FORMAT_STATUS",
    "SCHEMA_VERSION",
    "ChoiceOffer",
    "ChoiceReceipt",
    "GatewayObservation",
    "GatewayRequest",
    "GatewayResponse",
]

PACKAGE_VERSION = "0.1.0"
