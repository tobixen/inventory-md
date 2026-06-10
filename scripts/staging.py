"""Canonical staging-file schema, shared by every consumer.

A reviewed shopping staging file is **flat single-shop**: one file per shop
visit, with top-level ``session`` (date), ``shop``, ``currency`` and ``items``.
This is what ``shop_import.py`` emits and what ``ledger.py`` / ``tingbok_push.py``
consume.

An earlier design wrapped several shops in a top-level ``shops:`` list. That is
retired — a shopping trip spanning two shops is two independent staging files.
Feeding the old layout to a flat consumer used to import 0 rows *silently*
(docs/shopping-pipeline-issues-2026-06-07.md, issue 1), so consumers now reject
it loudly via :func:`require_flat`.
"""

from __future__ import annotations

from typing import Any


def require_flat(staging: Any) -> dict[str, Any]:
    """Validate the canonical flat single-shop schema; return it unchanged.

    Raises ``ValueError`` if *staging* is not a mapping or still carries the
    retired multi-shop ``shops:`` wrapper.
    """
    if not isinstance(staging, dict):
        raise ValueError("staging must be a mapping (flat single-shop schema)")
    if "shops" in staging:
        raise ValueError(
            "multi-shop 'shops:' staging is no longer supported; split the trip into one flat file per shop visit"
        )
    return staging
