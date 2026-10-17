"""Rule fallback. The gateway is disabled by default and is not called here.

``not_selected_for_live_barrier`` is a schedule outcome. It is not a timeout.
"""

from __future__ import annotations

from dataclasses import dataclass

from sim.core import ChoiceOffer, ChoiceReceipt

from sim.behavior.offers import Candidate, observation_hash, rule_choice

REASONS = (
    "gateway_disabled",
    "not_selected_for_live_barrier",
    "missing",
    "refused",
    "invalid_option",
    "late",
    "stale_revision",
    "unaffordable",
    "accepted",
)


@dataclass(frozen=True, slots=True)
class ResolvedChoice:
    receipt: ChoiceReceipt
    reason: str


def decide(
    offer: ChoiceOffer,
    candidates: tuple[Candidate, ...],
    receipt: ChoiceReceipt | None,
    *,
    gateway_enabled: bool,
    selected_for_live: bool,
    late: bool,
    affordable_option_ids: frozenset[str],
) -> ResolvedChoice:
    rule = rule_choice(candidates)
    digest = observation_hash(offer)
    if not gateway_enabled:
        return _rule(offer, rule, digest, "gateway_disabled")
    if not selected_for_live:
        return _rule(offer, rule, digest, "not_selected_for_live_barrier")
    reason = _rejection(offer, receipt, late=late, affordable_option_ids=affordable_option_ids)
    if reason is not None or receipt is None:
        return ResolvedChoice(
            ChoiceReceipt(
                decision_id=offer.decision_id,
                option_id=rule.option_id,
                origin="fallback",
                observation_hash=digest,
                explanation=f"fallback {reason or 'missing'} -> {rule.option_id}",
            ),
            reason or "missing",
        )
    return ResolvedChoice(
        ChoiceReceipt(
            decision_id=offer.decision_id,
            option_id=receipt.option_id,
            origin=receipt.origin,
            observation_hash=digest,
            explanation=receipt.explanation,
        ),
        "accepted",
    )


def _rule(offer: ChoiceOffer, rule: Candidate, digest: str, reason: str) -> ResolvedChoice:
    return ResolvedChoice(
        ChoiceReceipt(
            decision_id=offer.decision_id,
            option_id=rule.option_id,
            origin="rule",
            observation_hash=digest,
            explanation=f"{reason} {rule.option_id}",
        ),
        reason,
    )


def _rejection(
    offer: ChoiceOffer,
    receipt: ChoiceReceipt | None,
    *,
    late: bool,
    affordable_option_ids: frozenset[str],
) -> str | None:
    if receipt is None:
        return "missing"
    if late:
        return "late"
    if receipt.decision_id != offer.decision_id:
        return "invalid_option"
    if receipt.option_id == "refused":
        return "refused"
    legal = {option.option_id for option in offer.options}
    if receipt.option_id not in legal:
        return "invalid_option"
    if receipt.observation_hash != observation_hash(offer):
        return "stale_revision"
    if receipt.option_id not in affordable_option_ids and receipt.option_id != "no-purchase":
        return "unaffordable"
    if receipt.origin not in {"rule", "llm", "recorded", "fallback"}:
        return "invalid_option"
    return None
