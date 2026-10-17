import random
import unittest

import bootstrap  # noqa: F401

from sim.core.commands import (
    PHASE_CONSUME,
    PHASE_POLICY,
    PHASE_SETTLE,
    ConsumeFood,
    IntroduceLot,
    OpenAccount,
    PurchaseLot,
    TransferCash,
)
from sim.core.examples import open_fixture_world
from sim.core.kernel import apply_command, empty_state, fold_events, invariant_problems
from sim.core.reporting import cash_before_subsidy, cash_funding_gap, operating_result
from sim.core.units import allocate_largest_remainder, split_mass_by_ratio
from sim.core.catalog import load_catalog


class RoundingTest(unittest.TestCase):
    def test_largest_remainder_tie_breaks_toward_the_smaller_key(self) -> None:
        self.assertEqual(allocate_largest_remainder(100, (("b", 1), ("a", 1), ("c", 1))), {"a": 34, "b": 33, "c": 33})
        self.assertEqual(allocate_largest_remainder(5, (("c", 1), ("a", 1), ("b", 1))), {"a": 2, "b": 2, "c": 1})
        split = allocate_largest_remainder(1, (("take", 1), ("keep", 1)))
        self.assertEqual(split, {"keep": 1, "take": 0})
        self.assertEqual(sum(split.values()), 1)

    def test_mass_remainder_goes_to_the_declared_bucket(self) -> None:
        self.assertEqual(split_mass_by_ratio(1000, 1, 3, "process_loss"), (333, 667))
        self.assertEqual(split_mass_by_ratio(1000, 1, 3, "edible_output"), (334, 666))
        self.assertEqual(split_mass_by_ratio(400, 3, 4, "process_loss"), (300, 100))
        recipe = load_catalog().recipes[0]
        self.assertEqual(
            split_mass_by_ratio(400, recipe.edible_numerator, recipe.edible_denominator, recipe.remainder_to),
            (300, 100),
        )


class ViabilityTest(unittest.TestCase):
    def test_cash_and_operating_views_use_the_documented_arithmetic(self) -> None:
        self.assertEqual(cash_before_subsidy(1000, 400, 100), 500)
        self.assertEqual(cash_funding_gap(800, 200, 500), 100)
        self.assertEqual(cash_funding_gap(100, 200, 500), 0)
        self.assertEqual(cash_funding_gap(100, 0, -50), 150)
        self.assertEqual(
            operating_result(
                sales_revenue=1000,
                operating_subsidy=200,
                cost_of_food_sold=400,
                inventory_writeoffs=50,
                labor=100,
                occupancy=80,
                energy=20,
                logistics=30,
                disposal_charges=10,
                other_overhead=10,
            ),
            500,
        )


class InvariantTest(unittest.TestCase):
    def test_every_fixture_step_balances(self) -> None:
        state = open_fixture_world("conserve-run")
        self.assertEqual(invariant_problems(state), ())
        self.assertEqual(sum(account.settled_cents for account in state.accounts), 0)

    def test_seeded_fuzz_keeps_cash_and_mass(self) -> None:
        catalog = load_catalog()
        state = empty_state(
            run_id="fuzz-run",
            scenario_id="fuzz",
            catalog_id=catalog.catalog_id,
            catalog_sha256=catalog.sha256,
            known_product_ids=tuple(product.product_id for product in catalog.products),
        )
        opening = [
            OpenAccount("ext", 0, PHASE_POLICY, "acct-ext", "external", "external", True),
            OpenAccount("h", 0, PHASE_POLICY, "acct-h", "H", "household", False),
            OpenAccount("r", 0, PHASE_POLICY, "acct-r", "R", "retailer", False),
            TransferCash("fund", 0, PHASE_POLICY, "acct-ext", "acct-h", 5000, "opening_balance"),
            IntroduceLot("lot", 0, PHASE_POLICY, "lot-a", "produce.fresh", "R", "store", 5000, 100, 10_000),
        ]
        for transition in __import__("sim.core", fromlist=["apply_commands"]).apply_commands(state, opening):
            self.assertEqual(transition.status, "accepted")
            state = transition.state
        rng = random.Random(17)
        for index in range(30):
            before = state
            roll = rng.randrange(3)
            if roll == 0:
                command = TransferCash(f"t-{index}", index + 1, PHASE_SETTLE, "acct-h", "acct-r", 100, "transfer")
            elif roll == 1:
                command = PurchaseLot(
                    f"p-{index}",
                    index + 1,
                    PHASE_SETTLE,
                    "acct-h",
                    "acct-r",
                    "home",
                    "lot-a",
                    100,
                    50,
                )
            else:
                owned = [lot for lot in state.lots if lot.owner_id == "H" and lot.grams > 0]
                if not owned:
                    continue
                command = ConsumeFood(f"c-{index}", index + 1, PHASE_CONSUME, "H", owned[0].lot_id, min(50, owned[0].grams))
            result = apply_command(before, command)
            if result.status == "rejected":
                self.assertIs(result.state, before)
            else:
                self.assertEqual(result.status, "accepted")
                self.assertEqual(fold_events(before, result.events), result.state)
            self.assertEqual(invariant_problems(result.state), ())
            state = result.state


if __name__ == "__main__":
    unittest.main()
