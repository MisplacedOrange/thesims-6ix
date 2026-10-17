"""Execute each requested cell in a fresh, connected district world."""
from dataclasses import replace
from pathlib import Path

from sim.experiments.adapters import ReplicationResult
from sim.experiments.design import shock_digest
from sim.integration.scenario import DistrictConfig, run_district


class DistrictExecutor:
    def __init__(self, config=None, output_directory=None):
        self.config = config or DistrictConfig()
        self.output_directory = Path(output_directory) if output_directory else None
        self.executed_runs = 0

    def execute(self, request):
        if request.gateway_enabled or request.agent_policy != "rules":
            raise ValueError("the connected district currently supports recorded rule decisions only")
        if shock_digest(request.shocks) != request.shock_digest:
            raise ValueError("shock digest does not match the actual shocks")
        overrides = {}
        for key, value in request.parameter_overrides:
            if key in {"subsidy_cents", "price_support_cents"}:
                overrides[key] = int(value)
            elif key == "route_eligible":
                if value not in {"true", "false"}:
                    raise ValueError("route_eligible must be true or false")
                overrides[key] = value == "true"
            elif key in {"participation", "substitution_share", "procurement_mode"}:
                overrides[key] = value
            else:
                raise ValueError(f"unsupported district parameter: {key}")
        config = replace(self.config, **overrides)
        run = run_district(request.seed, request.enabled_policies, config, request.shocks)
        missing = set(request.outcome_names) - set(run.outcomes)
        if missing:
            raise ValueError(f"unsupported district outcomes: {sorted(missing)}")
        if self.output_directory:
            from sim.integration.export import export_run
            # Cell ids contain '+'; the directory name is data, never a shell command.
            name = f"{request.sensitivity_family or 'main'}-{request.sensitivity_level or 'main'}-{request.cell_id}-s{request.seed}"
            export_run(run, self.output_directory / name, request=request)
        self.executed_runs += 1
        return ReplicationResult(True, None,
            tuple((name, run.outcomes[name]) for name in request.outcome_names),
            run.households, request.shock_digest, 0, run.economic_hash)
