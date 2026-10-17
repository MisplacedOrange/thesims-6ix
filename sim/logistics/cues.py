"""Projection of committed events a client can animate.

This is not a second ledger. Every cue points at a command_recorded event.
"""

from __future__ import annotations

from dataclasses import dataclass

_PREFIXES = (
    ("q-", "queue_admission"),
    ("depart-", "trip_started"),
    ("arrive-", "trip_arrived"),
    ("buy-", "purchase"),
    ("batch-", "processing_batch"),
    ("serve-", "meal_served"),
)


@dataclass(frozen=True, slots=True)
class AnimationCue:
    kind: str
    command_id: str
    second: int
    event_id: str


def animation_cues(events: tuple) -> tuple[AnimationCue, ...]:
    cues: list[AnimationCue] = []
    for event in events:
        if event.kind != "command_recorded":
            continue
        kind = _kind(event.command_id)
        if kind is None:
            continue
        cues.append(AnimationCue(kind, event.command_id, event.second, event.event_id))
    return tuple(cues)


def _kind(command_id: str) -> str | None:
    for prefix, kind in _PREFIXES:
        if command_id.startswith(prefix):
            return kind
    return None
