"""Legal offers. An option the household cannot pay for is omitted."""

from __future__ import annotations

from dataclasses import dataclass

from sim.core import ChoiceOffer, FeasibleOption, ObservedFact, sha256_hex


@dataclass(frozen=True, slots=True)
class Candidate:
    option_id: str
    payment_cents: int
    grams: int
    score: int


def legal_candidates(candidates: tuple[Candidate, ...], spendable_cents: int) -> tuple[Candidate, ...]:
    affordable = tuple(
        candidate
        for candidate in candidates
        if candidate.payment_cents <= spendable_cents and candidate.grams > 0 and candidate.option_id != "no-purchase"
    )
    return affordable + (Candidate("no-purchase", 0, 0, 0),)


def rule_choice(candidates: tuple[Candidate, ...]) -> Candidate:
    if not candidates:
        raise ValueError("at least the no-purchase option is required")
    return min(candidates, key=lambda candidate: (-candidate.score, candidate.option_id))


def build_offer(
    decision_id: str,
    household_id: str,
    revision: int,
    facts: tuple[ObservedFact, ...],
    candidates: tuple[Candidate, ...],
) -> ChoiceOffer:
    ordered = tuple(sorted(candidates, key=lambda candidate: candidate.option_id))
    return ChoiceOffer(
        decision_id=decision_id,
        household_id=household_id,
        revision=revision,
        known_facts=facts,
        options=tuple(
            FeasibleOption(candidate.option_id, f"cents={candidate.payment_cents};grams={candidate.grams}")
            for candidate in ordered
        ),
    )


def observation_hash(offer: ChoiceOffer) -> str:
    return sha256_hex(offer)
