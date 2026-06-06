"""Tests for openprices_publish pure helpers."""

import sys

import pytest

sys.path.insert(0, str(__file__).rsplit("/tests/", 1)[0] + "/scripts")
from openprices_publish import _dms_to_deg, _parse_discount, _parse_osm, build_price  # noqa: E402


class TestDiscount:
    ROW = {"ean": "x", "unit_price": 0.79, "currency": "EUR", "date": "2026-06-06", "unit": "pcs"}

    def test_parse_discount(self):
        assert _parse_discount("3800050405919=1.15:SALE") == ("3800050405919", 1.15, "SALE")

    def test_parse_discount_default_type(self):
        assert _parse_discount("123=2.00") == ("123", 2.0, "SALE")

    def test_build_price_discounted(self):
        p = build_price(
            {**self.ROW, "price_without_discount": 1.15, "discount_type": "SALE"}, proof_id=1, osm_type="WAY", osm_id=1
        )
        assert p["price"] == 0.79
        assert p["price_is_discounted"] is True
        assert p["price_without_discount"] == 1.15
        assert p["discount_type"] == "SALE"

    def test_no_discount_when_gross_not_higher(self):
        p = build_price({**self.ROW, "price_without_discount": 0.79}, proof_id=1, osm_type="WAY", osm_id=1)
        assert "price_is_discounted" not in p


class TestParseOsm:
    def test_way(self):
        assert _parse_osm("WAY:1016681733") == ("WAY", 1016681733)

    def test_lowercase_node(self):
        assert _parse_osm("node:42") == ("NODE", 42)

    def test_bad_type(self):
        with pytest.raises(ValueError):
            _parse_osm("PLACE:1")

    def test_missing_id(self):
        with pytest.raises(ValueError):
            _parse_osm("WAY:")


class TestDmsToDeg:
    def test_north(self):
        assert _dms_to_deg((43.0, 13.0, 11.475), "N") == pytest.approx(43.21985, abs=1e-4)

    def test_east(self):
        assert _dms_to_deg((27.0, 52.0, 58.25), "E") == pytest.approx(27.88285, abs=1e-4)

    def test_south_is_negative(self):
        assert _dms_to_deg((10.0, 0.0, 0.0), "S") == pytest.approx(-10.0)


class TestBuildPrice:
    ROW = {
        "ean": "3800856095703",
        "unit_price": 1.78,
        "currency": "EUR",
        "date": "2026-06-06",
        "unit": "pcs",
        "name": "Billa rice",
    }

    def test_product_price_fields(self):
        p = build_price(self.ROW, proof_id=42, osm_type="NODE", osm_id=123)
        assert p["proof_id"] == 42
        assert p["type"] == "PRODUCT"
        assert p["product_code"] == "3800856095703"
        assert p["price"] == 1.78
        assert p["currency"] == "EUR"
        assert "price_per" not in p  # PRODUCT prices omit price_per
        assert p["location_osm_id"] == 123
        assert p["location_osm_type"] == "NODE"
        assert p["product_name"] == "Billa rice"

    def test_no_price_per_for_product(self):
        # price_per is only for CATEGORY prices; PRODUCT (EAN) must omit it
        row = {**self.ROW, "unit": "kg"}
        assert "price_per" not in build_price(row, proof_id=1, osm_type="NODE", osm_id=1)

    def test_ean_coerced_to_str(self):
        row = {**self.ROW, "ean": 3800856095703}
        assert build_price(row, proof_id=1, osm_type="NODE", osm_id=1)["product_code"] == "3800856095703"
