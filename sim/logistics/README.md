# Logistics

Weeks 9–11 headless logistics: seeded queues, a payload and shift limit, and a departure plus a later arrival.

```bash
PYTHONPATH=. python3 -m unittest discover -s sim/logistics/tests -q
```

`run_integrated(seed)` posts one van loading, one missed order, one store purchase, one processing batch, and one school serving. The same seed repeats `state_hash`. `animation_cues` lists queue admission, trip start, trip arrival, purchase, processing, and meal service. Each cue is a `command_recorded` event.

`compare_paired` refuses a kernel, catalog, or population mismatch before it subtracts metrics.

A travelling lot keeps the shipper as owner and sets `journey_id`. The kernel still counts those grams as available. This package does not offer a travelling lot for sale.
