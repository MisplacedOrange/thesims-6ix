import unittest

from sim.experiments.runner import StudySpec, run_study
from sim.integration.experiments import DistrictExecutor
from sim.integration.scenario import DistrictConfig


class ConnectedExperimentTests(unittest.TestCase):
    def test_sensitivity_varies_the_paired_policy_effect(self):
        from sim.experiments.adapters import ReplicationResult
        class Executor:
            def execute(self, request):
                subsidy = dict(request.parameter_overrides).get("subsidy_cents", "200")
                value = 4 if request.enabled_policies and subsidy == "200" else 10
                return ReplicationResult(True, None, (("unmet_grams", value),), (), request.shock_digest, 0)
        spec = StudySpec("sensitivity", "Does the effect depend on funding?", "synthetic", "one day",
            "paired", ("unmet_grams",), (("unmet_grams", "grams"),), (), (17,),
            treatment=("groceries",), shock_days=1, run_sensitivity=True,
            sensitivity_families=("municipal_stores",))
        report = run_study(spec, Executor())
        spread = next(row for row in report.sensitivity if row.cell_id == "groceries")
        self.assertEqual(spread.estimand, "treatment minus matched baseline")
        self.assertEqual(dict(spread.level_means), {"adverse": 0, "baseline": -6, "null": 0})

    def test_nonfinite_results_are_failed_replications(self):
        from sim.experiments.adapters import ReplicationResult
        class Executor:
            def execute(self, request):
                return ReplicationResult(True, None, (("unmet_grams", float("nan")),), (), request.shock_digest, 0)
        spec = StudySpec("invalid", "Reject invalid outcomes", "synthetic", "one day", "paired",
            ("unmet_grams",), (("unmet_grams", "grams"),), (), (17,), treatment=("groceries",), shock_days=1)
        report = run_study(spec, Executor())
        self.assertFalse(report.complete)
        self.assertEqual(report.failed_runs, 2)
        self.assertEqual(report.paired, ())

    def test_screening_executes_sixteen_distinct_worlds(self):
        outcomes = ("household_payment_cents", "unmet_grams", "fiscal_outlay_cents")
        spec = StudySpec("screen-smoke", "Do connected policy mechanisms change outcomes?",
            "12 synthetic households", "one synthetic school day", "screening", outcomes,
            ((outcomes[0], "cents"), (outcomes[1], "grams"), (outcomes[2], "cents")),
            ("Illustrative produce component only",), (17,), shock_days=1,
            worse_when_higher=("unmet_grams",))
        executor = DistrictExecutor(DistrictConfig(households=12))
        report = run_study(spec, executor)
        self.assertTrue(report.complete, report.failure_reasons)
        self.assertEqual(report.completed_runs, 16)
        self.assertEqual(executor.executed_runs, 16)
        self.assertEqual(len({digest for _, _, digest in report.economic_hashes}), 16)
        self.assertEqual(report.llm_dispatch_count, 0)
        self.assertTrue(report.subgroups)
        self.assertTrue(any(row.mean != 0 for row in report.paired))

    def test_unsupported_parameter_does_not_produce_a_completed_run(self):
        from sim.experiments.adapters import ReplicationRequest
        from sim.experiments.design import draw_shocks, shock_digest
        shocks = draw_shocks(17, days=1, actors=("district",))
        request = ReplicationRequest("test", "baseline", (), 17, "sha256-unit-v1",
            shock_digest(shocks), shocks, (("invented_parameter", "1"),), None, None,
            "rules", False, ("unmet_grams",))
        executor = DistrictExecutor(DistrictConfig(households=4))
        with self.assertRaisesRegex(ValueError, "unsupported"):
            executor.execute(request)
        self.assertEqual(executor.executed_runs, 0)
