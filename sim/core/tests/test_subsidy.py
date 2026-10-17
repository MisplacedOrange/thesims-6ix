import json
import unittest
from pathlib import Path

import bootstrap  # noqa: F401

from sim.core.examples import run_subsidy_example
from sim.core.kernel import state_hash
from sim.core.reporting import funded_discount, paired_difference, Metric


class SubsidyExampleTest(unittest.TestCase):
    def test_price_rule_literals(self) -> None:
        self.assertEqual(funded_discount(400, 200, 200), (200, 200))
        self.assertEqual(funded_discount(400, 200, 100), (300, 100))
        self.assertEqual(funded_discount(400, 200, 0), (400, 0))

    def test_baseline_treatment_and_exhausted_budget(self) -> None:
        example = run_subsidy_example()
        again = run_subsidy_example()
        self.assertEqual(state_hash(example.baseline.state), state_hash(again.baseline.state))
        self.assertEqual(state_hash(example.treatment.state), state_hash(again.treatment.state))

        self.assertEqual(example.baseline.household_pays_cents, 400)
        self.assertEqual(example.baseline.subsidy_cents, 0)
        self.assertEqual(example.baseline.unfunded_discount_cents, 200)
        self.assertFalse(example.baseline.budget_exhausted)
        self.assertEqual(_owner_cash(example.baseline.state, "H"), 600)
        self.assertEqual(_owner_cash(example.baseline.state, "M"), 500)
        self.assertEqual(_owner_cash(example.baseline.state, "R"), 400)
        self.assertEqual(_food(example.baseline.state, "H"), 600)

        self.assertEqual(example.treatment.household_pays_cents, 200)
        self.assertEqual(example.treatment.subsidy_cents, 200)
        self.assertEqual(example.treatment.unfunded_discount_cents, 0)
        self.assertTrue(example.treatment.budget_exhausted)
        self.assertEqual(example.treatment.subsidy_budget_remaining_cents, 0)
        self.assertEqual(_owner_cash(example.treatment.state, "H"), 800)
        self.assertEqual(_owner_cash(example.treatment.state, "M"), 300)
        self.assertEqual(_owner_cash(example.treatment.state, "R"), 400)
        self.assertEqual(_food(example.treatment.state, "H"), 600)

        self.assertEqual(example.exhausted.household_pays_cents, 300)
        self.assertEqual(example.exhausted.subsidy_cents, 100)
        self.assertEqual(example.exhausted.unfunded_discount_cents, 100)
        self.assertTrue(example.exhausted.budget_exhausted)
        self.assertEqual(example.exhausted.subsidy_budget_remaining_cents, 0)
        self.assertEqual(_owner_cash(example.exhausted.state, "H"), 700)
        self.assertEqual(_owner_cash(example.exhausted.state, "M"), 400)
        self.assertEqual(_owner_cash(example.exhausted.state, "R"), 400)

        deltas = {metric.name: metric.value for metric in example.treatment_minus_baseline}
        self.assertEqual(deltas["household_food_spend"], -200)
        self.assertEqual(deltas["municipal_subsidy"], 200)
        self.assertEqual(deltas["retailer_cash"], 0)
        self.assertEqual(deltas["household_food"], 0)
        self.assertEqual(deltas["unmet_need"], 0)
        exhausted = {metric.name: metric.value for metric in example.exhausted_minus_baseline}
        self.assertEqual(exhausted["household_food_spend"], -100)
        self.assertEqual(exhausted["municipal_subsidy"], 100)
        self.assertEqual(exhausted["unfunded_discount"], -100)
        self.assertEqual(exhausted["retailer_cash"], 0)
        for run in (example.baseline, example.treatment, example.exhausted):
            self.assertEqual(
                _owner_cash(run.state, "H") + _owner_cash(run.state, "M") + _owner_cash(run.state, "R") + _owner_cash(run.state, "P"),
                1500,
            )
            self.assertEqual(run.state.reservations, ())

    def test_paired_difference_rejects_mixed_units(self) -> None:
        with self.assertRaises(ValueError):
            paired_difference((Metric("cost", 1, "cad_cents"),), (Metric("cost", 1, "grams"),))

    def test_fixture_file_matches_the_planning_catalog(self) -> None:
        root = Path(__file__).resolve().parents[3]
        planning = json.loads((root / "planning" / "scenarios.json").read_text(encoding="utf-8"))
        spec = json.loads((root / "sim" / "core" / "data" / "fixture_scenario.json").read_text(encoding="utf-8"))
        scenarios = {item["id"]: item for item in planning["scenarios"]}
        self.assertEqual(spec["planning_ref"]["scenario_id"], "baseline")
        self.assertEqual(spec["planning_ref"]["mode"], scenarios["baseline"]["mode"])
        self.assertEqual(spec["subsidy_example"]["planning_scenario_id"], "groceries_only")
        self.assertEqual(spec["subsidy_example"]["planning_mode"], scenarios["groceries_only"]["mode"])
        self.assertEqual(spec["opening_cash_cents"], {"acct-H": 1000, "acct-M": 500, "acct-R": 0, "acct-P": 0})
        self.assertEqual(spec["opening_lots"][0]["grams"], 1000)


def _owner_cash(state, owner: str) -> int:
    return next(account.settled_cents for account in state.accounts if account.owner_id == owner)


def _food(state, owner: str) -> int:
    return sum(lot.grams for lot in state.lots if lot.owner_id == owner)


if __name__ == "__main__":
    unittest.main()
