"""Tests for shopping list generator."""

import json

import pytest

from inventory_md.shopping_list import (
    DesiredItem,
    InventoryItem,
    evaluate_item,
    generate_shopping_list,
    parse_inventory_for_shopping,
    parse_wanted_items,
    tag_matches,
)

MINIMAL_VOCABULARY = {
    "concepts": {
        "food": {"id": "food", "prefLabel": "Food", "broader": [], "narrower": ["food/grains", "food/legumes"]},
        "food/grains": {
            "id": "food/grains",
            "prefLabel": "Grains",
            "broader": ["food"],
            "narrower": ["food/grains/pasta", "food/grains/flour"],
        },
        "food/grains/pasta": {
            "id": "food/grains/pasta",
            "prefLabel": "Pasta",
            "broader": ["food/grains"],
            "narrower": [],
        },
        "food/grains/flour": {
            "id": "food/grains/flour",
            "prefLabel": "Flour",
            "broader": ["food/grains"],
            "narrower": [],
        },
        "food/legumes": {
            "id": "food/legumes",
            "prefLabel": "Legumes",
            "broader": ["food"],
            "narrower": ["food/legumes/lentils", "food/legumes/beans"],
        },
        "food/legumes/lentils": {
            "id": "food/legumes/lentils",
            "prefLabel": "Lentils",
            "broader": ["food/legumes"],
            "narrower": [],
        },
        "food/legumes/beans": {
            "id": "food/legumes/beans",
            "prefLabel": "Beans",
            "broader": ["food/legumes"],
            "narrower": [],
        },
    }
}


FLAT_VOCABULARY = {
    "concepts": {
        "food": {"id": "food", "prefLabel": "Food", "broader": [], "narrower": ["food/nuts", "food/grains"]},
        "food/nuts": {
            "id": "food/nuts",
            "prefLabel": "Nuts",
            "broader": ["food"],
            "narrower": ["peanuts", "cashews"],
        },
        "food/grains": {
            "id": "food/grains",
            "prefLabel": "Grains",
            "broader": ["food"],
            "narrower": ["pasta"],
        },
        "peanuts": {"id": "peanuts", "prefLabel": "Peanuts", "broader": ["food/nuts"], "narrower": []},
        "cashews": {"id": "cashews", "prefLabel": "Cashews", "broader": ["food/nuts"], "narrower": []},
        "pasta": {"id": "pasta", "prefLabel": "Pasta", "broader": ["food/grains"], "narrower": []},
    }
}


def _make_inventory_json(items_meta: list[dict]) -> dict:
    """Build a minimal inventory.json structure for testing."""
    items = [
        {
            "id": m.get("id", f"item-{i}"),
            "parent": None,
            "name": m.get("name", "Test item"),
            "raw_text": "",
            "metadata": {k: v for k, v in m.items() if k not in ("id", "name")},
            "indented": False,
        }
        for i, m in enumerate(items_meta)
    ]
    return {"containers": [{"id": "test", "items": items, "images": [], "metadata": {}}]}


class TestParseInventoryForShopping:
    """Test parse_inventory_for_shopping with JSON input."""

    def test_tags_are_ignored(self):
        """Tags are legacy; shopping list uses only categories."""
        data = _make_inventory_json([{"tags": ["food/grains/pasta"], "qty": 2.0, "mass_g": 500.0}])
        items = parse_inventory_for_shopping(data)
        assert len(items) == 0

    def test_metadata_tags_do_not_override_categories(self):
        """Metadata tags like 'expired' must not suppress category matching."""
        data = _make_inventory_json([{"categories": ["pasta"], "tags": ["expired"], "qty": 1.0}])
        items = parse_inventory_for_shopping(data)
        assert len(items) == 1
        assert items[0].tag == "pasta"

    def test_category_items_are_found(self):
        data = _make_inventory_json([{"categories": ["pasta"], "qty": 2.0}])
        items = parse_inventory_for_shopping(data)
        assert len(items) == 1

    def test_category_without_vocabulary_uses_raw(self):
        data = _make_inventory_json([{"categories": ["pasta"]}])
        items = parse_inventory_for_shopping(data)
        assert items[0].tag == "pasta"

    def test_category_with_vocabulary_resolves_to_canonical(self, tmp_path):
        vocab_path = tmp_path / "vocabulary.json"
        vocab_path.write_text(json.dumps(MINIMAL_VOCABULARY))
        from inventory_md import vocabulary

        concepts = vocabulary.load_local_vocabulary(vocab_path)

        data = _make_inventory_json([{"categories": ["pasta"]}])
        items = parse_inventory_for_shopping(data, concepts=concepts)
        assert items[0].tag == "food/grains/pasta"

    def test_items_without_tags_or_categories_skipped(self):
        data = _make_inventory_json([{"qty": 1.0}])
        items = parse_inventory_for_shopping(data)
        assert len(items) == 0

    def test_qty_as_float(self):
        data = _make_inventory_json([{"categories": ["pasta"], "qty": 0.5}])
        items = parse_inventory_for_shopping(data)
        assert items[0].qty == 0.5

    def test_qty_as_string_backward_compat(self):
        """Old inventory.json stores qty as string."""
        data = _make_inventory_json([{"categories": ["pasta"], "qty": "3"}])
        items = parse_inventory_for_shopping(data)
        assert items[0].qty == 3.0

    def test_mass_g_new_format(self):
        data = _make_inventory_json([{"categories": ["pasta"], "mass_g": 500.0}])
        items = parse_inventory_for_shopping(data)
        assert items[0].mass_g == 500.0

    def test_mass_string_backward_compat(self):
        """Old inventory.json stores mass as string like '500g'."""
        data = _make_inventory_json([{"categories": ["pasta"], "mass": "500g"}])
        items = parse_inventory_for_shopping(data)
        assert items[0].mass_g == 500.0

    def test_volume_l_new_format(self):
        data = _make_inventory_json([{"categories": ["juice"], "volume_l": 1.5}])
        items = parse_inventory_for_shopping(data)
        assert items[0].volume_l == 1.5

    def test_volume_string_backward_compat(self):
        """Old inventory.json stores volume as string like '1.5l'."""
        data = _make_inventory_json([{"categories": ["juice"], "volume": "1.5l"}])
        items = parse_inventory_for_shopping(data)
        assert items[0].volume_l == 1.5

    def test_bb_stored(self):
        data = _make_inventory_json([{"categories": ["pasta"], "bb": "2026-12-31"}])
        items = parse_inventory_for_shopping(data)
        assert items[0].bb == "2026-12-31"

    def test_no_expired_field(self):
        """InventoryItem has no expired field — expired items count toward stock."""
        data = _make_inventory_json([{"categories": ["pasta"], "bb": "2020-01-01"}])
        items = parse_inventory_for_shopping(data)
        assert not hasattr(items[0], "expired")


class TestTagMatches:
    """Test hierarchical tag matching."""

    def test_exact_match(self):
        assert tag_matches("food/grains/pasta", "food/grains/pasta") is True

    def test_ancestor_matches_descendant(self):
        assert tag_matches("food/grains", "food/grains/pasta") is True

    def test_root_matches_any_descendant(self):
        assert tag_matches("food", "food/grains/pasta") is True

    def test_unrelated_tags_dont_match(self):
        assert tag_matches("food/legumes/lentils", "food/grains/pasta") is False

    def test_non_ancestor_path_does_not_match(self):
        """food/pasta is not an ancestor of food/grains/pasta."""
        assert tag_matches("food/pasta", "food/grains/pasta") is False

    def test_comma_separated_desired_any_matches(self):
        assert tag_matches("food/grains/flour,food/grains/pasta", "food/grains/pasta") is True

    def test_comma_separated_inventory_any_matches(self):
        assert tag_matches("food/grains", "food/grains/pasta,food/legumes/lentils") is True

    def test_flat_concept_matches_via_broader(self, tmp_path):
        """peanuts (broader: food/nuts) should match desired food/nuts with vocabulary."""
        vocab_path = tmp_path / "vocabulary.json"
        vocab_path.write_text(json.dumps(FLAT_VOCABULARY))
        from inventory_md import vocabulary

        concepts = vocabulary.load_local_vocabulary(vocab_path)
        assert tag_matches("food/nuts", "peanuts", concepts) is True

    def test_flat_concept_does_not_match_wrong_parent(self, tmp_path):
        """peanuts should not match food/grains even with vocabulary."""
        vocab_path = tmp_path / "vocabulary.json"
        vocab_path.write_text(json.dumps(FLAT_VOCABULARY))
        from inventory_md import vocabulary

        concepts = vocabulary.load_local_vocabulary(vocab_path)
        assert tag_matches("food/grains", "peanuts", concepts) is False

    def test_flat_concept_matches_transitive_ancestor(self, tmp_path):
        """peanuts (broader: food/nuts, food/nuts broader: food) matches desired food."""
        vocab_path = tmp_path / "vocabulary.json"
        vocab_path.write_text(json.dumps(FLAT_VOCABULARY))
        from inventory_md import vocabulary

        concepts = vocabulary.load_local_vocabulary(vocab_path)
        assert tag_matches("food", "peanuts", concepts) is True


class TestEvaluateItem:
    """Test evaluate_item stock status logic."""

    def test_missing_when_no_matches(self):
        desired = DesiredItem(tag="food/grains/pasta", description="Pasta", target_qty=2.0)
        status, detail = evaluate_item(desired, [])
        assert status == "missing"
        assert "not in inventory" in detail

    def test_ok_when_sufficient_qty(self):
        desired = DesiredItem(tag="food/grains/pasta", description="Pasta", target_qty=2.0)
        inv = [InventoryItem(tag="food/grains/pasta", item_id="p1", description="Spaghetti", qty=3.0)]
        status, _ = evaluate_item(desired, inv)
        assert status == "ok"

    def test_low_when_insufficient_qty(self):
        desired = DesiredItem(tag="food/grains/pasta", description="Pasta", target_qty=5.0)
        inv = [InventoryItem(tag="food/grains/pasta", item_id="p1", description="Spaghetti", qty=2.0)]
        status, detail = evaluate_item(desired, inv)
        assert status == "low"
        assert "have" in detail
        assert "need" in detail

    def test_ok_when_sufficient_mass(self):
        desired = DesiredItem(tag="food/grains/pasta", description="Pasta", target_mass_g=500.0)
        inv = [InventoryItem(tag="food/grains/pasta", item_id="p1", description="Spaghetti", qty=2.0, mass_g=300.0)]
        status, _ = evaluate_item(desired, inv)
        assert status == "ok"  # 2 * 300 = 600g >= 500g

    def test_ok_when_sufficient_volume(self):
        desired = DesiredItem(tag="juice", description="Juice", target_volume_l=1.0)
        inv = [InventoryItem(tag="juice", item_id="j1", description="OJ", qty=2.0, volume_l=0.75)]
        status, _ = evaluate_item(desired, inv)
        assert status == "ok"  # 2 * 0.75 = 1.5l >= 1.0l

    def test_expired_items_count_toward_stock(self):
        """Items with past bb date still count — dispose separately."""
        desired = DesiredItem(tag="food/grains/pasta", description="Pasta", target_qty=1.0)
        inv = [InventoryItem(tag="food/grains/pasta", item_id="p1", description="Old pasta", qty=1.0, bb="2020-01-01")]
        status, _ = evaluate_item(desired, inv)
        assert status == "ok"

    def test_float_qty(self):
        desired = DesiredItem(tag="pasta", description="Pasta", target_qty=1.0)
        inv = [InventoryItem(tag="pasta", item_id="p1", description="Pasta", qty=0.5)]
        status, _ = evaluate_item(desired, inv)
        assert status == "low"


class TestGenerateShoppingList:
    """Integration tests: shopping list from wanted-items.md + inventory.json."""

    def test_in_stock_item_not_shown(self, tmp_path):
        vocab_path = tmp_path / "vocabulary.json"
        vocab_path.write_text(json.dumps(MINIMAL_VOCABULARY))

        inv_data = _make_inventory_json([{"categories": ["pasta"], "qty": 4.0, "mass_g": 500.0}])
        inv_json = tmp_path / "inventory.json"
        inv_json.write_text(json.dumps(inv_data))

        wanted_path = tmp_path / "wanted-items.md"
        wanted_path.write_text("## Dry goods\n\n* category:pasta - Pasta target:qty:2\n")

        result = generate_shopping_list(wanted_path, inv_json, vocab_path=vocab_path)
        assert "0 missing" in result or "missing" not in result.lower() or "0 missing" in result

    def test_missing_item_shown(self, tmp_path):
        vocab_path = tmp_path / "vocabulary.json"
        vocab_path.write_text(json.dumps(MINIMAL_VOCABULARY))

        inv_data = _make_inventory_json([{"categories": ["pasta"], "qty": 1.0}])
        inv_json = tmp_path / "inventory.json"
        inv_json.write_text(json.dumps(inv_data))

        wanted_path = tmp_path / "wanted-items.md"
        wanted_path.write_text("## Legumes\n\n* category:lentils - Lentils target:qty:1\n")

        result = generate_shopping_list(wanted_path, inv_json, vocab_path=vocab_path)
        assert "not in inventory" in result

    def test_category_wanted_matches_category_inventory(self, tmp_path):
        """category:pasta in wanted matches category:pasta in inventory via vocabulary."""
        vocab_path = tmp_path / "vocabulary.json"
        vocab_path.write_text(json.dumps(MINIMAL_VOCABULARY))

        inv_data = _make_inventory_json([{"categories": ["pasta"], "qty": 5.0}])
        inv_json = tmp_path / "inventory.json"
        inv_json.write_text(json.dumps(inv_data))

        wanted_path = tmp_path / "wanted-items.md"
        wanted_path.write_text("## Dry goods\n\n* category:pasta - Pasta target:qty:2\n")

        result = generate_shopping_list(wanted_path, inv_json, vocab_path=vocab_path)
        assert "1 fully stocked" in result

    def test_errors_without_inventory_json(self, tmp_path):
        wanted_path = tmp_path / "wanted-items.md"
        wanted_path.write_text("## Test\n\n* category:pasta - Pasta\n")
        missing_json = tmp_path / "inventory.json"

        with pytest.raises(FileNotFoundError):
            generate_shopping_list(wanted_path, missing_json)


class TestParseWantedItems:
    """Test wanted-items.md parsing."""

    def test_tag_syntax(self):
        content = "## Section\n\n* tag:food/grains/pasta - Pasta target:qty:3\n"
        sections = parse_wanted_items(content)
        assert len(sections) == 1
        assert sections[0].items[0].tag == "food/grains/pasta"
        assert sections[0].items[0].target_qty == 3.0

    def test_category_syntax(self):
        content = "## Section\n\n* category:pasta - Pasta target:qty:2\n"
        sections = parse_wanted_items(content)
        assert sections[0].items[0].tag == "pasta"
        assert sections[0].items[0].target_qty == 2.0

    def test_volume_in_liters(self):
        content = "## Section\n\n* category:juice - Juice volume:2l\n"
        sections = parse_wanted_items(content)
        assert sections[0].items[0].target_volume_l == 2.0

    def test_volume_ml_converted_to_liters(self):
        content = "## Section\n\n* category:juice - Juice volume:500ml\n"
        sections = parse_wanted_items(content)
        assert sections[0].items[0].target_volume_l == pytest.approx(0.5)
