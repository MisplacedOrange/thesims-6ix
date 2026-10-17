# Limitations

These limits apply to the simulation packages in this repository. They are part of the result, not a footnote to skip.

The district, policies, logistics, choices, drones, and screening totals are **illustrative**. They are not Census counts, Toronto shelf prices, measured walk times, or a **causal estimate** for residents of Toronto.

`price_base_month` is null. Cash in the ledger is nominal. A later display conversion must not rewrite those entries.

The municipal grocery baseline is a closed store. No operating appropriation is assumed from council adoption alone. A funded run is a hypothetical policy. Household savings from a till discount equal the municipal transfer. They are not a reduction in the resource cost of the food.

Processing uses one declared shift and the catalog recipe. Announced annual plant capacity is not throughput. Rescue and purchased inputs stay separate.

School meals do not change attendance or attainment. An absent pupil is not served. Substitution can be zero. The school's cost is not a household purchase.

Pooled procurement is compared at equal served grams. Spoilage and hub labor can make it cost more than separate school orders.

Drone corridors are off unless a scenario flag says otherwise. **No Toronto route approval** is established. The flag is a modeling condition, not permission. Door-to-collection time is a sum of declared stages, not an advertised foreign delivery time. Unserved orders are excluded from the cost per completed order. A failed handoff uses ground fallback when a van exists.

The LLM gateway is **disabled** in these packages. There is no provider client, no token charge, and no retry. Households outside the four-seat barrier are marked `not_selected_for_live_barrier`, which is not a timeout.

The planning screen is 16 cells by 30 matched seed blocks, **480** runs. The executable report runs the 16 cells at the seeds it is given (two seeds in the bundled demonstration). It does not re-simulate the 250-household week inside every cell. Interaction is computed from that declared outcome so a shared shock cancels. It is not a full-district Monte Carlo.

Held-out calibration against observed expenditure, uptake, or delivery reliability has not been done. Subgroup counts reproduce the synthetic quotas. They do not identify who is deprived in the city.

Person 2 owns persistence, replay storage, the provider gateway, and the client. This package emits economic events and animation cues. It does not render them and it does not commit them to a database.

A travelling lot still counts toward `available_grams` in kernel 0.1.0. Callers must not offer it. Queue order is a seeded hash, not actor-id order.
