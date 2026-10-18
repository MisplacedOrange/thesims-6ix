"""Council action capabilities. Candidate actions cannot mutate simulator state."""

EXECUTABLE_ACTIONS = {"establish_service_site", "expand_facility", "reduce_or_close_service"}
CANDIDATE_REQUIREMENTS = {
    "fund_program": "Separate appropriation, commitment and transfer; recipient authority, period and conditions.",
    "set_municipal_price_policy": "Municipal offers, effective interval, funded subsidy cap and receipt accounting.",
    "arrange_procurement": "Supply commitments, delivery failures, storage, reservations and settlement terms.",
    "allocate_operating_resources": "Staff/equipment pools, assignment authority, schedules and operating costs.",
    "modify_road_or_transit": "Network assets, route effects, construction disruption, budgets and multi-day state.",
    "develop_housing": "Housing assets, occupancy, construction resources, costs and multi-day state.",
    "modify_utilities": "Utility assets, network capacity, outages, demand, costs and multi-day state.",
}


def action_catalog() -> list[dict]:
    """Return fresh descriptors for display; Python validation remains authoritative."""
    actions = [
        ("establish_service_site", "Establish municipal food service",
         "Pinned location, hypothetical municipal operator, grant cents, stock grams, visit limit and six stage ticks.",
         "Readiness -> funding -> delivery -> commissioning -> opening -> closure; no service before opening."),
        ("expand_facility", "Expand municipal service capacity",
         "Complete base_site schedule, effective_second and absolute target_capacity above its original visit limit.",
         "Same base site in both arms; increase the visit limit during operating hours using assumed spare capability."),
        ("reduce_or_close_service", "Reduce or close municipal service",
         "Complete base_site schedule, effective_second and absolute target_capacity below its original limit (zero closes).",
         "Same base site in both arms; reduce the visit limit, retain past service and procurement; pending arrivals revalidate."),
    ]
    result = [dict(action=action, version=1, executable=True, label=label,
                   inputs=inputs, effects=effects,
                   limits="One hypothetical municipal food site, six hours; no new capital, staffing or cross-day persistence.")
              for action, label, inputs, effects in actions]
    result.extend(dict(action=action, version=1, executable=False,
                       label=action.replace("_", " ").capitalize(), inputs=requirements,
                       effects="No world changes; proposal review only.", limits=requirements)
                  for action, requirements in CANDIDATE_REQUIREMENTS.items())
    return result
