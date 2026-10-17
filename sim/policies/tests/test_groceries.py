"""Municipal grocery fixture.

Opening cash is household:h 1000, household:i 250, municipality 800.
The store receives a 600 subsidy, pays 100 of overhead, and buys 1000 grams
for 400 cents. Price support can fund only 150 cents of below-cost sales.
"""

from __future__ import annotations

import unittest
from dataclasses import replace

from sim.policies.core_interface import InMemoryCore
from sim.policies.groceries import (
    GroceryCommand,
    OverheadItem,
    Shopper,
    apply_grocery,
)
from sim.policies.tests.support import assert_conserved, assert_integers


def _command() -> GroceryCommand:
    return GroceryCommand(
        evidence_state="illustrative",
        funding_approved=True,
        site_ready=True,
        operator_ready=True,
        municipality_account="municipality",
        store_account="store",
        store_owner="store",
        store_custody="store",
        subsidy_cents=600,
        price_support_cents=150,
        minimum_cash_reserve=0,
        purchase_grams=1000,
        purchase_cents=400,
        purchase_payee="external:supplier",
        product_id="staple",
        unsafe_after=1000,
        now=0,
        pricing="subsidized_below_cost",
        target_cents_per_1000g=200,
        reference_cents_per_1000g=500,
        overhead=(
            OverheadItem("labor", 50, "external:labor"),
            OverheadItem("occupancy", 50, "external:occupancy"),
        ),
        shoppers=(
            Shopper("household:h", "household:h", 500, 0, 10, 30),
            Shopper("household:i", "household:i", 500, 1, 10, 30),
        ),
        spoil_grams=0,
        disposal_fee_cents=0,
        disposal_payee="external:disposal",
        fee_relief_cents=0,
        capital_cents=0,
        capital_payee="external:capital",
    )


def _endow(ledger: InMemoryCore) -> None:
    ledger.endow("household:h", 1000, memo="opening")
    ledger.endow("household:i", 250, memo="opening")
    ledger.endow("municipality", 800, memo="opening")
    ledger.endow("store", 0, memo="opening")


class GroceryTests(unittest.TestCase):
    def test_subsidy_funds_the_first_basket_then_price_returns_to_cost(self) -> None:
        first = InMemoryCore()
        second = InMemoryCore()
        _endow(first)
        _endow(second)
        result = apply_grocery(first, _command())
        again = apply_grocery(second, _command())
        self.assertEqual(result, again)
        assert_integers(self, result)
        assert_conserved(self, first)

        self.assertEqual(result.status, "open")
        self.assertEqual(result.evidence_state, "illustrative")
        self.assertTrue(result.subsidy_exhausted)
        self.assertFalse(result.procurement_delayed)
        self.assertEqual(result.subsidy_transferred_cents, 600)
        self.assertEqual(result.price_support_used_cents, 100)
        self.assertEqual(result.funded_price_reduction_cents, 100)
        self.assertEqual(result.sales_receipts_cents, 300)
        self.assertEqual(result.cogs_cents, 400)
        self.assertEqual(result.inventory_payments_cents, 400)
        self.assertEqual(result.labor_cents, 50)
        self.assertEqual(result.occupancy_cents, 50)
        self.assertEqual(result.operating_result_cents, 400)
        self.assertEqual(result.cash_before_subsidy_cents, -200)
        self.assertEqual(result.cash_funding_gap_cents, 200)
        # Supplier payment plus overhead. The subsidy is financing, not a second resource cost.
        self.assertEqual(result.external_resource_cents, 500)
        self.assertEqual(result.household_savings_vs_reference_cents, 200)
        self.assertEqual(result.fee_relief_cents, 0)
        self.assertEqual(result.capital_cents, 0)
        self.assertEqual(
            [(sale.household_id, sale.outcome, sale.paid_cents, sale.price_rule_applied, sale.funded_gap_cents, sale.savings_vs_reference_cents, sale.margin_not_charged_cents) for sale in result.sales],
            [
                ("household:h", "sold", 100, "subsidized", 100, 150, 50),
                ("household:i", "sold", 200, "at_cost", 0, 50, 50),
            ],
        )
        self.assertEqual(first.cash("household:h"), 900)
        self.assertEqual(first.cash("household:i"), 50)
        self.assertEqual(first.cash("municipality"), 200)
        self.assertEqual(first.cash("store"), 400)
        self.assertEqual(first.cash("external:supplier"), 400)
        self.assertEqual(first.cash("external:labor"), 50)
        self.assertEqual(first.cash("external:occupancy"), 50)
        self.assertEqual(_grams(first, "household:h"), 500)
        self.assertEqual(_grams(first, "household:i"), 500)
        self.assertEqual(first.conservation().grams_imported, 1000)
        self.assertEqual(first.conservation().grams_on_hand, 1000)

    def test_planning_state_posts_nothing(self) -> None:
        ledger = InMemoryCore()
        _endow(ledger)
        before = ledger.journal()
        command = replace(
            _command(),
            funding_approved=False,
            fee_relief_cents=30,
            subsidy_cents=600,
        )
        result = apply_grocery(ledger, command)
        self.assertEqual(result.status, "planning")
        self.assertEqual(result.subsidy_transferred_cents, 0)
        self.assertEqual(result.fee_relief_cents, 0)
        self.assertEqual(result.operating_result_cents, 0)
        self.assertEqual(ledger.journal(), before)
        self.assertEqual({sale.outcome for sale in result.sales}, {"not_operating"})
        assert_conserved(self, ledger)

    def test_underfunded_store_delays_procurement_and_records_fee_relief(self) -> None:
        ledger = InMemoryCore()
        ledger.endow("municipality", 100, memo="opening")
        ledger.endow("household:h", 500, memo="opening")
        ledger.endow("household:j", 0, memo="opening")
        ledger.endow("store", 0, memo="opening")
        command = replace(
            _command(),
            subsidy_cents=100,
            price_support_cents=0,
            purchase_grams=1000,
            purchase_cents=400,
            overhead=(OverheadItem("labor", 80, "external:labor"),),
            fee_relief_cents=30,
            shoppers=(
                Shopper("household:h", "household:h", 400, 0, 10, 30),
                Shopper("household:j", "household:j", 400, 1, 40, 10),
            ),
        )
        result = apply_grocery(ledger, command)
        assert_integers(self, result)
        assert_conserved(self, ledger)
        self.assertTrue(result.procurement_delayed)
        self.assertEqual(result.grams_purchased, 0)
        self.assertEqual(result.fee_relief_cents, 30)
        self.assertEqual(result.overhead_unpaid_cents, 0)
        self.assertEqual(result.labor_cents, 80)
        self.assertEqual(result.external_resource_cents, 80)
        self.assertEqual(result.operating_result_cents, 20)
        self.assertEqual(result.cash_before_subsidy_cents, -80)
        self.assertEqual(result.cash_funding_gap_cents, 80)
        self.assertEqual(result.unmet_grams, 800)
        self.assertEqual(
            [(sale.household_id, sale.outcome) for sale in result.sales],
            [("household:h", "stockout"), ("household:j", "time_budget")],
        )
        self.assertEqual(ledger.cash("municipality"), 0)
        self.assertEqual(ledger.cash("store"), 20)
        self.assertEqual(ledger.cash("external:labor"), 80)
        self.assertEqual(ledger.cash("household:h"), 500)
        self.assertEqual(ledger.conservation().grams_imported, 0)
        self.assertFalse(any(entry.memo == "fee relief" for entry in ledger.journal()))

    def test_spoilage_recognizes_acquisition_once_and_disposal_is_cash(self) -> None:
        ledger = InMemoryCore()
        ledger.endow("municipality", 500, memo="opening")
        ledger.endow("household:h", 200, memo="opening")
        ledger.endow("store", 0, memo="opening")
        command = replace(
            _command(),
            subsidy_cents=300,
            price_support_cents=0,
            pricing="at_cost",
            target_cents_per_1000g=0,
            reference_cents_per_1000g=0,
            purchase_grams=500,
            purchase_cents=200,
            overhead=(),
            spoil_grams=300,
            disposal_fee_cents=15,
            shoppers=(Shopper("household:h", "household:h", 200, 0, 5, 20),),
        )
        result = apply_grocery(ledger, command)
        assert_integers(self, result)
        assert_conserved(self, ledger)
        self.assertEqual(result.cogs_cents, 80)
        self.assertEqual(result.writeoff_cents, 120)
        self.assertEqual(result.disposal_cents, 15)
        self.assertEqual(result.sales_receipts_cents, 80)
        self.assertEqual(result.operating_result_cents, 165)
        self.assertEqual(result.cash_before_subsidy_cents, -135)
        self.assertEqual(result.cash_funding_gap_cents, 135)
        # Acquisition of the spoiled lot is not posted again as cash.
        self.assertEqual(ledger.cash("store"), 165)
        self.assertEqual(ledger.cash("external:disposal"), 15)
        self.assertEqual(ledger.cash("external:supplier"), 200)
        self.assertEqual(ledger.cash("household:h"), 120)
        self.assertEqual(_grams(ledger, "household:h"), 200)
        self.assertEqual(ledger.conservation().grams_waste, 300)
        self.assertEqual(ledger.conservation().writeoff_acquisition_cents, 120)


def _grams(ledger: InMemoryCore, owner: str) -> int:
    return sum(lot.grams for lot in ledger.lots() if lot.owner == owner)


if __name__ == "__main__":
    unittest.main()
