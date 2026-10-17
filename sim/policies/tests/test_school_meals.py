"""School meal fixture.

Capacity is 2 portions. Pupils in admission order are present A, absent B,
present C, allergic D, and ineligible E. The program buys two portions.
Household settlement order is household id, so household:g buys before
household:h.
"""

from __future__ import annotations

import unittest

from sim.policies.core_interface import InMemoryCore
from sim.policies.school_meals import (
    HomePurchasePlan,
    HouseholdNeed,
    Pupil,
    SchoolCommand,
    apply_school_day,
    settle_home_purchases,
)
from sim.policies.tests.support import assert_conserved, assert_integers


def _pupils() -> tuple[Pupil, ...]:
    return (
        Pupil("a", "household:h", True, True, True, True, 0),
        Pupil("b", "household:h", True, True, False, True, 1),
        Pupil("c", "household:g", True, True, True, True, 2),
        Pupil("d", "household:g", True, True, True, False, 3),
        Pupil("e", "household:h", False, True, True, True, 4),
    )


def _command() -> SchoolCommand:
    return SchoolCommand(
        evidence_state="illustrative",
        program_account="program",
        school_owner="school",
        school_custody="kitchen",
        supplier_account="external:supplier",
        product_id="meal",
        food_source="purchase",
        portion_grams=200,
        ingredient_cents_per_portion=80,
        kitchen_capacity=2,
        plate_waste_num=1,
        plate_waste_den=10,
        unsafe_after=1000,
        now=0,
        pupils=_pupils(),
        households=(
            HouseholdNeed("household:h", 300, 1, 2),
            HouseholdNeed("household:g", 200, 0, 1),
        ),
    )


class SchoolMealTests(unittest.TestCase):
    def test_absence_wastes_a_prepared_meal_and_substitution_is_not_program_cost(self) -> None:
        ledger = InMemoryCore()
        ledger.endow("program", 500, memo="opening")
        ledger.endow("household:h", 1000, memo="opening")
        ledger.endow("household:g", 1000, memo="opening")
        ledger.endow("retailer", 0, memo="opening")
        ledger.open_lot(
            product_id="staple",
            owner="retailer",
            custody="retailer",
            grams=1000,
            acquisition_cents=500,
            unsafe_after=1000,
            source_kind="opening",
            input_class="other",
        )
        day = apply_school_day(ledger, _command())
        homes = settle_home_purchases(
            ledger,
            day,
            (
                HomePurchasePlan("household:h", "household:h", "retailer", "retailer", "staple", 1000, "home:h"),
                HomePurchasePlan("household:g", "household:g", "retailer", "retailer", "staple", 1000, "home:g"),
            ),
            now=0,
        )
        assert_integers(self, day)
        assert_integers(self, homes)
        assert_conserved(self, ledger)

        self.assertEqual(day.binding_constraints, ("capacity",))
        self.assertEqual(day.meals_prepared, 2)
        self.assertEqual(day.meals_served, 1)
        self.assertEqual(day.meals_consumed, 1)
        self.assertEqual(day.absence_waste_meals, 1)
        self.assertEqual(day.grams_prepared, 400)
        self.assertEqual(day.grams_consumed, 180)
        self.assertEqual(day.grams_waste, 220)
        self.assertEqual(day.ingredient_cents, 160)
        self.assertEqual(
            [(item.pupil_id, item.outcome, item.consumed_grams, item.waste_grams) for item in day.pupils],
            [
                ("a", "served", 180, 20),
                ("b", "absent", 0, 200),
                ("c", "capacity", 0, 0),
                ("d", "menu_conflict", 0, 0),
                ("e", "ineligible", 0, 0),
            ],
        )
        self.assertEqual(
            [(item.household_id, item.school_consumed_grams, item.replaced_grams) for item in day.households],
            [("household:g", 0, 0), ("household:h", 180, 90)],
        )
        by_id = {item.household_id: item for item in homes}
        self.assertEqual(by_id["household:h"].purchased_grams, 210)
        self.assertEqual(by_id["household:h"].paid_cents, 210)
        self.assertEqual(by_id["household:h"].counterfactual_cents, 300)
        self.assertEqual(by_id["household:h"].cash_savings_cents, 90)
        self.assertEqual(by_id["household:h"].shortfall_grams, 0)
        self.assertEqual(by_id["household:g"].purchased_grams, 200)
        self.assertEqual(by_id["household:g"].paid_cents, 200)
        self.assertEqual(by_id["household:g"].cash_savings_cents, 0)
        self.assertNotEqual(by_id["household:h"].cash_savings_cents, day.ingredient_cents)
        self.assertEqual(ledger.cash("program"), 340)
        self.assertEqual(ledger.cash("external:supplier"), 160)
        self.assertEqual(ledger.cash("household:h"), 790)
        self.assertEqual(ledger.cash("household:g"), 800)
        self.assertEqual(ledger.cash("retailer"), 410)
        self.assertEqual(_holding(ledger, "retailer"), (590, 295))
        self.assertEqual(_grams(ledger, "household:h"), 210)
        self.assertEqual(_grams(ledger, "household:g"), 200)
        self.assertEqual(ledger.conservation().grams_consumed, 180)
        self.assertEqual(ledger.conservation().grams_waste, 220)

    def test_budget_funds_one_meal_and_absence_wastes_it(self) -> None:
        ledger = InMemoryCore()
        ledger.endow("program", 80, memo="opening")
        command = SchoolCommand(
            evidence_state="illustrative",
            program_account="program",
            school_owner="school",
            school_custody="kitchen",
            supplier_account="external:supplier",
            product_id="meal",
            food_source="purchase",
            portion_grams=200,
            ingredient_cents_per_portion=80,
            kitchen_capacity=5,
            plate_waste_num=0,
            plate_waste_den=1,
            unsafe_after=1000,
            now=0,
            pupils=(
                Pupil("a", "household:h", True, True, False, True, 0),
                Pupil("b", "household:h", True, True, True, True, 1),
                Pupil("d", "household:h", True, True, True, False, 2),
            ),
            households=(HouseholdNeed("household:h", 100, 0, 1),),
        )
        day = apply_school_day(ledger, command)
        assert_integers(self, day)
        assert_conserved(self, ledger)
        self.assertEqual(day.binding_constraints, ("budget",))
        self.assertEqual(day.meals_prepared, 1)
        self.assertEqual(day.meals_served, 0)
        self.assertEqual(day.meals_consumed, 0)
        self.assertEqual(day.absence_waste_meals, 1)
        self.assertEqual(day.ingredient_cents, 80)
        self.assertEqual(day.grams_consumed, 0)
        self.assertEqual(day.grams_waste, 200)
        self.assertEqual(day.households[0].replaced_grams, 0)
        self.assertEqual(
            [(item.pupil_id, item.outcome) for item in day.pupils],
            [("a", "absent"), ("b", "budget"), ("d", "menu_conflict")],
        )
        self.assertEqual(ledger.cash("program"), 0)
        self.assertEqual(ledger.cash("external:supplier"), 80)
        self.assertEqual(ledger.conservation().grams_waste, 200)
        self.assertEqual(ledger.conservation().grams_consumed, 0)


def _grams(ledger: InMemoryCore, owner: str) -> int:
    return sum(lot.grams for lot in ledger.lots() if lot.owner == owner)


def _holding(ledger: InMemoryCore, owner: str) -> tuple[int, int]:
    lots = [lot for lot in ledger.lots() if lot.owner == owner]
    return sum(lot.grams for lot in lots), sum(lot.acquisition_cents for lot in lots)


if __name__ == "__main__":
    unittest.main()
