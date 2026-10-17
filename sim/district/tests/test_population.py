"""Synthetic households match the frozen margins and school rules."""

import hashlib
import unittest

import bootstrap  # noqa: F401

from sim.district.population import attendance_present, build_population
from sim.district.snapshot import load_snapshot


class PopulationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.snapshot = load_snapshot()
        cls.population = build_population(cls.snapshot.controls, cls.snapshot.places)

    def test_margins_have_zero_residual(self) -> None:
        controls = self.snapshot.controls
        households = self.population.households
        self.assertEqual(len(households), 250)
        self.assertEqual(self.population.population_seed, 17)
        self.assertEqual(self.population.generator_version, "district-pop-1")
        self.assertEqual(
            self.population.population_hash,
            "b3f5209d3ebfb4e1844486339edbc9b2b89a613d28116bedbeb67e0d758061e0",
        )
        for field, attr in (
            ("size", "size"),
            ("income", "income_band"),
            ("tenure", "tenure"),
            ("area", "area_id"),
        ):
            expected = {str(key): count for key, count in controls[field]}
            actual: dict[str, int] = {}
            for household in households:
                label = str(getattr(household, attr))
                actual[label] = actual.get(label, 0) + 1
            self.assertEqual(actual, expected)
            self.assertEqual(sum(expected.values()) - sum(actual.values()), 0)

    def test_roles_and_school_assignment(self) -> None:
        controls = self.snapshot.controls
        areas = {area["area_id"]: area for area in self.snapshot.places["areas"]}
        schools = {school["school_id"]: school for school in self.snapshot.places["schools"]}
        bands = tuple(controls["child_age_bands"])
        school_bands = set(controls["school_age_bands"])
        ordinal = 0
        size2_seen = 0
        for household in self.population.households:
            adults = [member for member in household.members if member.role == "adult"]
            children = [member for member in household.members if member.role == "child"]
            self.assertEqual(len(adults) + len(children), household.size)
            if household.size == 1:
                self.assertEqual((len(adults), len(children)), (1, 0))
            elif household.size == 2:
                if size2_seen < controls["size2_with_child"]:
                    self.assertEqual((len(adults), len(children)), (1, 1))
                else:
                    self.assertEqual((len(adults), len(children)), (2, 0))
                size2_seen += 1
            else:
                self.assertEqual((len(adults), len(children)), (2, household.size - 2))
            for child in children:
                self.assertEqual(child.age_band, bands[ordinal % len(bands)])
                ordinal += 1
            self.assertEqual(household.habitual_store_id, areas[household.area_id]["store_id"])
            self.assertIn(household.diet, {"none", "vegetarian", "dairy_free"})
            self.assertIn(household.mobility, {"walk", "limited"})
        self.assertEqual(size2_seen, 75)
        pupils = self.population.pupils
        self.assertEqual([pupil.member_id for pupil in pupils], list(dict.fromkeys(pupil.member_id for pupil in pupils)))
        school_age = [
            member
            for household in self.population.households
            for member in household.members
            if member.age_band in school_bands
        ]
        self.assertEqual({pupil.member_id for pupil in pupils}, {member.member_id for member in school_age})
        self.assertEqual(len(pupils), 130)
        eligible = 0
        for pupil in pupils:
            household = next(item for item in self.population.households if item.household_id == pupil.household_id)
            school_id = areas[household.area_id]["school_id"]
            school = schools[school_id]
            self.assertEqual(pupil.school_id, school_id)
            self.assertEqual(pupil.eligible, school["program_status"] == "active")
            self.assertNotEqual(pupil.age_band, "0-4")
            eligible += int(pupil.eligible)
        self.assertEqual(eligible, 67)
        self.assertTrue(any(pupil.eligible for pupil in pupils))
        self.assertTrue(any(not pupil.eligible for pupil in pupils))

    def test_attendance_uses_the_population_seed(self) -> None:
        pupil = self.population.pupils[0]
        present = 0
        for day in range(7):
            digest = hashlib.sha256(f"17|{pupil.member_id}|{day}|attendance".encode("utf-8")).digest()
            shown = attendance_present(17, pupil.member_id, day)
            self.assertEqual(shown, digest[0] % 5 != 0)
            self.assertEqual(shown, attendance_present(self.population.population_seed, pupil.member_id, day))
            present += int(shown)
        self.assertNotEqual(present, 0)
        self.assertNotEqual(present, 7)
        total = sum(
            1
            for pupil in self.population.pupils
            for day in range(7)
            if attendance_present(17, pupil.member_id, day)
        )
        self.assertEqual(total, 697)


if __name__ == "__main__":
    unittest.main()
