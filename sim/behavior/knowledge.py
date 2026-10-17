"""What one household is allowed to see at a decision.

Another household's balance is not a fact. Tomorrow's stock is not a fact.
"""

from __future__ import annotations

from sim.core import ObservedFact, account_for_owner, lots_for_owner, spendable_cents


def known_facts(state, household_id: str, public_prices: tuple[tuple[str, int], ...]) -> tuple[ObservedFact, ...]:
    account = account_for_owner(state, household_id)
    if account is None:
        raise KeyError(household_id)
    pantry = sum(lot.grams for lot in lots_for_owner(state, household_id) if lot.journey_id is None)
    facts = [
        ObservedFact("household_id", household_id),
        ObservedFact("spendable_cents", str(spendable_cents(account))),
        ObservedFact("pantry_grams", str(pantry)),
    ]
    for store_id, cents in public_prices:
        facts.append(ObservedFact(f"price:{store_id}", str(cents)))
    return tuple(facts)


def leaks_other_balance(facts: tuple[ObservedFact, ...], other_household_id: str, other_cents: int) -> bool:
    secret = str(other_cents)
    for fact in facts:
        if fact.fact_id == "household_id":
            continue
        if other_household_id in fact.fact_id or fact.value == secret:
            return True
    return False
