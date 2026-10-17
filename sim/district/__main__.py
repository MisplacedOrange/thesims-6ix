"""Run the frozen 250-household baseline and print the quality report."""

from __future__ import annotations

from sim.district.baseline import run_baseline


def main() -> None:
    result = run_baseline()
    report = result.report
    print(f"baseline {report.run_id} completion {report.completion}")
    print(f"  households {report.household_count} pupils {report.pupil_count} eligible {report.eligible_pupil_count}")
    print(f"  choices {report.choice_count} purchases {report.purchase_count} rejections {report.rejection_count}")
    print(f"  food spend {report.household_food_spend_cents} cents")
    print(f"  purchased {report.grams_purchased} g consumed {report.grams_consumed} g unmet {report.grams_unmet} g")
    print(f"  travel {report.shopping_travel_seconds} s school access {report.school_access_seconds} s")
    print(f"  state {report.state_hash}")
    for check in report.checks:
        mark = "pass" if check.passed else "fail"
        print(f"  {mark} {check.name}: {check.detail}")


if __name__ == "__main__":
    main()
