"""Drone fallback, a reproducible screen, sensitivity, and subgroup counts."""

import ast
import unittest
from pathlib import Path

import bootstrap  # noqa: F401

from sim.district import load_snapshot
from sim.experiments import (
    all_cells,
    grocery_price_sweep,
    population_subgroups,
    procurement_spoilage_sweep,
    run_drones,
    run_screening,
)

ROOT = Path(__file__).resolve().parents[1]


class DroneTest(unittest.TestCase):
    def test_branches(self) -> None:
        blocked = run_drones("no_approval")
        approved = run_drones("approved")
        failed = run_drones("handoff_failure")
        weather = run_drones("weather_closed")
        air_only = run_drones("no_ground")
        self.assertEqual(blocked.flights, 0)
        self.assertEqual(blocked.ground_completed, 3)
        self.assertEqual(blocked.unserved, 0)
        self.assertEqual(blocked.allocated_cents, 900)
        self.assertEqual(blocked.cost_per_completed_cents, 300)
        self.assertIsNone(blocked.door_to_collection_seconds)
        self.assertEqual(approved.flights, 2)
        self.assertEqual(approved.drone_completed, 2)
        self.assertEqual(approved.ground_completed, 1)
        self.assertEqual(approved.allocated_cents, 1500)
        self.assertEqual(approved.cost_per_completed_cents, 500)
        self.assertEqual(approved.door_to_collection_seconds, 450)
        self.assertEqual(approved.remainder_cents, 0)
        self.assertEqual(failed.handoff_failures, 1)
        self.assertEqual(failed.drone_completed, 1)
        self.assertEqual(failed.ground_completed, 2)
        self.assertEqual(failed.unserved, 0)
        self.assertEqual(failed.allocated_cents, 1800)
        self.assertEqual(failed.cost_per_completed_cents, 600)
        self.assertEqual(weather.flights, 0)
        self.assertEqual(weather.ground_completed, 3)
        self.assertFalse(blocked.eligible)
        self.assertTrue(approved.eligible)
        self.assertEqual(air_only.drone_completed, 2)
        self.assertEqual(air_only.unserved, 1)
        self.assertEqual(air_only.ground_completed, 0)
        self.assertEqual(air_only.cost_per_completed_cents, 600)
        stranded = run_drones("stranded")
        self.assertEqual(stranded.flights, 0)
        self.assertEqual(stranded.unserved, 3)
        self.assertIsNone(stranded.cost_per_completed_cents)
        self.assertEqual(stranded.allocated_cents, 0)


class ScreeningTest(unittest.TestCase):
    def test_report_repeats_and_interaction_cancels_the_shock(self) -> None:
        first = run_screening((17, 18))
        second = run_screening((17, 18))
        self.assertEqual(first.report_hash, second.report_hash)
        self.assertEqual(len(all_cells()), 16)
        self.assertEqual(first.planned_runs, 480)
        self.assertEqual(first.executed_runs, 32)
        self.assertEqual(first.interaction_cents, 30)
        self.assertEqual(first.evidence_state, "illustrative")
        baseline_17 = next(cell for cell in first.cells if cell.seed == 17 and cell.enabled == ())
        baseline_18 = next(cell for cell in first.cells if cell.seed == 18 and cell.enabled == ())
        self.assertNotEqual(baseline_17.household_payment_cents, baseline_18.household_payment_cents)
        both = next(cell for cell in first.cells if cell.seed == 17 and cell.enabled == ("groceries", "school"))
        groceries = next(cell for cell in first.cells if cell.seed == 17 and cell.enabled == ("groceries",))
        school = next(cell for cell in first.cells if cell.seed == 17 and cell.enabled == ("school",))
        self.assertEqual(
            both.household_payment_cents
            - groceries.household_payment_cents
            - school.household_payment_cents
            + baseline_17.household_payment_cents,
            30,
        )


class SensitivityAndSubgroupTest(unittest.TestCase):
    def test_sweeps_move_in_the_declared_direction(self) -> None:
        prices = grocery_price_sweep()
        self.assertEqual(tuple(point.outcome_cents for point in prices), (200, 150, 120))
        spoilage = procurement_spoilage_sweep()
        self.assertEqual(spoilage[0].outcome_cents, 150)
        self.assertEqual(spoilage[1].outcome_cents, 190)

    def test_subgroups_match_the_frozen_population(self) -> None:
        snapshot = load_snapshot()
        report = population_subgroups(snapshot.controls, snapshot.places)
        self.assertEqual(report.household_count, 250)
        self.assertEqual(report.income_counts, (("high", 50), ("low", 100), ("middle", 100)))
        self.assertEqual(sum(count for _school, count in report.eligible_pupils_by_school), 67)
        self.assertEqual(report.ineligible_pupils, 63)
        self.assertGreater(sum(count for _income, mobility, count in report.mobility_by_income if mobility == "walk"), 0)
        self.assertGreater(sum(count for _income, mobility, count in report.mobility_by_income if mobility == "limited"), 0)

    def test_limitations_are_written_down(self) -> None:
        text = (ROOT / "LIMITATIONS.md").read_text(encoding="utf-8")
        for phrase in (
            "illustrative",
            "causal estimate",
            "No Toronto route approval",
            "disabled",
            "480",
            "price_base_month",
        ):
            self.assertIn(phrase, text)


class ExperimentBoundaryTest(unittest.TestCase):
    def test_imports(self) -> None:
        allowed = ("sim.core", "sim.experiments", "sim.policies", "sim.district", "sim.logistics", "sim.behavior")
        for path in ROOT.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    names = [node.module]
                else:
                    continue
                for name in names:
                    if name.startswith("sim.core."):
                        self.fail(name)
                    if any(token in name for token in ("urllib", "socket", "sqlite", "fastapi")):
                        self.fail(name)
                    if name.startswith("sim.") and not any(name == item or name.startswith(item + ".") for item in allowed):
                        self.fail(name)


if __name__ == "__main__":
    unittest.main()
