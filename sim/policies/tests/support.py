"""Checks shared by the mechanism fixtures."""

from __future__ import annotations

import unittest
from dataclasses import fields, is_dataclass

from sim.policies.core_interface import InMemoryCore


def assert_conserved(test: unittest.TestCase, ledger: InMemoryCore) -> None:
    snapshot = ledger.conservation()
    test.assertEqual(snapshot.cents_sum, 0, snapshot.cents_by_account)
    test.assertTrue(snapshot.grams_balanced, snapshot)
    for lot in ledger.lots():
        test.assertGreaterEqual(lot.grams, 0)
        test.assertGreaterEqual(lot.acquisition_cents, 0)
        test.assertGreaterEqual(lot.grams, ledger.reserved_grams(lot.lot_id))
    for account in snapshot.cents_by_account:
        if account == "external:opening":
            continue
        test.assertGreaterEqual(ledger.spendable(account), 0, account)


def assert_integers(test: unittest.TestCase, value: object) -> None:
    if value is None or isinstance(value, (str, bool)):
        return
    if isinstance(value, int):
        return
    if isinstance(value, float):
        test.fail(f"float in result: {value}")
    if isinstance(value, dict):
        for item in value.values():
            assert_integers(test, item)
        return
    if isinstance(value, (tuple, list)):
        for item in value:
            assert_integers(test, item)
        return
    if is_dataclass(value):
        for field in fields(value):
            assert_integers(test, getattr(value, field.name))
        return
    test.fail(f"unexpected result type {type(value)}")
