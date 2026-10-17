"""Explicit day windows. A local day is not assumed to be 86,400 seconds."""

from __future__ import annotations

from dataclasses import dataclass

from sim.core.reporting import FieldError
from sim.core.units import require_int, require_nonnegative


@dataclass(frozen=True, slots=True)
class DayWindow:
    day_index: int
    local_date: str
    start_second: int
    length_seconds: int


def validate_calendar(days: tuple[DayWindow, ...]) -> tuple[FieldError, ...]:
    errors: list[FieldError] = []
    if not days:
        return (FieldError("calendar", "at least one day is required"),)
    for index, day in enumerate(days):
        field = f"days[{index}]"
        try:
            day_index = require_nonnegative(day.day_index, f"{field}.day_index")
            start = require_nonnegative(day.start_second, f"{field}.start_second")
            length = require_int(day.length_seconds, f"{field}.length_seconds")
        except ValueError as exc:
            errors.append(FieldError(field, str(exc)))
            continue
        if day_index != index:
            errors.append(FieldError(f"{field}.day_index", "day_index must equal its position"))
        if length < 1:
            errors.append(FieldError(f"{field}.length_seconds", "length must be >= 1"))
        if not isinstance(day.local_date, str) or len(day.local_date) != 10:
            errors.append(FieldError(f"{field}.local_date", "local_date must be YYYY-MM-DD"))
        if index > 0 and not errors:
            previous = days[index - 1]
            if start != previous.start_second + previous.length_seconds:
                errors.append(FieldError(f"{field}.start_second", "days must meet without a gap or overlap"))
    return tuple(errors)


def second_in_day(day: DayWindow, offset_seconds: int) -> int:
    offset = require_nonnegative(offset_seconds, "offset_seconds")
    if offset >= day.length_seconds:
        raise ValueError("offset_seconds is outside the day")
    return day.start_second + offset
