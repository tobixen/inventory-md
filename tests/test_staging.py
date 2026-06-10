"""Tests for the canonical staging schema guard (scripts/staging.py).

Canonical schema is *flat single-shop*: one staging file per shop visit, with
top-level ``session`` / ``shop`` / ``currency`` / ``items``. The retired
multi-shop ``shops:`` wrapper must be rejected loudly (it used to import 0 rows
silently — see docs/shopping-pipeline-issues-2026-06-07.md issue 1).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import pytest  # noqa: E402
from staging import require_flat  # noqa: E402


def test_accepts_flat_single_shop():
    staging = {"session": "2026-06-07", "shop": "Lidl Varna", "currency": "EUR", "items": []}
    assert require_flat(staging) is staging


def test_rejects_multishop_shops_wrapper():
    staging = {"session": "2026-06-07", "shops": [{"shop": "Lidl", "items": []}]}
    with pytest.raises(ValueError, match="shops"):
        require_flat(staging)


def test_rejects_non_mapping():
    with pytest.raises(ValueError):
        require_flat([{"shop": "Lidl"}])
