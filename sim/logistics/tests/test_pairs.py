"""Paired runs subtract only when population, baseline, and units match."""

from __future__ import annotations

import unittest
from dataclasses import replace

from sim.logistics.compatibility import CompatibilityError, delta_by_name, paired_difference
from sim.logistics.tests.support import (
    context,
    corridor,
    direct_order,
    drone,
    drone_order,
    engine_for,
    fleet,
    lot,
    van,
)


def _ground():
    world, _core = engine_for(
        [direct_order("o-1", "hh-1", "lot-1")],
        [lot("lot-1")],
        [van()],
        fleet_config=fleet(),
        scenario=context(),
    )
    world.advance_to(10_000)
    return world.outcome()


def _drone():
    order = drone_order(
        "o-1",
        "hh-1",
        "lot-1",
        allow_ground_fallback=False,
        handoff="collect",
        pickup_window_seconds=100,
    )
    world, _core = engine_for(
        [order],
        [lot("lot-1")],
        [drone()],
        corridors=[corridor()],
        scenario=context(),
    )
    world.advance_to(10_000)
    return world.outcome()


class PairedRunTests(unittest.TestCase):
    def test_matching_runs_subtract_in_original_units(self) -> None:
        baseline = _ground()
        treatment = _drone()
        difference = paired_difference(baseline, treatment)
        # Ground collection is 55 s and costs 1,220 cents.
        # Drone collection is 70 s and costs 1,850 cents.
        self.assertEqual(delta_by_name(difference, "completed_orders").difference, 0)
        self.assertEqual(delta_by_name(difference, "completed_orders").unit, "orders")
        self.assertEqual(delta_by_name(difference, "completed_door_to_collection_seconds").difference, 15)
        self.assertEqual(delta_by_name(difference, "completed_door_to_collection_seconds").unit, "seconds")
        self.assertEqual(delta_by_name(difference, "allocated_operating_cost_cents").difference, 630)
        self.assertEqual(delta_by_name(difference, "allocated_operating_cost_cents").unit, "cents")
        self.assertEqual(delta_by_name(difference, "drone_completed_orders").difference, 1)
        self.assertEqual(delta_by_name(difference, "ground_completed_orders").difference, -1)
        cost = next(item for item in difference.ratios if item.name == "cost_per_completed_order")
        self.assertTrue(cost.defined)
        self.assertEqual(cost.difference_numerator, 630)
        self.assertEqual(cost.difference_denominator, 1)
        self.assertEqual(cost.numerator_unit, "cents")

    def test_identical_runs_have_zero_differences(self) -> None:
        difference = paired_difference(_ground(), _ground())
        for item in difference.metrics:
            self.assertEqual(item.difference, 0, item.name)
        for item in difference.ratios:
            self.assertTrue(item.defined)
            self.assertEqual(item.difference_numerator, 0)

    def test_population_baseline_and_units_are_rejected(self) -> None:
        baseline = _ground()
        other_population = replace(
            baseline,
            fingerprint=replace(baseline.fingerprint, population_ids=("hh-9",)),
        )
        with self.assertRaises(CompatibilityError) as population:
            paired_difference(baseline, other_population)
        self.assertIn("population", population.exception.reasons)

        other_baseline = replace(
            baseline,
            fingerprint=replace(baseline.fingerprint, baseline_id="some-other-baseline"),
        )
        with self.assertRaises(CompatibilityError) as baseline_error:
            paired_difference(baseline, other_baseline)
        self.assertIn("baseline", baseline_error.exception.reasons)

        forged_quantities = tuple(
            replace(item, unit="minutes") if item.name == "completed_door_to_collection_seconds" else item
            for item in baseline.metrics.quantities
        )
        mixed_units = replace(
            baseline,
            metrics=replace(baseline.metrics, quantities=forged_quantities),
        )
        with self.assertRaises(CompatibilityError) as units:
            paired_difference(baseline, mixed_units)
        self.assertIn("units", units.exception.reasons)

    def test_an_undefined_ratio_is_not_treated_as_zero(self) -> None:
        # A failed drone with no completed order has a cost and an undefined ratio.
        order = drone_order(
            "o-1",
            "hh-1",
            "lot-1",
            allow_ground_fallback=False,
            handoff="miss",
            pickup_window_seconds=10,
        )
        failed, _core = engine_for(
            [order],
            [lot("lot-1")],
            [drone(energy_per_metre=0, energy_capacity=0, energy_remaining=0, reserve_energy=0, charge_per_second=0)],
            corridors=[corridor()],
        )
        failed.advance_to(10_000)
        difference = paired_difference(_ground(), failed.outcome())
        ratio = next(item for item in difference.ratios if item.name == "cost_per_completed_order")
        self.assertFalse(ratio.defined)
        self.assertEqual(ratio.difference_denominator, 0)
        self.assertEqual(delta_by_name(difference, "allocated_operating_cost_cents").treatment, 1_870)
        self.assertEqual(delta_by_name(difference, "completed_orders").treatment, 0)


if __name__ == "__main__":
    unittest.main()
