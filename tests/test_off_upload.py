"""Tests for off_upload.build_body (pure OFF write-body construction)."""

import sys

import pytest

sys.path.insert(0, str(__file__).rsplit("/tests/", 1)[0] + "/scripts")
from off_upload import build_body  # noqa: E402


def test_code_required():
    with pytest.raises(ValueError):
        build_body({"product_name_en": "x"})


def test_known_fields_passed_through():
    body = build_body(
        {
            "code": "3800225663700",
            "lang": "bg",
            "product_name_bg": "НАХУТ КРИНА",
            "product_name_en": "Krina chickpeas",
            "brands": "Krina",
            "quantity": "250 g",
            "categories": "Chickpeas, Legumes",
            "stores": "Billa",
            "countries": "Bulgaria",
        }
    )
    assert body["code"] == "3800225663700"
    assert body["product_name_bg"] == "НАХУТ КРИНА"
    assert body["brands"] == "Krina"
    assert body["quantity"] == "250 g"


def test_empty_and_unknown_fields_dropped():
    body = build_body(
        {
            "code": "1",
            "brands": "",
            "quantity": None,
            "front_image": "/x.jpg",  # not an OFF field
            "notes": "ignore me",
        }
    )
    assert body == {"code": "1"}  # nothing blank or extraneous gets written


def test_code_coerced_to_str_and_stripped():
    assert build_body({"code": " 123 "})["code"] == "123"
