"""Knowledge limits, legal offers, a disabled gateway, and the focal panel."""

import ast
import unittest
from pathlib import Path

import bootstrap  # noqa: F401

from sim.core import (
    PHASE_POLICY,
    ChoiceReceipt,
    OpenAccount,
    TransferCash,
    empty_state,
    load_catalog,
)
from sim.behavior import (
    Candidate,
    build_offer,
    by_income,
    decide,
    known_facts,
    leaks_other_balance,
    legal_candidates,
    live_barrier,
    select_panel,
    summarize,
)
from sim.behavior.compare import ChoiceRow
from sim.core import apply_command

ROOT = Path(__file__).resolve().parents[1]
BANNED = ("urllib", "socket", "http.client", "openai", "requests")


def _state():
    catalog = load_catalog()
    state = empty_state(
        run_id="behavior",
        scenario_id="baseline",
        catalog_id=catalog.catalog_id,
        catalog_sha256=catalog.sha256,
        known_product_ids=tuple(product.product_id for product in catalog.products),
    )
    commands = [
        OpenAccount("ext", 0, PHASE_POLICY, "acct-ext", "ext", "external", True),
        OpenAccount("a", 0, PHASE_POLICY, "acct-a", "hh-a", "household", False),
        OpenAccount("b", 0, PHASE_POLICY, "acct-b", "hh-b", "household", False),
        TransferCash("cash-a", 0, PHASE_POLICY, "acct-ext", "acct-a", 100, "opening_balance"),
        TransferCash("cash-b", 0, PHASE_POLICY, "acct-ext", "acct-b", 999, "opening_balance"),
    ]
    for command in commands:
        state = apply_command(state, command).state
    return state


def _offer(candidates):
    facts = known_facts(_state(), "hh-a", (("store-near", 50), ("store-far", 200)))
    return build_offer("dec-a", "hh-a", 3, facts, candidates), facts


class KnowledgeAndOfferTest(unittest.TestCase):
    def test_neighbor_cash_is_not_a_fact(self) -> None:
        facts = known_facts(_state(), "hh-a", (("store-near", 50),))
        self.assertEqual(facts[1].value, "100")
        self.assertFalse(leaks_other_balance(facts, "hh-b", 999))

    def test_unaffordable_basket_is_omitted(self) -> None:
        candidates = legal_candidates(
            (
                Candidate("store:near", 50, 100, 10),
                Candidate("store:far", 200, 100, 40),
            ),
            100,
        )
        self.assertEqual(tuple(item.option_id for item in candidates), ("store:near", "no-purchase"))
        offer, _facts = _offer(candidates)
        self.assertEqual(tuple(option.option_id for option in offer.options), ("no-purchase", "store:near"))

    def test_higher_score_wins_a_tie_breaks_by_id(self) -> None:
        from sim.behavior import rule_choice

        chosen = rule_choice((Candidate("store:b", 50, 100, 5), Candidate("store:a", 50, 100, 5)))
        self.assertEqual(chosen.option_id, "store:a")
        preferred = rule_choice((Candidate("store:a", 50, 100, 5), Candidate("store:b", 40, 100, 9)))
        self.assertEqual(preferred.option_id, "store:b")


class FallbackTest(unittest.TestCase):
    def setUp(self) -> None:
        self.candidates = legal_candidates((Candidate("store:near", 50, 100, 10),), 100)
        self.offer, _facts = _offer(self.candidates)
        self.affordable = frozenset(option.option_id for option in self.offer.options)

    def test_disabled_gateway_uses_the_rule(self) -> None:
        resolved = decide(
            self.offer,
            self.candidates,
            None,
            gateway_enabled=False,
            selected_for_live=True,
            late=False,
            affordable_option_ids=self.affordable,
        )
        self.assertEqual(resolved.reason, "gateway_disabled")
        self.assertEqual(resolved.receipt.origin, "rule")
        self.assertEqual(resolved.receipt.option_id, "store:near")

    def test_bad_receipts_fall_back(self) -> None:
        cases = {
            "missing": None,
            "invalid_option": ChoiceReceipt(self.offer.decision_id, "store:missing", "llm", "a" * 64, None),
            "refused": ChoiceReceipt(self.offer.decision_id, "refused", "llm", self.offer.decision_id, None),
            "unaffordable": None,
        }
        missing = decide(
            self.offer,
            self.candidates,
            cases["missing"],
            gateway_enabled=True,
            selected_for_live=True,
            late=False,
            affordable_option_ids=self.affordable,
        )
        invalid = decide(
            self.offer,
            self.candidates,
            cases["invalid_option"],
            gateway_enabled=True,
            selected_for_live=True,
            late=False,
            affordable_option_ids=self.affordable,
        )
        refused = decide(
            self.offer,
            self.candidates,
            ChoiceReceipt(self.offer.decision_id, "refused", "llm", "b" * 64, None),
            gateway_enabled=True,
            selected_for_live=True,
            late=False,
            affordable_option_ids=self.affordable,
        )
        late = decide(
            self.offer,
            self.candidates,
            ChoiceReceipt(self.offer.decision_id, "store:near", "llm", "c" * 64, None),
            gateway_enabled=True,
            selected_for_live=True,
            late=True,
            affordable_option_ids=self.affordable,
        )
        stale = decide(
            self.offer,
            self.candidates,
            ChoiceReceipt(self.offer.decision_id, "store:near", "recorded", "d" * 64, None),
            gateway_enabled=True,
            selected_for_live=True,
            late=False,
            affordable_option_ids=self.affordable,
        )
        poor = decide(
            self.offer,
            self.candidates,
            ChoiceReceipt(self.offer.decision_id, "store:near", "llm", stale.receipt.observation_hash, None),
            gateway_enabled=True,
            selected_for_live=True,
            late=False,
            affordable_option_ids=frozenset({"no-purchase"}),
        )
        self.assertEqual(missing.reason, "missing")
        self.assertEqual(invalid.reason, "invalid_option")
        self.assertEqual(refused.reason, "refused")
        self.assertEqual(late.reason, "late")
        self.assertEqual(stale.reason, "stale_revision")
        self.assertEqual(poor.reason, "unaffordable")
        for resolved in (missing, invalid, refused, late, stale, poor):
            self.assertEqual(resolved.receipt.origin, "fallback")
            self.assertEqual(resolved.receipt.option_id, "store:near")

    def test_a_fresh_recorded_receipt_is_kept(self) -> None:
        digest = decide(
            self.offer,
            self.candidates,
            None,
            gateway_enabled=False,
            selected_for_live=False,
            late=False,
            affordable_option_ids=self.affordable,
        ).receipt.observation_hash
        kept = decide(
            self.offer,
            self.candidates,
            ChoiceReceipt(self.offer.decision_id, "no-purchase", "recorded", digest, "frozen"),
            gateway_enabled=True,
            selected_for_live=True,
            late=False,
            affordable_option_ids=self.affordable,
        )
        self.assertEqual(kept.reason, "accepted")
        self.assertEqual(kept.receipt.origin, "recorded")
        self.assertEqual(kept.receipt.option_id, "no-purchase")

    def test_outside_the_barrier_is_not_a_timeout(self) -> None:
        resolved = decide(
            self.offer,
            self.candidates,
            None,
            gateway_enabled=True,
            selected_for_live=False,
            late=True,
            affordable_option_ids=self.affordable,
        )
        self.assertEqual(resolved.reason, "not_selected_for_live_barrier")
        self.assertEqual(resolved.receipt.origin, "rule")


class PanelTest(unittest.TestCase):
    def test_panel_and_barrier(self) -> None:
        rows = tuple((f"hh-{band}-{index}", band) for band in ("high", "low", "middle") for index in range(3))
        panel = select_panel(rows, 4, 17)
        self.assertEqual(panel, select_panel(rows, 4, 17))
        self.assertEqual(len(panel), 4)
        counts = {"high": 0, "low": 0, "middle": 0}
        for household_id in panel:
            counts[household_id.split("-")[1]] += 1
        self.assertEqual(counts, {"high": 2, "low": 1, "middle": 1})
        seated = ("hh-0", "hh-1", "hh-2", "hh-3", "hh-4", "hh-5")
        day0 = live_barrier(seated, 0, 4)
        day1 = live_barrier(seated, 1, 4)
        self.assertEqual(day0, ("hh-0", "hh-1", "hh-2", "hh-3"))
        self.assertEqual(day1, ("hh-4", "hh-5", "hh-0", "hh-1"))
        skipped = [household for household in seated if household not in day0]
        self.assertEqual(skipped, ["hh-4", "hh-5"])

    def test_summary_separates_origins(self) -> None:
        rows = (
            ChoiceRow("hh-1", "low", "rule", "gateway_disabled", "store:near"),
            ChoiceRow("hh-2", "low", "fallback", "late", "store:near"),
            ChoiceRow("hh-3", "high", "recorded", "accepted", "no-purchase"),
            ChoiceRow("hh-4", "high", "rule", "not_selected_for_live_barrier", "store:near"),
        )
        totals = {metric.name: metric.value for metric in summarize(rows)}
        self.assertEqual(totals, {"rule_choices": 2, "fallback_choices": 1, "recorded_choices": 1, "llm_choices": 0, "not_selected": 1})
        self.assertEqual(len(by_income(rows, "low")), 2)


class BehaviorBoundaryTest(unittest.TestCase):
    def test_no_provider_client(self) -> None:
        for path in ROOT.glob("*.py"):
            text = path.read_text(encoding="utf-8")
            tree = ast.parse(text)
            for banned in BANNED:
                self.assertNotIn(banned, text)
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
                    if name.startswith("sim.") and not name.startswith("sim.behavior") and name != "sim.core":
                        self.fail(name)


if __name__ == "__main__":
    unittest.main()
