# Experiments

Weeks 14–16 reports: drone fallback, a matched-seed screen, sensitivity sweeps, and subgroup counts.

```bash
PYTHONPATH=. python3 -m unittest discover -s sim/experiments/tests -q
```

`run_drones` keeps a no-approval branch, a weather closure, a failed handoff with ground fallback, and a case with no van. Cost per completed order is integer cents plus a remainder. Unserved orders are not in the denominator.

`run_screening` executes 16 cells at the seeds you pass. The planning total remains 480. The bundled demonstration uses seeds 17 and 18. The groceries-and-school interaction is 30 cents at every seed because the shared shock cancels.

`grocery_price_sweep` and `procurement_spoilage_sweep` read the policy ledgers. `population_subgroups` counts the frozen 250 households.

Read [LIMITATIONS.md](LIMITATIONS.md) before quoting a number.
