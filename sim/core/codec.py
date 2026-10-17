"""Canonical JSON for states and events.

The encoding is UTF-8, sorted object keys, and compact separators. SHA-256 of
those bytes is the economic hash. Floats and boolean-as-int are refused.
"""

from __future__ import annotations

import hashlib
import json
import types
from dataclasses import is_dataclass
from typing import Union, get_args, get_origin, get_type_hints

from sim.core.events import EventEnvelope
from sim.core.models import WorldState
from sim.core.version import EVENT_SCHEMA_VERSION, KERNEL_VERSION


class CodecError(ValueError):
    pass


def to_jsonable(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return {name: to_jsonable(getattr(value, name)) for name in value.__dataclass_fields__}
    if isinstance(value, tuple):
        return [to_jsonable(item) for item in value]
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    raise CodecError(f"cannot encode {type(value).__name__}")


def canonical_json(value: object) -> str:
    return json.dumps(to_jsonable(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _convert(hint: object, value: object) -> object:
    if hint is type(None):
        if value is not None:
            raise CodecError("expected null")
        return None
    if hint is int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise CodecError(f"expected int, got {value!r}")
        return value
    if hint is str:
        if not isinstance(value, str):
            raise CodecError(f"expected str, got {value!r}")
        return value
    if hint is bool:
        if not isinstance(value, bool):
            raise CodecError(f"expected bool, got {value!r}")
        return value
    origin = get_origin(hint)
    if origin is tuple:
        if not isinstance(value, list):
            raise CodecError("expected a list for a tuple field")
        inner = get_args(hint)[0]
        return tuple(_convert(inner, item) for item in value)
    if origin is Union or origin is types.UnionType:
        args = get_args(hint)
        if value is None and type(None) in args:
            return None
        non_none = [arg for arg in args if arg is not type(None)]
        dataclasses = [arg for arg in non_none if isinstance(arg, type) and is_dataclass(arg)]
        if dataclasses and isinstance(value, dict) and "kind" in value:
            for cls in dataclasses:
                if cls.__dataclass_fields__["kind"].default == value["kind"]:
                    return from_jsonable(cls, value)
            raise CodecError(f"unknown kind {value['kind']!r}")
        if len(non_none) == 1:
            return _convert(non_none[0], value)
        raise CodecError(f"cannot decode union {hint}")
    if isinstance(hint, type) and is_dataclass(hint):
        if not isinstance(value, dict):
            raise CodecError(f"expected object for {hint.__name__}")
        return from_jsonable(hint, value)
    raise CodecError(f"unsupported annotation {hint}")


def from_jsonable(cls: type, data: dict) -> object:
    if not isinstance(data, dict):
        raise CodecError(f"{cls.__name__} expects an object")
    hints = get_type_hints(cls)
    missing = set(hints) - set(data)
    extra = set(data) - set(hints)
    if missing or extra:
        raise CodecError(f"{cls.__name__} keys mismatch missing={sorted(missing)} extra={sorted(extra)}")
    kwargs = {name: _convert(hints[name], data[name]) for name in hints}
    return cls(**kwargs)


def state_to_json(state: WorldState) -> str:
    return canonical_json(state)


def state_from_json(text: str) -> WorldState:
    data = json.loads(text)
    if not isinstance(data, dict):
        raise CodecError("state must be an object")
    if data.get("schema_version") != 1:
        raise CodecError("unsupported state schema_version")
    if data.get("kernel_version") != KERNEL_VERSION:
        raise CodecError("unsupported kernel_version")
    state = from_jsonable(WorldState, data)
    if not isinstance(state, WorldState):
        raise CodecError("decoded value was not a world state")
    return state


def events_to_json(events: tuple[EventEnvelope, ...]) -> str:
    return canonical_json(events)


def events_from_json(text: str) -> tuple[EventEnvelope, ...]:
    data = json.loads(text)
    if not isinstance(data, list):
        raise CodecError("events must be a list")
    events = tuple(from_jsonable(EventEnvelope, item) for item in data)
    for event in events:
        if not isinstance(event, EventEnvelope):
            raise CodecError("decoded value was not an event")
        if event.schema_version != EVENT_SCHEMA_VERSION:
            raise CodecError("unsupported event schema_version")
    return events
