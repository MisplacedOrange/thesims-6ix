"""Adapter invariants the policy fixtures rely on."""

from __future__ import annotations

import unittest

from sim.policies.core_interface import InMemoryCore, LedgerError, largest_remainder
from sim.policies.tests.support import assert_conserved


class AllocateTests(unittest.TestCase):
    def test_largest_remainder_tie_breaks_by_key(self) -> None:
        # One cent, two equal weights. Key order, not dict order, decides.
        self.assertEqual(largest_remainder(1, {"b": 1, "a": 1}), {"a": 1, "b": 0})

    def test_partial_split_leaves_remainder_cents_on_the_source(self) -> None:
        ledger = InMemoryCore()
        lot_id = ledger.open_lot(
            product_id="produce",
            owner="store",
            custody="store",
            grams=3,
            acquisition_cents=10,
            unsafe_after=10,
            source_kind="opening",
            input_class="other",
        )
        piece = ledger.take(lot_id, 1)
        self.assertEqual(ledger.lot(piece).acquisition_cents, 3)
        self.assertEqual(ledger.lot(lot_id).grams, 2)
        self.assertEqual(ledger.lot(lot_id).acquisition_cents, 7)
        assert_conserved(self, ledger)


class LedgerTests(unittest.TestCase):
    def test_cash_reservation_blocks_a_second_spend(self) -> None:
        ledger = InMemoryCore()
        ledger.endow("store", 150, memo="opening")
        hold = ledger.reserve_cash("store", 100, key="subsidy")
        with self.assertRaises(LedgerError):
            ledger.transfer("store", "labor", 60, memo="wage")
        ledger.release_cash(hold)
        ledger.transfer("store", "labor", 60, memo="wage")
        self.assertEqual(ledger.cash("store"), 90)
        assert_conserved(self, ledger)

    def test_lot_reservation_is_exclusive(self) -> None:
        ledger = InMemoryCore()
        lot_id = ledger.open_lot(
            product_id="produce",
            owner="retailer",
            custody="dock",
            grams=200,
            acquisition_cents=0,
            unsafe_after=10,
            source_kind="opening",
            input_class="rescued",
        )
        ledger.reserve_lot(lot_id, "food_bank")
        with self.assertRaises(LedgerError):
            ledger.reserve_lot(lot_id, "processor")
        with self.assertRaises(LedgerError):
            ledger.take(lot_id, 200)

    def test_transform_must_balance(self) -> None:
        ledger = InMemoryCore()
        lot_id = ledger.open_lot(
            product_id="produce",
            owner="processor",
            custody="processor",
            grams=10,
            acquisition_cents=4,
            unsafe_after=10,
            source_kind="opening",
            input_class="rescued",
        )
        from sim.policies.core_interface import OutputDraft

        with self.assertRaises(LedgerError):
            ledger.replace_lot(
                lot_id,
                (
                    OutputDraft(
                        9,
                        4,
                        "prepared",
                        "processor",
                        "processor",
                        20,
                        "processed",
                        "rescued",
                        "stock",
                        "edible",
                    ),
                ),
            )

    def test_export_stays_inside_the_gram_identity(self) -> None:
        ledger = InMemoryCore()
        lot_id = ledger.open_lot(
            product_id="produce",
            owner="hub",
            custody="hub",
            grams=10,
            acquisition_cents=0,
            unsafe_after=10,
            source_kind="opening",
            input_class="other",
        )
        ledger.export_lot(lot_id, reason="left the district")
        snapshot = ledger.conservation()
        self.assertEqual(snapshot.grams_exported, 10)
        self.assertEqual(snapshot.grams_on_hand, 0)
        assert_conserved(self, ledger)


if __name__ == "__main__":
    unittest.main()
