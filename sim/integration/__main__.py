"""Run a district or replicated study without rendering or provider calls."""
import argparse
from dataclasses import asdict
from pathlib import Path

from sim.experiments.report import render_report
from sim.experiments.runner import StudySpec, run_study
from sim.integration.experiments import DistrictExecutor
from sim.integration.export import export_run, write_json
from sim.integration.scenario import DistrictConfig, run_district


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("run", "paired", "screening"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--households", type=int, default=250)
    parser.add_argument("--seeds", type=int, nargs="+", default=[17])
    parser.add_argument("--policies", nargs="*", default=["groceries"])
    parser.add_argument("--procurement", choices=("decentralized", "pooled"), default="decentralized")
    parser.add_argument("--conditional-drone-route", action="store_true")
    args = parser.parse_args()
    config = DistrictConfig(households=args.households, procurement_mode=args.procurement,
                            route_eligible=args.conditional_drone_route)
    if args.mode == "run":
        if len(args.seeds) != 1:
            parser.error("run accepts exactly one seed")
        run = run_district(args.seeds[0], tuple(args.policies), config)
        export_run(run, args.out)
        print(run.outcomes)
        print(f"Illustrative district export: {args.out}")
        return
    args.out.mkdir(parents=True, exist_ok=False)
    outcomes = ("household_payment_cents", "unmet_grams", "travel_seconds", "fiscal_outlay_cents", "food_waste_grams")
    spec = StudySpec(study_id="connected-district", question="How do declared policies change this illustrative produce-component day?",
        population=f"{args.households} unweighted synthetic households", observation_window="one synthetic school day",
        design="paired" if args.mode == "paired" else "screening", outcomes=outcomes,
        units=tuple((name, "cents" if name.endswith("cents") else "seconds" if name.endswith("seconds") else "grams") for name in outcomes),
        assumptions=("Illustrative inputs. Rule choices. Existing synthetic school provision in the baseline.",),
        seeds=tuple(args.seeds), treatment=tuple(args.policies), shock_days=1,
        worse_when_higher=("household_payment_cents", "unmet_grams", "travel_seconds"))
    report = run_study(spec, DistrictExecutor(config, args.out / "runs"))
    write_json(args.out / "study.json", asdict(report))
    (args.out / "report.txt").write_text(render_report(report), encoding="utf-8")
    if not report.complete:
        raise SystemExit(f"Study incomplete: {report.failure_reasons}")
    print(f"Completed {report.completed_runs} actual district runs: {args.out}")


if __name__ == "__main__":
    main()
