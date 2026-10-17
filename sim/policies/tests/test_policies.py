"""Literal mechanism results. Expected cents and grams are the fixture, not a second formula."""

import ast
import unittest
from pathlib import Path

import bootstrap  # noqa: F401

from sim.core import invariant_problems, paired_difference
from sim.policies import run_municipal_grocery, run_processing, run_procurement, run_school_day

ROOT = Path(__file__).resolve().parents[1]


class GroceryTest(unittest.TestCase):
    def test_closed_store_spends_nothing(self) -> None:
        result = run_municipal_grocery("closed")
        self.assertEqual(invariant_problems(result.state), ())
        self.assertEqual(result.household_payment_cents, 200)
        self.assertEqual(result.price_subsidy_cents, 0)
        self.assertEqual(result.operating_subsidy_cents, 0)
        self.assertEqual(result.fiscal_outlay_cents, 0)
        self.assertEqual(result.resource_cash_cents, 0)
        self.assertEqual(result.household_grams, 400)
        self.assertEqual(result.store_grams, 0)
        self.assertEqual(sum(lot.grams for lot in result.state.lots), 1000)

    def test_full_subsidy_is_a_transfer(self) -> None:
        result = run_municipal_grocery("open_full")
        self.assertEqual(invariant_problems(result.state), ())
        self.assertEqual(result.household_payment_cents, 120)
        self.assertEqual(result.price_subsidy_cents, 80)
        self.assertEqual(result.operating_subsidy_cents, 500)
        self.assertEqual(result.fiscal_outlay_cents, 580)
        self.assertEqual(result.resource_cash_cents, 480)
        self.assertNotEqual(result.fiscal_outlay_cents, result.resource_cash_cents)
        self.assertEqual(result.cogs_cents, 120)
        self.assertEqual(result.cash_before_subsidy_cents, -360)
        self.assertEqual(result.cash_funding_gap_cents, 360)
        self.assertEqual(result.operating_result_cents, 400)
        self.assertEqual(result.household_grams, 400)
        self.assertEqual(result.store_grams, 600)
        municipal = next(account.settled_cents for account in result.state.accounts if account.owner_id == "store-m")
        self.assertEqual(municipal, 220)

    def test_exhausted_budget_leaves_part_of_the_discount_unfunded(self) -> None:
        result = run_municipal_grocery("open_exhausted")
        self.assertEqual(result.household_payment_cents, 150)
        self.assertEqual(result.price_subsidy_cents, 50)
        self.assertEqual(result.fiscal_outlay_cents, 550)
        self.assertEqual(result.household_grams, 400)

    def test_paired_difference_uses_the_same_units(self) -> None:
        closed = run_municipal_grocery("closed")
        opened = run_municipal_grocery("open_full")
        delta = paired_difference(closed.metrics, opened.metrics)
        self.assertEqual(delta[0].value, -80)
        self.assertEqual(delta[0].unit, "cad_cents")
        self.assertEqual(delta[3].value, 0)


class ProcessingTest(unittest.TestCase):
    def test_rescue_uses_the_shift_and_leaves_purchased_food(self) -> None:
        result = run_processing(rescue_eligible=True)
        self.assertEqual(invariant_problems(result.state), ())
        self.assertEqual(result.rescued_input_grams, 400)
        self.assertEqual(result.purchased_input_grams, 0)
        self.assertEqual(result.purchased_grams_remaining, 400)
        self.assertEqual(result.edible_grams, 300)
        self.assertEqual(result.process_loss_grams, 100)
        self.assertEqual(result.waste_grams, 0)
        self.assertEqual(result.labor_cents, 100)
        self.assertEqual(result.purchased_food_cents, 120)
        self.assertEqual(result.fiscal_transfer_cents, 220)
        prepared = next(lot for lot in result.state.lots if lot.product_id == "produce.prepared")
        self.assertEqual(prepared.acquisition_cents, 0)

    def test_unsafe_rescue_is_wasted_and_purchased_food_is_processed(self) -> None:
        result = run_processing(rescue_eligible=False)
        self.assertEqual(invariant_problems(result.state), ())
        self.assertEqual(result.waste_grams, 400)
        self.assertEqual(result.purchased_input_grams, 400)
        self.assertEqual(result.purchased_grams_remaining, 0)
        self.assertEqual(result.edible_grams, 300)
        self.assertEqual(result.process_loss_grams, 100)
        prepared = next(lot for lot in result.state.lots if lot.product_id == "produce.prepared")
        recognized = sum(
            movement.acquisition_cents_recognized
            for movement in result.state.movements
            if movement.kind == "process_loss"
        )
        self.assertEqual(prepared.acquisition_cents, 90)
        self.assertEqual(recognized, 30)
        self.assertEqual(prepared.acquisition_cents + recognized, 120)


class MealTest(unittest.TestCase):
    def test_one_present_pupil_is_served(self) -> None:
        result = run_school_day(substitution_grams=0)
        self.assertEqual(invariant_problems(result.state), ())
        self.assertEqual((result.meals_prepared, result.meals_served, result.meals_consumed), (1, 1, 1))
        self.assertEqual(result.waste_grams, 50)
        self.assertEqual(result.school_cost_cents, 115)
        self.assertEqual(result.household_purchase_grams, 400)
        self.assertEqual(result.household_payment_cents, 200)
        self.assertNotEqual(result.school_cost_cents, result.household_payment_cents - 200)
        options = {choice.household_id: choice.option_id for choice in result.state.choices}
        self.assertEqual(options, {"hh-a": "meal:served", "hh-b": "meal:absent", "hh-c": "meal:ineligible"})
        self.assertEqual(sum(lot.grams for lot in result.state.lots if lot.owner_id == "school-a"), 0)

    def test_substitution_reduces_home_grams_only(self) -> None:
        baseline = run_school_day(substitution_grams=0)
        replaced = run_school_day(substitution_grams=100)
        self.assertEqual(replaced.household_purchase_grams, 300)
        self.assertEqual(replaced.household_payment_cents, 150)
        self.assertEqual(replaced.school_cost_cents, baseline.school_cost_cents)
        self.assertEqual(replaced.school_cost_cents, 115)
        self.assertEqual(baseline.household_payment_cents - replaced.household_payment_cents, 50)

    def test_no_kitchen_capacity_serves_nobody(self) -> None:
        result = run_school_day(substitution_grams=100, kitchen_capacity_grams=0)
        self.assertEqual(result.meals_consumed, 0)
        self.assertEqual(result.household_purchase_grams, 400)
        self.assertEqual(result.waste_grams, 250)
        self.assertEqual(result.school_cost_cents, 115)


class ProcurementTest(unittest.TestCase):
    def test_equal_meals_and_both_cost_directions(self) -> None:
        direct = run_procurement("decentralized")
        pooled = run_procurement("pooled")
        spoiled = run_procurement("pooled", spoilage_grams=100)
        self.assertEqual(invariant_problems(direct.state), ())
        self.assertEqual(invariant_problems(pooled.state), ())
        self.assertEqual(invariant_problems(spoiled.state), ())
        self.assertEqual(direct.served_grams, 400)
        self.assertEqual(pooled.served_grams, 400)
        self.assertEqual(spoiled.served_grams, 400)
        self.assertEqual(direct.delivered_cost_cents, 160)
        self.assertEqual(pooled.delivered_cost_cents, 150)
        self.assertEqual(spoiled.delivered_cost_cents, 190)
        self.assertEqual(spoiled.waste_grams, 100)
        self.assertLess(pooled.delivered_cost_cents, direct.delivered_cost_cents)
        self.assertGreater(spoiled.delivered_cost_cents, direct.delivered_cost_cents)


class PolicyBoundaryTest(unittest.TestCase):
    def test_imports_use_the_public_kernel(self) -> None:
        for path in ROOT.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                module = None
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    names = [node.module or ""]
                else:
                    continue
                for module in names:
                    if module.startswith("sim.core."):
                        self.fail(module)
                    if module.startswith("sim.") and not module.startswith("sim.policies") and module != "sim.core":
                        self.fail(module)


if __name__ == "__main__":
    unittest.main()
