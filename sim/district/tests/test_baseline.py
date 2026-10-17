"""250-household baseline: conservation, reconciliation, and a repeated seed."""

import unittest

import bootstrap  # noqa: F401

from sim.core import empty_state, fold_events, lots_for_owner, state_hash
from sim.district.baseline import run_baseline
from sim.district.network import shortest_path
from sim.district.snapshot import load_snapshot


class BaselineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = run_baseline(17)

    def test_quality_report_completes(self) -> None:
        report = self.result.report
        self.assertTrue(report.completion)
        self.assertTrue(all(check.passed for check in report.checks))
        self.assertEqual(report.household_count, 250)
        self.assertEqual(report.pupil_count, 130)
        self.assertEqual(report.eligible_pupil_count, 67)
        self.assertEqual(report.present_pupil_days, 697)
        self.assertEqual(report.choice_count, 1750)
        self.assertEqual(report.purchase_count, 1672)
        self.assertEqual(report.rejection_count, 0)
        self.assertEqual(report.household_food_spend_cents, 783180)
        self.assertEqual(report.grams_purchased, 1486000)
        self.assertEqual(report.grams_consumed, 1486000)
        self.assertEqual(report.grams_unmet, 124000)
        self.assertEqual(report.total_need_grams, 1610000)
        self.assertEqual(report.municipal_spend_cents, 0)
        self.assertEqual(report.event_count, 26520)
        self.assertEqual(report.population_hash, "b3f5209d3ebfb4e1844486339edbc9b2b89a613d28116bedbeb67e0d758061e0")
        self.assertEqual(report.state_hash, "067e50d1212faa3cdc01e56a3c38cca22b3208b152e4ba51ddc670fe5286ba81")
        self.assertEqual(report.scene_hash, report.state_hash)
        self.assertEqual(report.kernel_version, "0.1.0")

    def test_spend_stock_and_travel_match_the_ledger(self) -> None:
        state = self.result.state
        trips = self.result.trips
        journal_spend = sum(
            -line.cents
            for entry in state.journal
            for line in entry.lines
            if line.memo.startswith("purchase:") and line.cents < 0
        )
        moved = sum(
            movement.grams
            for movement in state.movements
            if movement.kind == "transfer" and movement.to_owner_id is not None and movement.to_owner_id.startswith("hh-")
        )
        self.assertEqual(journal_spend, sum(trip.payment_cents for trip in trips))
        self.assertEqual(moved, sum(trip.grams for trip in trips))
        self.assertEqual(journal_spend, self.result.report.household_food_spend_cents)
        self.assertEqual(state.imported_grams, state.consumed_grams + sum(lot.grams for lot in state.lots))
        self.assertEqual(state.loss_grams, 0)
        households = {household.household_id: household for household in self.result.population.households}
        snapshot = load_snapshot()
        price = {store["store_id"]: store["price_cents_per_100g"] for store in snapshot.places["stores"]}
        for trip in trips:
            household = households[trip.household_id]
            found = shortest_path(snapshot.network, household.area_id, trip.store_id or "")
            self.assertIsNotNone(found)
            assert found is not None
            multiplier = snapshot.behavior["mobility_multiplier"][household.mobility]
            self.assertEqual(trip.travel_seconds, (household.access_seconds + found[1]) * multiplier)
            self.assertEqual(trip.payment_cents * 100, trip.grams * price[trip.store_id or ""])
        member_ids = {member.member_id for household in self.result.population.households for member in household.members}
        owners = {account.owner_id for account in state.accounts}
        self.assertTrue(member_ids.isdisjoint(owners))
        self.assertEqual(lots_for_owner(state, "store-municipal"), ())
        municipal = next(account for account in state.accounts if account.owner_id == "muni")
        self.assertEqual(municipal.settled_cents, 0)
        for account in state.accounts:
            if account.kind == "school":
                self.assertEqual(account.settled_cents, 0)
        self.assertEqual(state.reservations, ())

    def test_replay_and_repeated_seed(self) -> None:
        state = self.result.state
        replayed = fold_events(
            empty_state(
                run_id=state.run_id,
                scenario_id=state.scenario_id,
                catalog_id=state.catalog_id,
                catalog_sha256=state.catalog_sha256,
                known_product_ids=state.known_product_ids,
            ),
            self.result.events,
        )
        self.assertEqual(state_hash(replayed), self.result.report.state_hash)
        again = run_baseline(17)
        self.assertEqual(again.report.state_hash, self.result.report.state_hash)
        self.assertEqual(again.trips, self.result.trips)
        other = run_baseline(18)
        self.assertEqual(other.population.population_hash, self.result.population.population_hash)
        self.assertNotEqual(other.trips, self.result.trips)
        self.assertNotEqual(other.report.state_hash, self.result.report.state_hash)


if __name__ == "__main__":
    unittest.main()
