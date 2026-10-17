import unittest

import bootstrap  # noqa: F401

from sim.core.commands import PHASE_SETTLE, PurchaseLot
from sim.core.examples import open_fixture_world
from sim.core.kernel import (
    SequenceError,
    apply_command,
    events_from_json,
    events_to_json,
    fold_events,
    output_hash,
    scene_snapshot,
    seeded_admission_order,
    state_from_json,
    state_hash,
    state_to_json,
)


def _purchase(command_id: str = "buy") -> PurchaseLot:
    return PurchaseLot(command_id, 2, PHASE_SETTLE, "acct-H", "acct-R", "home-H", "lot-produce-open", 600, 400)


class DeterminismTest(unittest.TestCase):
    def test_same_inputs_have_the_same_output_hash(self) -> None:
        first = apply_command(open_fixture_world("same-run"), _purchase())
        second = apply_command(open_fixture_world("same-run"), _purchase())
        self.assertEqual(output_hash(first.state, first.events), output_hash(second.state, second.events))
        self.assertEqual(state_hash(first.state), state_hash(second.state))
        changed = apply_command(open_fixture_world("same-run"), PurchaseLot("buy", 2, PHASE_SETTLE, "acct-H", "acct-R", "home-H", "lot-produce-open", 600, 401))
        self.assertNotEqual(state_hash(changed.state), state_hash(first.state))

    def test_crash_discards_the_candidate_and_a_duplicate_does_not_resettle(self) -> None:
        state = open_fixture_world("crash-run")
        candidate = apply_command(state, _purchase())
        self.assertEqual(candidate.status, "accepted")
        restored = state_from_json(state_to_json(state))
        self.assertEqual(state_hash(restored), state_hash(state))
        self.assertEqual(restored, state)
        committed = candidate.state
        duplicate = apply_command(committed, _purchase())
        self.assertEqual(duplicate.status, "duplicate")
        self.assertEqual(duplicate.events, ())
        self.assertEqual(state_hash(duplicate.state), state_hash(committed))
        buyer = next(account.settled_cents for account in duplicate.state.accounts if account.owner_id == "H")
        self.assertEqual(buyer, 600)
        replayed = fold_events(state, candidate.events)
        self.assertEqual(replayed, committed)
        with self.assertRaises(SequenceError):
            fold_events(committed, candidate.events)

    def test_event_json_round_trip_replays(self) -> None:
        state = open_fixture_world("json-run")
        transition = apply_command(state, _purchase())
        restored_events = events_from_json(events_to_json(transition.events))
        self.assertEqual(restored_events, transition.events)
        self.assertEqual(fold_events(state, restored_events), transition.state)
        self.assertEqual(scene_snapshot(transition.state).state_hash, state_hash(transition.state))

    def test_admission_order_is_stable_and_not_actor_id_order(self) -> None:
        actors = ["H1", "H2", "H3", "H4"]
        self.assertEqual(
            seeded_admission_order(17, "shop-1", actors),
            seeded_admission_order(17, "shop-1", list(reversed(actors))),
        )
        differed = False
        for seed in range(30):
            if seeded_admission_order(seed, "shop-1", actors) != tuple(sorted(actors)):
                differed = True
                break
        self.assertTrue(differed)


if __name__ == "__main__":
    unittest.main()
