"""Household knowledge, legal offers, and rule fallback.

The LLM gateway is Person 2's. This package never enables it. A disabled
gateway still returns a legal rule choice.
"""

from sim.behavior.compare import ChoiceRow, by_income, summarize
from sim.behavior.fallback import REASONS, ResolvedChoice, decide
from sim.behavior.knowledge import known_facts, leaks_other_balance
from sim.behavior.offers import Candidate, build_offer, legal_candidates, observation_hash, rule_choice
from sim.behavior.panel import live_barrier, select_panel

__all__ = (
    "known_facts",
    "leaks_other_balance",
    "Candidate",
    "legal_candidates",
    "rule_choice",
    "build_offer",
    "observation_hash",
    "REASONS",
    "ResolvedChoice",
    "decide",
    "select_panel",
    "live_barrier",
    "ChoiceRow",
    "summarize",
    "by_income",
)
