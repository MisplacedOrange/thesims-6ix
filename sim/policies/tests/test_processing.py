"""Rescue and processing fixture.

Retailer opening stock is 200 reserved grams plus 800 eligible rescued grams.
The processor buys 400 grams, of which capacity accepts 200. Yield is 3/4.
"""

from __future__ import annotations

import unittest

from sim.policies.core_interface import InMemoryCore
from sim.policies.processing import ProcessingCommand, PurchaseInput, apply_processing
from sim.policies.tests.support import assert_conserved, assert_integers


def _command(**changes: object) -> ProcessingCommand:
    command = ProcessingCommand(
        evidence_state="illustrative",
        processor_account="processor",
        processor_owner="processor",
        processor_custody="processor",
        now=10,
        max_input_grams=1000,
        mode="process",
        edible_num=3,
        edible_den=4,
        product_out="prepared_produce",
        output_unsafe_after=400,
        transport_cents=50,
        transport_payee="external:carrier",
        transport_loss_num=0,
        transport_loss_den=1,
        labor_cents=80,
        labor_payee="external:labor",
        pay_labor_if_idle=False,
        added_grams=0,
        added_product_id="water",
        cold_storage_grams=200,
        demand_grams=500,
        demand_owner="hub",
        demand_custody="hub",
        source_owners=("retailer", "processor"),
        accepted_classes=("rescued", "purchased"),
        purchases=(
            PurchaseInput("produce", 400, 120, 200, "external:supplier"),
        ),
    )
    if changes:
        from dataclasses import replace

        command = replace(command, **changes)
    return command


class ProcessingTests(unittest.TestCase):
    def test_fefo_recipe_leaves_baseline_donation_untouched(self) -> None:
        ledger = InMemoryCore()
        ledger.endow("processor", 300, memo="opening")
        donation = ledger.open_lot(
            product_id="produce",
            owner="retailer",
            custody="retailer",
            grams=200,
            acquisition_cents=0,
            unsafe_after=50,
            source_kind="opening",
            input_class="rescued",
        )
        ledger.open_lot(
            product_id="produce",
            owner="retailer",
            custody="retailer",
            grams=800,
            acquisition_cents=0,
            unsafe_after=80,
            source_kind="opening",
            input_class="rescued",
        )
        ledger.reserve_lot(donation, "food_bank")
        result = apply_processing(ledger, _command())
        assert_integers(self, result)
        assert_conserved(self, ledger)

        self.assertEqual(result.evidence_state, "illustrative")
        self.assertEqual(result.output_product_id, "prepared_produce")
        self.assertEqual(result.skipped_reserved_grams, 200)
        self.assertEqual(result.accepted_grams, 1000)
        self.assertEqual(result.accepted_by_class, (("purchased", 200), ("rescued", 800)))
        self.assertEqual(result.unprocessed_grams, 200)
        self.assertEqual(result.edible_grams, 750)
        self.assertEqual(result.edible_by_class, (("purchased", 150), ("rescued", 600)))
        self.assertEqual(result.process_loss_grams, 250)
        self.assertEqual(result.delivered_grams, 500)
        self.assertEqual(result.storage_spoilage_grams, 50)
        self.assertEqual(result.stored_grams, 200)
        self.assertEqual(result.purchased_input_cents, 120)
        self.assertEqual(result.transport_cents, 50)
        self.assertEqual(result.labor_cents, 80)
        self.assertEqual(result.operating_cents, 130)
        self.assertTrue(result.unit_cost_defined)
        self.assertEqual(result.usable_delivered_grams, 500)
        self.assertEqual(ledger.lot(donation).owner, "retailer")
        self.assertEqual(ledger.lot(donation).grams, 200)
        self.assertEqual(_holding(ledger, "hub", "prepared_produce", "rescued"), (500, 0))
        self.assertEqual(_holding(ledger, "processor", "prepared_produce", "rescued"), (50, 0))
        self.assertEqual(_holding(ledger, "processor", "prepared_produce", "purchased"), (150, 45))
        self.assertEqual(_holding(ledger, "processor", "produce", "purchased"), (200, 60))
        self.assertEqual(ledger.conservation().writeoff_acquisition_cents, 15)
        self.assertEqual(ledger.cash("processor"), 50)
        self.assertEqual(ledger.cash("external:supplier"), 120)
        self.assertEqual(ledger.cash("external:carrier"), 50)
        self.assertEqual(ledger.cash("external:labor"), 80)
        self.assertEqual(
            result.edible_grams,
            result.delivered_grams + result.stored_grams + result.storage_spoilage_grams,
        )

    def test_direct_redistribution_delivers_more_grams_at_a_lower_operating_cost(self) -> None:
        direct_ledger = InMemoryCore()
        process_ledger = InMemoryCore()
        for ledger in (direct_ledger, process_ledger):
            ledger.endow("processor", 200, memo="opening")
            ledger.open_lot(
                product_id="produce",
                owner="retailer",
                custody="retailer",
                grams=800,
                acquisition_cents=0,
                unsafe_after=80,
                source_kind="opening",
                input_class="rescued",
            )
        direct = apply_processing(
            direct_ledger,
            _command(
                mode="direct",
                purchases=(),
                transport_cents=40,
                labor_cents=0,
                cold_storage_grams=10_000,
                demand_grams=10_000,
            ),
        )
        processed = apply_processing(
            process_ledger,
            _command(
                purchases=(),
                transport_cents=40,
                labor_cents=80,
                cold_storage_grams=10_000,
                demand_grams=10_000,
            ),
        )
        assert_conserved(self, direct_ledger)
        assert_conserved(self, process_ledger)
        self.assertEqual(direct.delivered_grams, 800)
        self.assertEqual(direct.operating_cents, 40)
        self.assertEqual(direct.process_loss_grams, 0)
        self.assertEqual(direct.output_product_id, "produce")
        self.assertEqual(processed.delivered_grams, 600)
        self.assertEqual(processed.process_loss_grams, 200)
        self.assertEqual(processed.operating_cents, 120)
        self.assertEqual(processed.output_product_id, "prepared_produce")
        self.assertEqual(direct_ledger.cash("processor"), 160)
        self.assertEqual(process_ledger.cash("processor"), 80)

    def test_expired_supply_still_pays_idle_labor_and_has_no_unit_cost(self) -> None:
        ledger = InMemoryCore()
        ledger.endow("processor", 80, memo="opening")
        ledger.open_lot(
            product_id="produce",
            owner="retailer",
            custody="retailer",
            grams=500,
            acquisition_cents=0,
            unsafe_after=50,
            source_kind="opening",
            input_class="rescued",
        )
        result = apply_processing(
            ledger,
            _command(
                purchases=(),
                now=100,
                labor_cents=80,
                transport_cents=40,
                pay_labor_if_idle=True,
            ),
        )
        assert_integers(self, result)
        assert_conserved(self, ledger)
        self.assertEqual(result.expired_grams, 500)
        self.assertEqual(result.accepted_grams, 0)
        self.assertEqual(result.delivered_grams, 0)
        self.assertEqual(result.labor_cents, 80)
        self.assertEqual(result.transport_cents, 0)
        self.assertEqual(result.operating_cents, 80)
        self.assertFalse(result.unit_cost_defined)
        self.assertEqual(ledger.cash("processor"), 0)
        self.assertEqual(ledger.cash("external:labor"), 80)
        self.assertEqual(_grams(ledger, "retailer"), 500)

    def test_added_water_is_mass_and_not_a_free_gram(self) -> None:
        ledger = InMemoryCore()
        ledger.endow("processor", 0, memo="opening")
        ledger.open_lot(
            product_id="produce",
            owner="retailer",
            custody="retailer",
            grams=100,
            acquisition_cents=0,
            unsafe_after=80,
            source_kind="opening",
            input_class="rescued",
        )
        result = apply_processing(
            ledger,
            _command(
                purchases=(),
                edible_num=2,
                edible_den=3,
                added_grams=50,
                labor_cents=0,
                transport_cents=0,
                cold_storage_grams=10_000,
                demand_grams=10_000,
            ),
        )
        assert_conserved(self, ledger)
        self.assertEqual(result.accepted_grams, 100)
        self.assertEqual(result.added_grams, 50)
        self.assertEqual(result.edible_grams, 100)
        self.assertEqual(result.process_loss_grams, 50)
        self.assertEqual(result.delivered_grams, 100)
        self.assertEqual(ledger.conservation().grams_added, 50)


def _holding(ledger: InMemoryCore, owner: str, product: str, input_class: str) -> tuple[int, int]:
    lots = [
        lot
        for lot in ledger.lots()
        if lot.owner == owner and lot.product_id == product and lot.input_class == input_class
    ]
    return sum(lot.grams for lot in lots), sum(lot.acquisition_cents for lot in lots)


def _grams(ledger: InMemoryCore, owner: str) -> int:
    return sum(lot.grams for lot in ledger.lots() if lot.owner == owner)


if __name__ == "__main__":
    unittest.main()
