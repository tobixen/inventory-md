"""Tests for ledger.py — the append-only purchases.jsonl spending ledger.

One line per receipt line-item, keyed by inventory_id so spending can be sliced
by category/time and joined to consumption (items removed from inventory.md).
"""

import sys

sys.path.insert(0, str(__file__).rsplit("/tests/", 1)[0] + "/scripts")
from ledger import (  # noqa: E402
    consumed_rows,
    decathlon_purchase_to_rows,
    detect_removals,
    extract_ids,
    filter_rows,
    lidl_receipt_to_rows,
    load_rows,
    row_identity,
    staging_to_rows,
    total,
    upsert_rows,
)

LIDL_RECEIPT = {
    "purchase_date": "2026.05.28",
    "store": "Варна",
    "total_price_no_saving": "6,64",
    "items": [
        {"name": "СВЕТЛА БИРА 3,0%", "price": "1,17", "quantity": "1"},
        {"name": "НЕКТАРИНИ НА КГ", "price": "2,79", "quantity": "0,078"},
    ],
}

DECATHLON_PURCHASE = {
    "purchase": {
        "transaction": {
            "transaction_id": "7-881-881-XYZ",
            "business_unit_name": "VARNA",
            "currency": "EUR",
            "transaction_date_time_iso": "2026-01-18T14:45:17Z",
            "amount": 5.11,
            "sale_items": [
                {
                    "unit_price": 5.11,
                    "quantity": 1,
                    "amount": 5.11,
                    "product_name": "ВСЕСЕЗОННА СМАЗКА ЗА ВЕРИГА",
                    "serial_number": {"gtin": "03583787174722", "dkt_item_lookup_code": "3583787174722"},
                }
            ],
        }
    }
}


class TestLidlReceiptToRows:
    def test_one_row_per_item(self):
        rows = lidl_receipt_to_rows(LIDL_RECEIPT)
        assert len(rows) == 2

    def test_row_fields(self):
        beer = lidl_receipt_to_rows(LIDL_RECEIPT, shop="Lidl Varna")[0]
        assert beer["date"] == "2026-05-28"
        assert beer["shop"] == "Lidl Varna"
        assert beer["receipt_name"] == "СВЕТЛА БИРА 3,0%"
        assert beer["qty"] == 1.0
        assert beer["unit"] == "pcs"
        assert beer["unit_price"] == 1.17
        assert beer["total"] == 1.17
        assert beer["currency"] == "EUR"
        assert beer["ean"] is None
        assert beer["inventory_id"] is None

    def test_kg_total_is_price_times_qty(self):
        nectarines = lidl_receipt_to_rows(LIDL_RECEIPT)[1]
        assert nectarines["unit"] == "kg"
        assert nectarines["total"] == 0.22

    def test_source_recorded(self):
        rows = lidl_receipt_to_rows(LIDL_RECEIPT, source="lidl#2026-05-28")
        assert all(r["source"] == "lidl#2026-05-28" for r in rows)


class TestDecathlonPurchaseToRows:
    def test_row_has_ean_and_price(self):
        row = decathlon_purchase_to_rows(DECATHLON_PURCHASE)[0]
        assert row["date"] == "2026-01-18"
        assert row["shop"] == "Decathlon VARNA"
        assert row["ean"] == "3583787174722"
        assert row["name"] == "ВСЕСЕЗОННА СМАЗКА ЗА ВЕРИГА"
        assert row["qty"] == 1
        assert row["unit_price"] == 5.11
        assert row["total"] == 5.11
        assert row["currency"] == "EUR"

    def test_gtin_normalized_when_no_lookup_code(self):
        p = {
            "purchase": {
                "transaction": {
                    "business_unit_name": "VARNA",
                    "currency": "EUR",
                    "transaction_date_time_iso": "2026-01-18T14:45:17Z",
                    "sale_items": [
                        {
                            "unit_price": 1.0,
                            "quantity": 1,
                            "amount": 1.0,
                            "product_name": "x",
                            "serial_number": {"gtin": "03583787174722"},
                        }
                    ],
                }
            }
        }
        assert decathlon_purchase_to_rows(p)[0]["ean"] == "3583787174722"


class TestStagingToRows:
    def test_uses_reviewed_fields(self):
        staging = {
            "session": "2026-05-28",
            "shop": "Lidl Varna",
            "currency": "EUR",
            "items": [
                {
                    "receipt_name": "ПРЯСНО МЛЯКО 3,7%",
                    "price": 1.49,
                    "qty": 1.0,
                    "unit": "pcs",
                    "line_total": 1.49,
                    "ean": "4056489947882",
                    "name": "Pilos Fresh Milk 3.7%",
                    "category": "food/dairy",
                    "inventory_id": "milk-2026-05-28",
                    "add_to_inventory": True,
                },
            ],
        }
        row = staging_to_rows(staging)[0]
        assert row["ean"] == "4056489947882"
        assert row["category"] == "food/dairy"
        assert row["inventory_id"] == "milk-2026-05-28"
        assert row["total"] == 1.49


class TestUpsert:
    def test_reimport_is_noop(self, tmp_path):
        path = tmp_path / "purchases.jsonl"
        rows = lidl_receipt_to_rows(LIDL_RECEIPT)
        assert upsert_rows(path, rows) == (2, 0)
        assert upsert_rows(path, rows) == (0, 0)  # re-import adds and enriches nothing
        assert len(load_rows(path)) == 2

    def test_staging_enriches_raw_row_in_place(self, tmp_path):
        path = tmp_path / "purchases.jsonl"
        upsert_rows(path, lidl_receipt_to_rows(LIDL_RECEIPT))  # raw: no ean/category
        staging = {
            "session": "2026-05-28",
            "shop": "Lidl Varna",
            "currency": "EUR",
            "items": [
                {
                    "receipt_name": "СВЕТЛА БИРА 3,0%",
                    "price": 1.17,
                    "qty": 1.0,
                    "unit": "pcs",
                    "line_total": 1.17,
                    "ean": "20431877",
                    "name": "Steam Brew Red",
                    "category": "food/beverages/beer",
                    "inventory_id": "beer-2026-05-28",
                }
            ],
        }
        added, enriched = upsert_rows(path, staging_to_rows(staging))
        assert (added, enriched) == (0, 1)  # matched the raw row, enriched it
        rows = load_rows(path)
        assert len(rows) == 2  # not duplicated
        beer = next(r for r in rows if r["receipt_name"] == "СВЕТЛА БИРА 3,0%")
        assert beer["ean"] == "20431877"
        assert beer["category"] == "food/beverages/beer"
        assert beer["inventory_id"] == "beer-2026-05-28"

    def test_null_incoming_never_overwrites(self, tmp_path):
        path = tmp_path / "purchases.jsonl"
        enriched = lidl_receipt_to_rows(LIDL_RECEIPT)
        enriched[0]["category"] = "food/beverages/beer"
        upsert_rows(path, enriched)
        upsert_rows(path, lidl_receipt_to_rows(LIDL_RECEIPT))  # raw nulls again
        beer = next(r for r in load_rows(path) if r["receipt_name"] == "СВЕТЛА БИРА 3,0%")
        assert beer["category"] == "food/beverages/beer"  # preserved

    def test_identity_ignores_enrichable_fields(self):
        raw = lidl_receipt_to_rows(LIDL_RECEIPT)[0]
        reviewed = dict(raw, ean="20431877", category="food/beverages/beer", inventory_id="x")
        assert row_identity(raw) == row_identity(reviewed)


class TestQuery:
    ROWS = [
        {"date": "2026-08-03", "category": "food/beverages/beer", "total": 1.17, "currency": "EUR", "shop": "Lidl"},
        {"date": "2026-08-20", "category": "food/dairy", "total": 1.49, "currency": "EUR", "shop": "Lidl"},
        {"date": "2026-09-01", "category": "food/beverages/beer", "total": 2.00, "currency": "EUR", "shop": "Lidl"},
    ]

    def test_filter_by_category_prefix(self):
        beer = filter_rows(self.ROWS, category="food/beverages")
        assert len(beer) == 2

    def test_filter_by_date_range(self):
        august = filter_rows(self.ROWS, since="2026-08-01", until="2026-08-31")
        assert len(august) == 2

    def test_total_sums(self):
        beer_august = filter_rows(self.ROWS, category="food/beverages/beer", since="2026-08-01", until="2026-08-31")
        assert total(beer_august) == 1.17


class TestExtractIds:
    def test_extracts_ids(self):
        text = "* category:milk ID:milk-2026 qty:1 Milk\n* category:beer ID:beer-x EAN:123 Beer"
        assert extract_ids(text) == {"milk-2026", "beer-x"}

    def test_ignores_container_headers_only_when_asked(self):
        # plain ID: tokens are captured regardless of context
        assert "food1" in extract_ids("## ID:food1 Pantry")


class TestDetectRemovals:
    def test_removal_recorded_at_disappearance_commit(self):
        revisions = [
            ("2026-08-01", {"milk-1", "beer-1"}),
            ("2026-08-10", {"beer-1"}),  # milk-1 removed here
            ("2026-08-20", set()),  # beer-1 removed here
        ]
        removals = detect_removals(revisions)
        assert removals == {"milk-1": "2026-08-10", "beer-1": "2026-08-20"}

    def test_readded_item_not_marked_removed(self):
        revisions = [
            ("2026-08-01", {"x"}),
            ("2026-08-05", set()),  # removed
            ("2026-08-09", {"x"}),  # re-added
        ]
        # latest state has it present -> not consumed
        assert "x" not in detect_removals(revisions)


class TestConsumedRows:
    def test_join_by_inventory_id_and_date(self):
        rows = [
            {"inventory_id": "milk-1", "total": 1.49, "date": "2026-07-01", "category": "food/dairy"},
            {"inventory_id": "beer-1", "total": 1.17, "date": "2026-07-02", "category": "food/beer"},
            {"inventory_id": None, "total": 9.0, "date": "2026-07-03", "category": "food/x"},
        ]
        removals = {"milk-1": "2026-08-10", "beer-1": "2026-09-20"}
        consumed = consumed_rows(rows, removals, since="2026-08-01", until="2026-08-31")
        assert [r["inventory_id"] for r in consumed] == ["milk-1"]
        assert consumed[0]["consumed_date"] == "2026-08-10"
