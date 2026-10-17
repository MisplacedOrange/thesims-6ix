# Policy mechanisms

Illustrative weeks 6–8 mechanisms. Each function posts `sim.core` commands and reads costs back from the journal and food movements.

```bash
PYTHONPATH=. python3 -m unittest discover -s sim/policies/tests -q
```

- `run_municipal_grocery` compares a closed store with a funded store. The till discount is a municipal transfer. Inventory, labor, and occupancy are the resource cash.
- `run_processing` runs one 400 g shift. Safe rescue is processed first. Purchased grams stay labeled purchased. The yield is the catalog recipe, 300 g edible and 100 g process loss.
- `run_school_day` serves one present eligible pupil, skips an absence, and skips an ineligible pupil. Substitution can be zero. The school bill is not a household purchase.
- `run_procurement` serves 400 g either as two school orders or one hub order. Spoilage and hub labor can make pooling cost more.

Evidence state is `illustrative`. No operating appropriation is assumed for the closed grocery baseline.
