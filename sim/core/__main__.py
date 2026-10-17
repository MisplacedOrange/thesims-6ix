"""Print the literal fixture and the illustrative subsidy comparison."""

from __future__ import annotations

from sim.core.commands import PHASE_CONSUME, PHASE_POLICY, PHASE_SETTLE, ConsumeFood, ProcessBatch, PurchaseLot, TransferCash, TransferLot
from sim.core.economy import account_for_owner, lots_for_owner
from sim.core.examples import open_fixture_world, run_subsidy_example
from sim.core.kernel import apply_commands, state_hash


def _cash(state, owner: str) -> int:
    account = account_for_owner(state, owner)
    if account is None:
        raise RuntimeError(owner)
    return account.settled_cents


def main() -> None:
    state = open_fixture_world("demo-fixture")
    state = apply_commands(
        state,
        [
            TransferCash("demo-subsidy", 1, PHASE_POLICY, "acct-M", "acct-R", 200, "subsidy"),
            PurchaseLot("demo-buy", 2, PHASE_SETTLE, "acct-H", "acct-R", "home-H", "lot-produce-open", 600, 400),
        ],
    )[-1].state
    household_lot = lots_for_owner(state, "H")[0]
    retailer_lot = lots_for_owner(state, "R")[0]
    state = apply_commands(
        state,
        [
            ConsumeFood("demo-eat", 3, PHASE_CONSUME, "H", household_lot.lot_id, 200),
            TransferLot("demo-move", 4, PHASE_SETTLE, retailer_lot.lot_id, 400, "P", "plant-P"),
            TransferCash("demo-fee", 4, PHASE_SETTLE, "acct-R", "acct-P", 100, "processing_fee"),
        ],
    )[-1].state
    processor_lot = lots_for_owner(state, "P")[0]
    state = apply_commands(
        state,
        [
            ProcessBatch(
                "demo-process",
                5,
                PHASE_SETTLE,
                "P",
                processor_lot.lot_id,
                400,
                "produce.prepared",
                300,
                100,
                "plant-P",
                None,
            )
        ],
    )[-1].state
    print("literal fixture")
    for owner in ("H", "M", "R", "P"):
        print(f"  cash {owner} {_cash(state, owner)} cents")
    print(f"  household grams {sum(lot.grams for lot in lots_for_owner(state, 'H'))}")
    print(f"  processor grams {sum(lot.grams for lot in lots_for_owner(state, 'P'))}")
    print(f"  consumed {state.consumed_grams} g  loss {state.loss_grams} g")
    print(f"  state {state_hash(state)}")
    example = run_subsidy_example()
    print("subsidy example")
    for run in (example.baseline, example.treatment, example.exhausted):
        print(
            f"  {run.label}: pay {run.household_pays_cents} subsidy {run.subsidy_cents} "
            f"unfunded {run.unfunded_discount_cents} exhausted {run.budget_exhausted}"
        )
    print(example.note)


if __name__ == "__main__":
    main()
