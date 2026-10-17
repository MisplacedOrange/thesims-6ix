"""Keep a funded store's authorization across separate household arrivals."""
from dataclasses import dataclass, replace

from sim.policies.core_interface import plan_draw, quote_acquisition
from sim.policies.groceries import GroceryCommand, Shopper, _price, _sell, apply_grocery


@dataclass
class GrocerySession:
    command: GroceryCommand
    opening_result: object
    support_left: int
    sales: list

    @classmethod
    def open(cls, ledger, command):
        if command.shoppers or command.spoil_grams:
            raise ValueError("open a trading session before shoppers or end-of-day spoilage")
        result = ledger.policy(apply_grocery, command)
        return cls(command, result, result.price_support_authorized_cents, [])

    def quote(self, ledger, grams, now):
        if self.opening_result.status != "open":
            return None
        draws = plan_draw(ledger, owner=self.command.store_owner,
                          product_id=self.command.product_id, grams=grams, now=now)
        if draws is None:
            return None
        cogs = quote_acquisition(ledger, draws)
        return _price(self.command, grams, cogs, self.support_left)[0]

    def sell(self, ledger, shopper: Shopper, now):
        command = replace(self.command, now=now)
        with ledger.atomic():
            ledger.at(now)
            result, support, _ = _sell(ledger, command, shopper, self.support_left)
        self.support_left = support
        self.sales.append(result)
        return result
