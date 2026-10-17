"""Rule explanations and a grounding check for generated text.

Generated text may cite only event ids, household ids, and cent amounts that
are already on the offer. A failed check replaces the text with the rule
explanation. The replacement does not by itself change a legal option id.
"""

from __future__ import annotations

import re

from sim.behavior.draft import EXPLANATION_GROUNDED, EXPLANATION_REPLACED, ChoiceOffer, FeasibleOption

_EVENT_ID = re.compile(r"evt-[A-Za-z0-9_]+")
_HOUSEHOLD_ID = re.compile(r"hh-[A-Za-z0-9_]+")
_CENTS = re.compile(r"(\d+) cents")


def rule_explanation(offer: ChoiceOffer, option: FeasibleOption) -> str:
    events = ", ".join(offer.recent_event_ids) if offer.recent_event_ids else "none"
    store = option.store_id or "none"
    return (
        f"Household {offer.household_id} selected {option.option_id} under the rule policy. "
        f"Store {store}. Expected payment {option.expected_payment_cents} cents. "
        f"Collection time {option.total_seconds} seconds. "
        f"Cited events: {events}."
    )


def cited_event_ids(text: str, offer: ChoiceOffer) -> tuple[str, ...]:
    found = [event_id for event_id in _EVENT_ID.findall(text) if event_id in offer.recent_event_ids]
    return tuple(dict.fromkeys(found))


def ground_explanation(text: str | None, offer: ChoiceOffer, option: FeasibleOption) -> tuple[str, str, tuple[str, ...]]:
    """Return explanation, origin, and cited event ids."""

    fallback = rule_explanation(offer, option)
    if text is None or not text.strip():
        return fallback, EXPLANATION_REPLACED, cited_event_ids(fallback, offer)
    if _makes_unsupported_claim(text, offer):
        return fallback, EXPLANATION_REPLACED, cited_event_ids(fallback, offer)
    return text.strip(), EXPLANATION_GROUNDED, cited_event_ids(text, offer)


def _makes_unsupported_claim(text: str, offer: ChoiceOffer) -> bool:
    allowed_events = set(offer.recent_event_ids)
    for event_id in _EVENT_ID.findall(text):
        if event_id not in allowed_events:
            return True
    for household_id in _HOUSEHOLD_ID.findall(text):
        if household_id != offer.household_id:
            return True
    allowed_cents = {str(option.expected_payment_cents) for option in offer.options}
    for fact in offer.known_facts:
        for key, value in fact.attributes:
            if key == "cents":
                allowed_cents.add(value)
    for amount in _CENTS.findall(text):
        if amount not in allowed_cents:
            return True
    return False
