"""Apply kernel commands and stop on the first rejection.

Policy modules post intents. They do not write balances by hand.
"""

from __future__ import annotations

from sim.core import apply_command, empty_state, load_catalog


def world(run_id: str, scenario_id: str):
    catalog = load_catalog()
    return empty_state(
        run_id=run_id,
        scenario_id=scenario_id,
        catalog_id=catalog.catalog_id,
        catalog_sha256=catalog.sha256,
        known_product_ids=tuple(product.product_id for product in catalog.products),
    )


def settle(state, commands: list):
    events: list = []
    for command in commands:
        transition = apply_command(state, command)
        if transition.status != "accepted":
            raise RuntimeError(f"{command.command_id} {transition.status} {transition.reason} {transition.detail}")
        events.extend(transition.events)
        state = transition.state
    return state, tuple(events)


def memo_cents(state, account_id: str, memo: str, *, leaving: bool) -> int:
    total = 0
    for entry in state.journal:
        for line in entry.lines:
            if line.account_id != account_id or line.memo != memo:
                continue
            if leaving and line.cents < 0:
                total += -line.cents
            if not leaving and line.cents > 0:
                total += line.cents
    return total
