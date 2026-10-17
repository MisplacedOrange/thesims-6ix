# District baseline

`sim.district` is the weeks 3–5 synthetic district: input snapshots, 250 households, shopping rules, store inventories, school assignments, and network travel. Settlement stays in `sim.core`. This package imports that public API only.

School meals, subsidies, vans, and drones are not run here. Pupils are assigned, marked eligible or not, and given an attendance draw. No school account is paid and no meal is served. The municipal candidate store is closed and unstocked. The municipality opens at 0 cents.

Inputs are illustrative. They are not Census counts, Toronto shelf prices, or measured walk times. `sim/district/data/manifest.json` pins the raw SHA-256 of each input file, including `sim/core/data/catalog.json`. The manifest does not hash itself.

The population seed (17, in the controls) decides who exists. The run seed decides admission order and choice noise. The same run seed repeats the state hash and the trip list.

## Run

From the repository root:

```bash
PYTHONPATH=. python3 -m unittest discover -s sim/district/tests -v
PYTHONPATH=. python3 -m sim.district
```

The module entry prints the quality report. Completion requires the frozen margins, pupil assignment, conservation, released reservations, zero rejected commands, and spending, stock, and travel reconciled from the ledger.

Shopping is sequential. Household rank `0..249` shops at `day_start + 36000 + rank`, still inside store hours. Each household sees the stock left by earlier shoppers that day. A purchase settles custody at `home-{household}` immediately. Travel seconds are reported beside that purchase. Reserve and purchase are separate kernel commands so a later logistics package can delay arrival without a new settlement verb.

Public names are `sim.district.__all__`.
