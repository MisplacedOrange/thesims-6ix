"""Capacity-limited waiting line.

The line preserves admission order. Same-second arrivals are sorted by seeded
rank before they are pushed, so the list itself is first-in admission order.
A full line rejects the order. It does not evict someone already waiting.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WaitEntry:
    order_id: str
    actor_id: str
    rank: int
    enqueued_second: int


class WaitingLine:
    def __init__(self, queue_id: str, capacity: int) -> None:
        self.queue_id = queue_id
        self.capacity = capacity
        self.entries: list[WaitEntry] = []

    def __len__(self) -> int:
        return len(self.entries)

    def full(self) -> bool:
        return len(self.entries) >= self.capacity

    def push(self, entry: WaitEntry) -> int:
        if self.full():
            raise RuntimeError("waiting line is full")
        self.entries.append(entry)
        return len(self.entries) - 1

    def pop_head(self) -> WaitEntry:
        return self.entries.pop(0)

    def positions(self) -> list[tuple[str, int]]:
        return [(entry.order_id, index) for index, entry in enumerate(self.entries)]
