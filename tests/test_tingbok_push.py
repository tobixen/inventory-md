"""Tests for scripts/tingbok_push.py — the standalone tingbok observation pusher.

The same script serves the shopping pipeline and ad-hoc single found-item pushes
(a minimal hand-written staging file). A found item typically has no receipt and
no price, so the payload must not carry empty ``receipt_names``/``prices`` rows.
"""

import sys

sys.path.insert(0, str(__file__).rsplit("/tests/", 1)[0] + "/scripts")

import tingbok_push  # noqa: E402


def test_found_item_no_receipt_no_price() -> None:
    """A found item (no receipt_name, no price) pushes name/categories/quantity only."""
    item = {
        "ean": "3800214924577",
        "to_tingbok": True,
        "tingbok_name": "Bulgarian XXL dry-cured sausage",
        "tingbok_categories": ["meats", "dry sausages"],
        "tingbok_quantity": "550g",
    }
    payload = tingbok_push.build_payload(
        item, shop="", date="2026-06-15", currency="EUR", current={}, fill_missing=False
    )
    assert payload["name"] == "Bulgarian XXL dry-cured sausage"
    assert payload["categories"] == ["meats", "dry sausages"]
    assert payload["quantity"] == "550g"
    # No receipt → no receipt_names row; no price → no prices row.
    assert "receipt_names" not in payload
    assert "prices" not in payload


def test_shopping_item_keeps_receipt_and_price() -> None:
    """A normal receipt-derived item still records receipt_names + prices."""
    item = {
        "ean": "5000213101872",
        "to_tingbok": True,
        "receipt_name": "GUINNESS DRAUGHT",
        "name": "Guinness Draught Stout 440ml",
        "price": 2.52,
        "unit": "pcs",
    }
    payload = tingbok_push.build_payload(
        item, shop="Lidl", date="2026-06-13", currency="EUR", current={}, fill_missing=True
    )
    assert payload["receipt_names"] == [
        {"name": "GUINNESS DRAUGHT", "shop": "Lidl", "first_seen": "2026-06-13", "last_seen": "2026-06-13"}
    ]
    assert payload["prices"] == [
        {"date": "2026-06-13", "shop": "Lidl", "price": 2.52, "currency": "EUR", "unit": "pcs"}
    ]
