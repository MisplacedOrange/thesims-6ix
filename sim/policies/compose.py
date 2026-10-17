"""One neighbourhood day that runs rescue, school meals, then groceries.

School consumption reduces the household's grocery request before the store
sells. The same grams are not pantry stock and a served meal. The subsidy
that lowers the store price is not added to the processor's operating cost.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from sim.policies.core_interface import CoreLedger
from sim.policies.groceries import GroceryCommand, GroceryResult, apply_grocery
from sim.policies.processing import ProcessingCommand, ProcessingResult, apply_processing
from sim.policies.school_meals import SchoolCommand, SchoolDayResult, apply_school_day


@dataclass(frozen=True)
class JointResult:
    evidence_state: str
    processing: ProcessingResult
    school: SchoolDayResult
    grocery: GroceryResult
    school_consumed_grams: int
    pantry_grams: int
    replaced_grams: int
    household_payment_cents: int
    counterfactual_at_cost_cents: int
    subsidy_funded_discount_cents: int
    substitution_avoided_cents: int
    processing_operating_cents: int
    fiscal_subsidy_cents: int


def apply_joint(
    ledger: CoreLedger,
    processing: ProcessingCommand,
    school: SchoolCommand,
    grocery: GroceryCommand,
) -> JointResult:
    """Process food, serve meals, then sell the residual home basket."""

    states = {processing.evidence_state, school.evidence_state, grocery.evidence_state}
    if len(states) != 1:
        raise ValueError("joint day requires one evidence state")
    processed = apply_processing(ledger, processing)
    served = apply_school_day(ledger, school)
    needs = {item.household_id: item.need_grams for item in school.households}
    replaced = {item.household_id: item.replaced_grams for item in served.households}
    shoppers = []
    for shopper in grocery.shoppers:
        if shopper.household_id not in needs:
            shoppers.append(shopper)
            continue
        residual = max(0, needs[shopper.household_id] - replaced[shopper.household_id])
        shoppers.append(replace(shopper, requested_grams=residual))
    sold = apply_grocery(ledger, replace(grocery, shoppers=tuple(shoppers)))
    if sold.grams_purchased:
        rate = sold.inventory_payments_cents * 1000 // sold.grams_purchased
    else:
        rate = 0
    counterfactual = 0
    avoided = 0
    pantry = 0
    for shopper in shoppers:
        if shopper.household_id not in needs:
            continue
        counterfactual += needs[shopper.household_id] * rate // 1000
        avoided += replaced[shopper.household_id] * rate // 1000
        pantry += sum(lot.grams for lot in ledger.lots() if lot.owner == shopper.household_id)
    return JointResult(
        evidence_state=processing.evidence_state,
        processing=processed,
        school=served,
        grocery=sold,
        school_consumed_grams=served.grams_consumed,
        pantry_grams=pantry,
        replaced_grams=sum(replaced[shopper.household_id] for shopper in shoppers if shopper.household_id in replaced),
        household_payment_cents=sold.sales_receipts_cents,
        counterfactual_at_cost_cents=counterfactual,
        subsidy_funded_discount_cents=sold.funded_price_reduction_cents,
        substitution_avoided_cents=avoided,
        processing_operating_cents=processed.operating_cents,
        fiscal_subsidy_cents=sold.subsidy_transferred_cents,
    )
