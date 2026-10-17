# Kernel contracts

Version 0.2.0 is the sole economic authority. Event schema 2 carries settled account, lot, reservation, journal, movement, decision, and non-mass-loss records. State decoding pins the kernel version and refuses old bodies.

Use public commands exported from `sim.core`. `apply_command` returns an accepted transition, an unchanged rejection, or an unchanged duplicate. Adapters may stage multiple commands, but must discard the complete candidate on failure. Core checks cash, food mass, acquisition value, custody, clock and reservation invariants.

`SplitLot` uses the policy port's floor rule for acquisition value and leaves the remainder on the source. The older `PurchaseLot` retains its documented largest-remainder settlement. `TransformLot` conserves the exact stated mass and book value across explicit output and waste records. Added ingredients must be introduced explicitly using a catalog product; they are not inferred from a yield.

`MoveLot` keeps lot identity stable for logistics. A matching whole-lot reservation holder can change custody. The food arrives at a place before changing owner. A cashless reservation may be held by an order ID; cash reservations still require the account owner. No travelling lot is available for sale, processing, consumption, or a second reservation.

Household offers and receipts live only in `sim.behavior.draft`. Core stores settled `ChoiceRecord` values. The connected adapters and remaining compatibility limits are documented in [integration status](../../docs/integration.md).
