import unittest

import bootstrap  # noqa: F401

import sim.core as core
from sim.core.catalog import load_catalog, validate_catalog
from sim.core.clock import DayWindow, second_in_day, validate_calendar
EXPECTED_API = (
    "__version__",
    "KERNEL_VERSION",
    "EVENT_SCHEMA_VERSION",
    "CATALOG_SCHEMA_VERSION",
    "SCENARIO_SCHEMA_VERSION",
    "PHASE_POLICY",
    "PHASE_EXPIRY",
    "PHASE_ARRIVAL",
    "PHASE_CHOICE",
    "PHASE_SETTLE",
    "PHASE_CONSUME",
    "ACTOR_KINDS",
    "CAD_CENTS",
    "GRAMS",
    "SIM_SECONDS",
    "METRES",
    "COUNT",
    "METRIC_UNITS",
    "REJECTION_CODES",
    "require_int",
    "require_nonnegative",
    "allocate_largest_remainder",
    "split_mass_by_ratio",
    "Account",
    "FoodLot",
    "Reservation",
    "JournalLine",
    "JournalEntry",
    "FoodMovement",
    "ChoiceRecord",
    "WorldState",
    "Metric",
    "FieldError",
    "InputError",
    "OpenAccount",
    "TransferCash",
    "IntroduceLot",
    "ReserveResources",
    "ReleaseReservation",
    "PurchaseLot",
    "ConsumeFood",
    "TransferLot",
    "ProcessBatch",
    "ApplyExpiry",
    "RecordChoice",
    "Command",
    "EventEnvelope",
    "AccountsSet",
    "LotsSet",
    "ReservationsSet",
    "JournalAppended",
    "MovementsAppended",
    "ChoicesAppended",
    "CommandRecorded",
    "DomainEvent",
    "Transition",
    "Rejection",
    "SequenceError",
    "ConservationError",
    "empty_state",
    "apply_command",
    "apply_commands",
    "fold_events",
    "state_hash",
    "output_hash",
    "canonical_json",
    "sha256_hex",
    "to_jsonable",
    "state_to_json",
    "state_from_json",
    "events_to_json",
    "events_from_json",
    "seeded_admission_order",
    "scene_snapshot",
    "SceneSnapshot",
    "ChoiceOffer",
    "ChoiceReceipt",
    "ChoiceOrigin",
    "FeasibleOption",
    "ObservedFact",
    "account_by_id",
    "account_for_owner",
    "lot_by_id",
    "lots_for_owner",
    "spendable_cents",
    "available_grams",
    "invariant_problems",
    "load_catalog",
    "default_catalog_path",
    "Catalog",
    "Product",
    "Recipe",
    "DayWindow",
    "validate_calendar",
    "second_in_day",
    "funded_discount",
    "cash_before_subsidy",
    "cash_funding_gap",
    "operating_result",
    "paired_difference",
    "run_subsidy_example",
    "SubsidyExample",
    "SubsidyRun",
)


class CatalogAndApiTest(unittest.TestCase):
    def test_public_surface_is_frozen(self) -> None:
        self.assertEqual(core.__all__, EXPECTED_API)
        for name in EXPECTED_API:
            self.assertTrue(hasattr(core, name), name)

    def test_catalog_ids_and_float_refusal(self) -> None:
        catalog = load_catalog()
        self.assertEqual(
            [product.product_id for product in catalog.products],
            [
                "produce.fresh",
                "produce.prepared",
                "staple.rice",
                "protein.beans",
                "dairy.milk",
                "staple.bread",
            ],
        )
        self.assertEqual(len(catalog.sha256), 64)
        self.assertEqual(load_catalog().sha256, catalog.sha256)
        broken = {
            "schema_version": 1,
            "catalog_id": "sim6ix-basket-v1",
            "frozen_on": "2026-10-17",
            "evidence_state": "illustrative",
            "note": "x",
            "products": [],
            "recipes": [],
            "dollars": 1.5,
        }
        errors = validate_catalog(broken)
        self.assertTrue(any("float" in error.message or "dollar" in error.message for error in errors))

    def test_calendar_allows_a_short_local_day(self) -> None:
        days = (
            DayWindow(0, "2026-11-01", 0, 82800),
            DayWindow(1, "2026-11-02", 82800, 86400),
        )
        self.assertEqual(validate_calendar(days), ())
        self.assertEqual(second_in_day(days[0], 82799), 82799)
        overlap = (days[0], DayWindow(1, "2026-11-02", 80000, 86400))
        self.assertTrue(validate_calendar(overlap))


if __name__ == "__main__":
    unittest.main()
