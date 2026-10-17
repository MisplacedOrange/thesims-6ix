# Behavior

Weeks 12–13 choice contract on the simulation side. There is no provider client here.

```bash
PYTHONPATH=. python3 -m unittest discover -s sim/behavior/tests -q
```

`known_facts` exposes one household's spendable cents, pantry grams, and public prices. `legal_candidates` drops a basket that costs more than that cash and always keeps `no-purchase`. `decide(..., gateway_enabled=False)` returns the rule option and the reason `gateway_disabled`.

Invalid, refused, late, stale, missing, and unaffordable receipts fall back to that same rule option with origin `fallback`. Households outside the four-seat barrier use the rule and the reason `not_selected_for_live_barrier`. That reason is not a timeout.

`ChoiceOffer` and `ChoiceReceipt` are the DRAFT records in `sim.core`. `ResolvedChoice.reason` sits beside the receipt because the receipt has no reason field yet.
