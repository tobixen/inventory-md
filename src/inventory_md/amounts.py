"""Parsing of ``mass:``/``volume:`` amounts, shared by the parser and the shopping list."""

from __future__ import annotations

import math
import re

_UNITS: dict[str, tuple[float, str]] = {
    "kg": (1000.0, "g"),
    "g": (1.0, "g"),
    "l": (1.0, "l"),
    "dl": (0.1, "l"),
    "cl": (0.01, "l"),
    "ml": (0.001, "l"),
}


def parse_amount(value: str | None) -> tuple[float | None, str | None]:
    """Parse ``500g``, ``1.2kg``, ``400ml`` or ``TOTAL/COUNT`` into ``(amount, unit)``.

    Mass is normalised to grams (``"g"``), volume to litres (``"l"``).  A
    divisor gives the per-unit amount (``mass:1200g/6`` -> 200 g): the documented
    notation for non-uniform items.  A bare number returns unit ``None``, an
    unknown unit is returned as written.  Anything unreadable — including a
    divisor that is empty, not a number, zero, negative or not finite — returns
    ``(None, None)`` rather than a guess.
    """
    if not value:
        return None, None
    main, sep, div = value.lower().strip().partition("/")
    match = re.fullmatch(r"([\d.]+)\s*([a-z]*)", main.strip())
    if not match:
        return None, None
    try:
        amount = float(match.group(1))
    except ValueError:
        return None, None
    unit: str | None = match.group(2) or None
    if unit in _UNITS:
        factor, unit = _UNITS[unit]
        amount *= factor
    if sep:
        try:
            divisor = float(div.strip())
        except ValueError:
            return None, None
        if not math.isfinite(divisor) or divisor <= 0:
            return None, None
        amount /= divisor
    return amount, unit
