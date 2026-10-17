# Economic kernel

`sim.core` is the weeks 1â€“2 pure transition layer. A caller passes a state and a command and receives either a rejection or the events plus the next state. Replaying those events writes the settled cents and grams. It does not look up a price or a yield again.

Kernel version **0.2.0**. The public names are `sim.core.__all__`. Import `sim.core` only. Importing a submodule is private and can move without a version bump. Renaming or removing a public name requires a kernel version bump.

The 250-household baseline lives in `sim.district`. Policy, logistics, behavior, and experiment packages are other owners. This package does not import them.

## Run

From the repository root, with Python 3.10 or newer:

```bash
PYTHONPATH=. python3 -m unittest discover -s sim/core/tests -v
PYTHONPATH=. python3 -m sim.core
```

The demo prints the literal fixture (household 600 cents, municipality 300, retailer 500, processor 100, household 400 g, processor 300 g, consumed 200 g, process loss 100 g) and the illustrative subsidy comparison.

Money is integer Canadian cents. Food is integer grams. Time is integer simulation seconds. Route length, when recorded, is integer metres. `price_base_month` stays null, so cash in the ledger is nominal.

## Shared contracts

Commands, events, state, and scene projections are exported by `sim.core`. Household choice offers and receipts live in `sim.behavior.draft`; the incompatible duplicate proposal was removed. See [kernel contracts](CONTRACTS.md) and [integration status](../../docs/integration.md). Event schema 2 and the required kernel version pin reject 0.1.0 replay bodies.
