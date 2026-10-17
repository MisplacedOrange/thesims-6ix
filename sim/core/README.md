# Economic kernel

`sim.core` is the weeks 1–2 pure transition layer. A caller passes a state and a command and receives either a rejection or the events plus the next state. Replaying those events writes the settled cents and grams. It does not look up a price or a yield again.

Kernel version **0.1.0**. The public names are `sim.core.__all__`. Import `sim.core` only. Importing a submodule is private and can move without a version bump. Renaming or removing a public name requires a kernel version bump.

The 250-household baseline lives in `sim.district`. Policy, logistics, behavior, and experiment packages are other owners. This package does not import them.

## Run

From the repository root, with Python 3.12:

```bash
PYTHONPATH=. python3 -m unittest discover -s sim/core/tests -v
PYTHONPATH=. python3 -m sim.core
```

The demo prints the literal fixture (household 600 cents, municipality 300, retailer 500, processor 100, household 400 g, processor 300 g, consumed 200 g, process loss 100 g) and the illustrative subsidy comparison.

Money is integer Canadian cents. Food is integer grams. Time is integer simulation seconds. Route length, when recorded, is integer metres. `price_base_month` stays null, so cash in the ledger is nominal.

## Shared contracts

Typed drafts for the scenario, the event envelope, commands, the scene snapshot, metric units, and choice offers live in `sim.core.contracts`. The review note is [contracts/DRAFT-shared-contracts.md](contracts/DRAFT-shared-contracts.md). It is marked DRAFT. Wire compatibility beyond kernel 0.1.0 is an open review, not a promise that later packages can extend these records in place.
