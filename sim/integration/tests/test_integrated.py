"""Integration and defect regressions stated independently of implementation."""
import tempfile
import unittest
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from sim.core import (
    PHASE_ARRIVAL, PHASE_CONSUME, PHASE_SETTLE, ConsumeFood, PurchaseLot,
    ReserveResources, TransferLot, apply_command, available_grams, state_hash,
)
from sim.integration.ledger import KernelLedger
from sim.integration.scenario import DistrictConfig, run_district
from sim.integration.export import export_run, verify_export
from sim.policies.processing import ProcessingCommand, apply_processing


def processing_command():
    return ProcessingCommand("illustrative", "processor", "processor", "processor", 10,
        800, "process", 3, 4, "produce.prepared", 10000, 50, "external:carrier", 0, 1,
        80, "external:labor", False, 0, "produce.fresh", 1000, 1000,
        "school", "school", ("retailer",), ("rescued",), ())


def rescued_stock(ledger):
    return ledger.open_lot(product_id="produce.fresh", owner="retailer", custody="retailer",
        grams=800, acquisition_cents=100, unsafe_after=10000,
        source_kind="opening", input_class="rescued")


class LedgerRegressionTests(unittest.TestCase):
    def test_food_in_transit_cannot_be_bought_reserved_or_consumed(self):
        ledger = KernelLedger()
        ledger.endow("hh", 1000, memo="opening")
        lot_id = rescued_stock(ledger)
        moved = apply_command(ledger.state, TransferLot("depart", 1, PHASE_SETTLE,
            lot_id, 800, "retailer", "school", "trip"))
        lot = next(lot for lot in moved.state.lots if lot.journey_id)
        self.assertEqual(available_grams(lot), 0)
        for command in (
            PurchaseLot("buy", 2, PHASE_SETTLE, "hh", "retailer", "home", lot.lot_id, 800, 100),
            ConsumeFood("eat", 2, PHASE_CONSUME, "retailer", lot.lot_id, 800),
            ReserveResources("hold", 2, PHASE_SETTLE, "hh", "hh", 100, lot.lot_id, 800),
        ):
            result = apply_command(moved.state, command)
            self.assertEqual(result.status, "rejected")
            self.assertIs(result.state, moved.state)
        arrived = apply_command(moved.state, TransferLot("arrive", 2, PHASE_ARRIVAL,
            lot.lot_id, 800, "retailer", "school"))
        self.assertEqual(arrived.status, "accepted")

    def test_unfunded_processing_has_no_output_or_partial_mutation(self):
        ledger = KernelLedger()
        ledger.ensure_account("processor")
        rescued_stock(ledger)
        before, events = state_hash(ledger.state), tuple(ledger.events)
        with self.assertRaisesRegex(ValueError, "fund"):
            ledger.policy(apply_processing, processing_command())
        self.assertEqual(state_hash(ledger.state), before)
        self.assertEqual(tuple(ledger.events), events)

    def test_processing_matches_reference_mechanism_on_real_kernel(self):
        from sim.policies.core_interface import InMemoryCore
        kernel, reference = KernelLedger(), InMemoryCore()
        results = []
        for ledger in (kernel, reference):
            ledger.endow("processor", 1000, memo="opening")
            rescued_stock(ledger)
            if isinstance(ledger, KernelLedger):
                results.append(ledger.policy(apply_processing, processing_command()))
            else:
                results.append(apply_processing(ledger, processing_command()))
            self.assertTrue(ledger.conservation().grams_balanced)
            self.assertEqual(ledger.cash("processor"), 870)
            self.assertEqual(ledger.conservation().grams_waste, 200)
            self.assertEqual(ledger.conservation().writeoff_acquisition_cents, 25)
        self.assertEqual(results[0], results[1])

    def test_malformed_transform_rolls_back_whole_mechanism(self):
        from sim.policies.core_interface.ledger import OutputDraft, LedgerError
        ledger = KernelLedger()
        lot_id = rescued_stock(ledger)
        before = state_hash(ledger.state)
        with self.assertRaises(LedgerError):
            with ledger.atomic():
                ledger.endow("processor", 100, memo="candidate only")
                ledger.replace_lot(lot_id, (OutputDraft(801, 100, "produce.prepared",
                    "processor", "processor", 10000, "opening", "rescued", "stock", "test"),))
        self.assertEqual(state_hash(ledger.state), before)


class BoundaryRegressionTests(unittest.TestCase):
    def test_food_that_expires_during_delivery_is_not_completed(self):
        from sim.logistics.tests.support import direct_order, engine_for, lot, van
        world, core = engine_for([direct_order("order", "hh-1", "food")],
            [lot("food", unsafe_after_second=20)], [van()])
        world.advance_to(1000)
        self.assertEqual(world.orders["order"].status, "failed")
        self.assertIn("unsafe_food", world.orders["order"].reasons)
        self.assertEqual(core.lot("food").owner_id, "hub-owner")
        self.assertIsNone(core.lot("food").reserved_by)

    def test_mismatched_provider_budget_cannot_dispatch(self):
        from sim.behavior.tests.support import panel_of, shopping_context
        from sim.behavior.coordinator import BehaviorConfig, resolve_barrier
        from sim.behavior.budget import MemoryChargeReservation, TokenPrice
        from sim.behavior.errors import BehaviorError
        class BombGateway:
            def dispatch_barrier(self, *args, **kwargs):
                raise AssertionError("provider must not be called")
        config = BehaviorConfig(agent_policy="live_llm", gateway_enabled=True,
            run_budget_cad=Decimal("0.01"), token_price=TokenPrice("illustrative",
                Decimal(1), Decimal(1000), Decimal(1000), Decimal(0)))
        budget = MemoryChargeReservation()
        with self.assertRaisesRegex(BehaviorError, "ceiling"):
            resolve_barrier((shopping_context(opportunity="unfamiliar_store"),),
                config=config, panel=panel_of(("hh-1", "low")), master_seed=1,
                gateway=BombGateway(), budget=budget)
        self.assertEqual(budget.remaining_cad(), Decimal(30))


class ConnectedDistrictTests(unittest.TestCase):
    def test_connected_world_repeats_and_reconciles(self):
        config = DistrictConfig(households=12)
        policies = ("groceries", "processing", "school", "drones")
        first = run_district(17, policies, config)
        again = run_district(17, policies, config)
        self.assertEqual(first.economic_hash, again.economic_hash)
        self.assertEqual(len(first.households), 12)
        self.assertEqual(first.ledger.state.reservations, ())
        self.assertTrue(first.ledger.conservation().grams_balanced)
        ids = {h.household_id for h in first.households}
        paid = sum(-line.cents for entry in first.ledger.state.journal for line in entry.lines
                   if line.account_id in ids and line.cents < 0)
        self.assertEqual(paid, first.outcomes["household_payment_cents"])
        self.assertTrue(any(j["arrive_second"] > j["depart_second"] for j in first.journeys))
        self.assertTrue(all(account.settled_cents >= 0 for account in first.ledger.state.accounts if not account.allows_credit))

    def test_unfunded_new_store_has_no_household_effect(self):
        config = DistrictConfig(households=12, subsidy_cents=0)
        baseline = run_district(17, (), config)
        treatment = run_district(17, ("groceries",), config)
        self.assertEqual(baseline.outcomes, treatment.outcomes)
        self.assertEqual(treatment.policy_results["groceries"]["status"], "planning")

    def test_conditional_route_and_no_approval_have_distinct_events(self):
        config = DistrictConfig(households=12)
        closed = run_district(17, ("school", "drones"), config)
        opened = run_district(17, ("school", "drones"), replace(config, route_eligible=True))
        flights = lambda run: [e for e in run.logistics_state["events"] if e.get("kind") == "DroneFlightStarted" and e.get("leg") == "flight"]
        self.assertFalse(flights(closed))
        self.assertTrue(flights(opened))

    def test_terminal_export_is_immutable_and_detects_corruption(self):
        run = run_district(17, (), DistrictConfig(households=4))
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "run"
            export_run(run, target)
            self.assertEqual(verify_export(target)["economic_hash"], run.economic_hash)
            with self.assertRaises(FileExistsError):
                export_run(run, target)
            (target / "state.json").write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "artifact"):
                verify_export(target)
