"""Pooled procurement at the same served demand as two separate orders.

Each site needs 3000 grams. Decentralized orders have no storage loss.
The pool loses one gram in five after delivery, so it orders 7499 grams to
serve 6000. The volume discount does not offset hub cost and spoilage.
"""

from __future__ import annotations

import unittest

from sim.policies.core_interface import InMemoryCore
from sim.policies.procurement import (
    DecentralizedArm,
    PooledArm,
    PriceBand,
    SiteDemand,
    SupplyContract,
    run_decentralized,
    run_pooled,
)
from sim.policies.tests.support import assert_conserved, assert_integers

BANDS = (PriceBand(0, 200), PriceBand(5000, 150))
SITES = (
    SiteDemand("school:a", "school:a", "school:a", "school:a", 3000, 0),
    SiteDemand("school:b", "school:b", "school:b", "school:b", 3000, 1),
)


def _contract(**changes: object) -> SupplyContract:
    from dataclasses import replace

    contract = SupplyContract(
        evidence_state="illustrative",
        bands=BANDS,
        minimum_order_grams=0,
        expected_receive_num=1,
        expected_receive_den=1,
        actual_receive_num=1,
        actual_receive_den=1,
        loss_num=0,
        loss_den=1,
        pay_for="ordered",
        supplier_account="external:supplier",
        product_id="produce",
        unsafe_after=1000,
        now=0,
    )
    if changes:
        contract = replace(contract, **changes)
    return contract


def _endow(ledger: InMemoryCore) -> None:
    ledger.endow("hub", 2000, memo="opening")
    ledger.endow("school:a", 1000, memo="opening")
    ledger.endow("school:b", 1000, memo="opening")


class ProcurementTests(unittest.TestCase):
    def test_equal_served_grams_can_cost_more_when_pooled(self) -> None:
        separate = InMemoryCore()
        pooled = InMemoryCore()
        _endow(separate)
        _endow(pooled)
        decentralized = run_decentralized(
            separate,
            SITES,
            DecentralizedArm(_contract(), delivery_cents=25, delivery_payee="external:carrier"),
        )
        pool = run_pooled(
            pooled,
            SITES,
            PooledArm(
                _contract(loss_num=1, loss_den=5),
                buyer_account="hub",
                hub_owner="hub",
                hub_custody="hub",
                labor_cents=80,
                labor_payee="external:labor",
                inbound_cents=40,
                inbound_payee="external:carrier",
                outbound_cents=15,
                outbound_payee="external:carrier",
            ),
        )
        assert_integers(self, decentralized)
        assert_integers(self, pool)
        assert_conserved(self, separate)
        assert_conserved(self, pooled)

        self.assertEqual(decentralized.served_grams, 6000)
        self.assertEqual(pool.served_grams, 6000)
        self.assertEqual(decentralized.ordered_grams, 6000)
        self.assertEqual(decentralized.food_cents, 1200)
        self.assertEqual(decentralized.delivery_cents, 50)
        self.assertEqual(decentralized.labor_cents, 0)
        self.assertEqual(decentralized.total_cents, 1250)
        self.assertEqual(decentralized.rate_cents_per_1000g, 200)
        self.assertFalse(decentralized.discount_applied)
        self.assertEqual(decentralized.spoilage_grams, 0)
        self.assertEqual(pool.ordered_grams, 7499)
        self.assertEqual(pool.spoilage_grams, 1499)
        self.assertEqual(pool.food_cents, 1124)
        self.assertEqual(pool.labor_cents, 80)
        self.assertEqual(pool.delivery_cents, 70)
        self.assertEqual(pool.total_cents, 1274)
        self.assertEqual(pool.rate_cents_per_1000g, 150)
        self.assertTrue(pool.discount_applied)
        self.assertGreater(pool.total_cents, decentralized.total_cents)
        self.assertEqual(
            [(site.site_id, site.served_grams, site.unmet_grams) for site in pool.sites],
            [("school:a", 3000, 0), ("school:b", 3000, 0)],
        )
        self.assertEqual(_holding(pooled, "school:a"), (3000, 450))
        self.assertEqual(_holding(pooled, "school:b"), (3000, 450))
        self.assertEqual(pooled.cash("hub"), 726)
        self.assertEqual(pooled.cash("external:supplier"), 1124)
        self.assertEqual(pooled.cash("external:labor"), 80)
        self.assertEqual(pooled.cash("external:carrier"), 70)
        self.assertEqual(separate.cash("school:a"), 375)
        self.assertEqual(separate.cash("school:b"), 375)
        self.assertEqual(separate.cash("external:supplier"), 1200)
        self.assertEqual(separate.cash("external:carrier"), 50)
        self.assertEqual(separate.cash("hub"), 2000)

    def test_prepaid_shortfall_serves_the_higher_priority_site_only(self) -> None:
        ledger = InMemoryCore()
        _endow(ledger)
        pool = run_pooled(
            ledger,
            SITES,
            PooledArm(
                _contract(loss_num=1, loss_den=5, actual_receive_num=1, actual_receive_den=2),
                buyer_account="hub",
                hub_owner="hub",
                hub_custody="hub",
                labor_cents=80,
                labor_payee="external:labor",
                inbound_cents=40,
                inbound_payee="external:carrier",
                outbound_cents=15,
                outbound_payee="external:carrier",
            ),
        )
        assert_integers(self, pool)
        assert_conserved(self, ledger)
        self.assertEqual(pool.ordered_grams, 7499)
        self.assertEqual(pool.delivered_grams, 3749)
        self.assertEqual(pool.shortage_grams, 3750)
        self.assertEqual(pool.shortage_loss_cents, 562)
        self.assertEqual(pool.spoilage_grams, 749)
        self.assertEqual(pool.served_grams, 3000)
        self.assertEqual(pool.unmet_grams, 3000)
        self.assertEqual(pool.food_cents, 1124)
        self.assertEqual(pool.total_cents, 1274)
        self.assertTrue(pool.discount_applied)
        self.assertEqual(
            [(site.site_id, site.served_grams, site.unmet_grams) for site in pool.sites],
            [("school:a", 3000, 0), ("school:b", 0, 3000)],
        )
        self.assertEqual(_holding(ledger, "school:a"), (3000, 450))
        self.assertEqual(_grams(ledger, "school:b"), 0)
        self.assertEqual(ledger.conservation().grams_imported, 3749)
        self.assertEqual(ledger.conservation().grams_waste, 749)
        self.assertEqual(ledger.conservation().non_mass_loss_cents, 562)
        self.assertEqual(ledger.cash("external:supplier"), 1124)
        self.assertEqual(ledger.cash("hub"), 726)

    def test_order_below_the_minimum_buys_nothing(self) -> None:
        ledger = InMemoryCore()
        ledger.endow("hub", 500, memo="opening")
        sites = (
            SiteDemand("school:a", "school:a", "school:a", "school:a", 500, 0),
            SiteDemand("school:b", "school:b", "school:b", "school:b", 500, 1),
        )
        pool = run_pooled(
            ledger,
            sites,
            PooledArm(
                _contract(minimum_order_grams=10_000),
                buyer_account="hub",
                hub_owner="hub",
                hub_custody="hub",
                labor_cents=80,
                labor_payee="external:labor",
                inbound_cents=40,
                inbound_payee="external:carrier",
                outbound_cents=15,
                outbound_payee="external:carrier",
            ),
        )
        assert_conserved(self, ledger)
        self.assertTrue(pool.refused)
        self.assertEqual(pool.refusal, "below_minimum")
        self.assertEqual(pool.served_grams, 0)
        self.assertEqual(pool.unmet_grams, 1000)
        self.assertEqual(pool.total_cents, 0)
        self.assertEqual(pool.food_cents, 0)
        self.assertEqual(pool.labor_cents, 0)
        self.assertEqual(ledger.cash("hub"), 500)
        self.assertEqual(ledger.conservation().grams_imported, 0)


def _holding(ledger: InMemoryCore, owner: str) -> tuple[int, int]:
    lots = [lot for lot in ledger.lots() if lot.owner == owner]
    return sum(lot.grams for lot in lots), sum(lot.acquisition_cents for lot in lots)


def _grams(ledger: InMemoryCore, owner: str) -> int:
    return sum(lot.grams for lot in ledger.lots() if lot.owner == owner)


if __name__ == "__main__":
    unittest.main()
