"""Hand-scored baskets. Noise is zero in these literals."""

import unittest

import bootstrap  # noqa: F401

from sim.district.shopping import ScoredOption, choose, score_option


def _score(price_sensitivity: int, payment: int, travel: int, habit: bool, quality: int) -> int:
    return score_option(
        grams=500,
        payment_cents=payment,
        travel_seconds=travel,
        habit=habit,
        quality=quality,
        preference=20,
        nutrition_per_gram=2,
        price_sensitivity_per_dollar=price_sensitivity,
        time_sensitivity_per_minute=10,
        habit_score=80,
        noise=0,
    )


class ShoppingScoreTest(unittest.TestCase):
    def test_low_sensitivity_prefers_the_far_store(self) -> None:
        local = _score(200, 300, 150, True, 10)
        far = _score(200, 200, 540, False, 5)
        self.assertEqual(local, 485)
        self.assertEqual(far, 535)
        chosen = choose(
            (
                ScoredOption("store:local", "local", "lot", 500, 300, 150, local),
                ScoredOption("store:far", "far", "lot", 500, 200, 540, far),
                ScoredOption("no-purchase", None, None, 0, 0, 0, 0),
            )
        )
        self.assertEqual(chosen.option_id, "store:far")

    def test_high_sensitivity_prefers_the_habitual_store(self) -> None:
        local = _score(50, 300, 150, True, 10)
        far = _score(50, 200, 540, False, 5)
        self.assertEqual(local, 935)
        self.assertEqual(far, 835)
        chosen = choose(
            (
                ScoredOption("store:far", "far", "lot", 500, 200, 540, far),
                ScoredOption("store:local", "local", "lot", 500, 300, 150, local),
            )
        )
        self.assertEqual(chosen.option_id, "store:local")

    def test_tied_scores_break_to_the_smaller_option_id(self) -> None:
        chosen = choose(
            (
                ScoredOption("store:b", "b", "lot", 100, 10, 10, 5),
                ScoredOption("store:a", "a", "lot", 100, 10, 10, 5),
            )
        )
        self.assertEqual(chosen.option_id, "store:a")


if __name__ == "__main__":
    unittest.main()
