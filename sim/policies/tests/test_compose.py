"""Rescue, a school meal, and a municipal basket share one ledger.

The household need is 500 grams. The school meal replaces 200, so the store
sells 300. Those 200 grams are consumed, not added to the pantry.
"""

from __future__ import annotations

import unittest

from sim.policies.compose import apply_joint
from sim.policies.core_interface import InMemoryCore
from sim.policies.groceries import GroceryCommand, Shopper
from sim.policies.processing import ProcessingCommand
from sim.policies.school_meals import HouseholdNeed, Pupil, SchoolCommand
from sim.policies.tests.support import assert_conserved, assert_integers


class ComposeTests(unittest.TestCase):
    def test_school_grams_are_not_also_pantry_and_subsidy_is_not_processing_cost(self) -> None:
        ledger = InMemoryCore()
        ledger.endow("municipality", 1000, memo="opening")
        ledger.endow("processor", 200, memo="opening")
        ledger.endow("household:h", 1000, memo="opening")
        ledger.endow("store", 0, memo="opening")
        ledger.open_lot(
            product_id="produce",
            owner="retailer",
            custody="retailer",
            grams=400,
            acquisition_cents=0,
            unsafe_after=500,
            source_kind="opening",
            input_class="rescued",
        )
        result = apply_joint(
            ledger,
            ProcessingCommand(
                evidence_state="illustrative",
                processor_account="processor",
                processor_owner="processor",
                processor_custody="processor",
                now=0,
                max_input_grams=400,
                mode="process",
                edible_num=1,
                edible_den=2,
                product_out="prepared_produce",
                output_unsafe_after=800,
                transport_cents=20,
                transport_payee="external:carrier",
                transport_loss_num=0,
                transport_loss_den=1,
                labor_cents=30,
                labor_payee="external:labor",
                pay_labor_if_idle=False,
                added_grams=0,
                added_product_id="water",
                cold_storage_grams=1000,
                demand_grams=200,
                demand_owner="school",
                demand_custody="kitchen",
                source_owners=("retailer",),
                accepted_classes=("rescued",),
                purchases=(),
            ),
            SchoolCommand(
                evidence_state="illustrative",
                program_account="program",
                school_owner="school",
                school_custody="kitchen",
                supplier_account="external:supplier",
                product_id="prepared_produce",
                food_source="on_hand",
                portion_grams=200,
                ingredient_cents_per_portion=0,
                kitchen_capacity=1,
                plate_waste_num=0,
                plate_waste_den=1,
                unsafe_after=800,
                now=0,
                pupils=(Pupil("a", "household:h", True, True, True, True, 0),),
                households=(HouseholdNeed("household:h", 500, 1, 1),),
            ),
            GroceryCommand(
                evidence_state="illustrative",
                funding_approved=True,
                site_ready=True,
                operator_ready=True,
                municipality_account="municipality",
                store_account="store",
                store_owner="store",
                store_custody="store",
                subsidy_cents=200,
                price_support_cents=120,
                minimum_cash_reserve=0,
                purchase_grams=300,
                purchase_cents=150,
                purchase_payee="external:supplier",
                product_id="staple",
                unsafe_after=1000,
                now=0,
                pricing="subsidized_below_cost",
                target_cents_per_1000g=100,
                reference_cents_per_1000g=500,
                overhead=(),
                shoppers=(Shopper("household:h", "household:h", 0, 0, 10, 30),),
                spoil_grams=0,
                disposal_fee_cents=0,
                disposal_payee="external:disposal",
                fee_relief_cents=0,
                capital_cents=0,
                capital_payee="external:capital",
            ),
        )
        assert_integers(self, result)
        assert_conserved(self, ledger)
        self.assertEqual(result.evidence_state, "illustrative")
        self.assertEqual(result.school_consumed_grams, 200)
        self.assertEqual(result.pantry_grams, 300)
        self.assertEqual(result.replaced_grams, 200)
        self.assertEqual(result.processing.delivered_grams, 200)
        self.assertEqual(result.processing.process_loss_grams, 200)
        self.assertEqual(result.processing_operating_cents, 50)
        self.assertEqual(result.school.ingredient_cents, 0)
        self.assertEqual(result.household_payment_cents, 30)
        self.assertEqual(result.subsidy_funded_discount_cents, 120)
        self.assertEqual(result.substitution_avoided_cents, 100)
        self.assertEqual(result.counterfactual_at_cost_cents, 250)
        self.assertEqual(result.fiscal_subsidy_cents, 200)
        self.assertEqual(ledger.cash("municipality"), 800)
        self.assertEqual(ledger.cash("processor"), 150)
        self.assertEqual(ledger.cash("household:h"), 970)
        self.assertEqual(ledger.cash("store"), 80)
        self.assertEqual(ledger.cash("external:supplier"), 150)
        self.assertEqual(ledger.cash("external:carrier"), 20)
        self.assertEqual(ledger.cash("external:labor"), 30)
        self.assertEqual(sum(lot.grams for lot in ledger.lots() if lot.owner == "school"), 0)
        self.assertEqual(ledger.conservation().grams_consumed, 200)
        self.assertEqual(ledger.conservation().grams_waste, 200)


if __name__ == "__main__":
    unittest.main()
