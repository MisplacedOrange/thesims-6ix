"""Synthetic walk network. Path cost is declared walk seconds, not metres."""

from __future__ import annotations

import heapq
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Edge:
    edge_id: str
    a: str
    b: str
    metres: int
    walk_seconds: int


@dataclass(frozen=True, slots=True)
class Network:
    nodes: tuple[str, ...]
    edges: tuple[Edge, ...]


def shortest_path(network: Network, origin: str, destination: str) -> tuple[tuple[str, ...], int] | None:
    """Return the node sequence and total walk seconds.

    Equal durations break toward the lexicographically smaller node sequence.
    Metres are not the cost.
    """

    if origin not in network.nodes or destination not in network.nodes:
        return None
    if origin == destination:
        return (origin,), 0
    neighbors: dict[str, list[tuple[str, int, str]]] = {node: [] for node in network.nodes}
    for edge in network.edges:
        neighbors[edge.a].append((edge.b, edge.walk_seconds, edge.edge_id))
        neighbors[edge.b].append((edge.a, edge.walk_seconds, edge.edge_id))
    for node in neighbors:
        neighbors[node].sort(key=lambda item: item[2])
    best: dict[str, tuple[int, tuple[str, ...]]] = {origin: (0, (origin,))}
    heap: list[tuple[int, str, tuple[str, ...]]] = [(0, origin, (origin,))]
    while heap:
        dist, node, path = heapq.heappop(heap)
        if best.get(node) != (dist, path):
            continue
        for nxt, seconds, _edge_id in neighbors[node]:
            candidate = (dist + seconds, path + (nxt,))
            if nxt not in best or candidate < best[nxt]:
                best[nxt] = candidate
                heapq.heappush(heap, (candidate[0], nxt, candidate[1]))
    found = best.get(destination)
    if found is None:
        return None
    return found[1], found[0]
