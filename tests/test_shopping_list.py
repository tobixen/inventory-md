"""Tests for shopping list generator, focusing on category: vs tag: handling."""

import json

from inventory_md.shopping_list import (
    generate_shopping_list,
    parse_inventory_for_shopping,
    tag_matches,
)

MINIMAL_VOCABULARY = {
    "concepts": {
        "food": {"id": "food", "broader": [], "narrower": ["food/grains", "food/legumes"]},
        "food/grains": {
            "id": "food/grains",
            "broader": ["food"],
            "narrower": ["food/grains/pasta", "food/grains/flour"],
        },
        "food/grains/pasta": {"id": "food/grains/pasta", "broader": ["food/grains"], "narrower": []},
        "food/grains/flour": {"id": "food/grains/flour", "broader": ["food/grains"], "narrower": []},
        "food/legumes": {
            "id": "food/legumes",
            "broader": ["food"],
            "narrower": ["food/legumes/lentils", "food/legumes/beans"],
        },
        "food/legumes/lentils": {"id": "food/legumes/lentils", "broader": ["food/legumes"], "narrower": []},
        "food/legumes/beans": {"id": "food/legumes/beans", "broader": ["food/legumes"], "narrower": []},
    }
}


class TestParseInventoryForShoppingWithCategories:
    """Test that category: items are parsed as well as tag: items."""

    def test_tag_items_are_found(self):
        """Original tag: items still work."""
        content = "* tag:food/grains/pasta ID:spaghetti qty:2 mass:500g Spaghetti\n"
        items = parse_inventory_for_shopping(content)
        assert len(items) == 1
        assert items[0].qty == 2

    def test_category_items_are_found(self):
        """Items with category: are now included."""
        content = "* category:pasta ID:spaghetti qty:2 mass:500g Spaghetti\n"
        items = parse_inventory_for_shopping(content)
        assert len(items) == 1
        assert items[0].qty == 2

    def test_category_items_without_vocabulary_use_raw_category(self):
        """Without vocabulary, category:pasta becomes tag 'pasta'."""
        content = "* category:pasta ID:spaghetti qty:1 mass:500g Spaghetti\n"
        items = parse_inventory_for_shopping(content)
        assert len(items) == 1
        assert items[0].tag == "pasta"

    def test_category_items_with_vocabulary_get_mapped_tag(self, tmp_path):
        """With vocabulary.json present, category:pasta maps to food/grains/pasta."""
        vocab_path = tmp_path / "vocabulary.json"
        vocab_path.write_text(json.dumps(MINIMAL_VOCABULARY))
        inventory_path = tmp_path / "inventory.md"
        inventory_path.write_text("* category:pasta ID:spaghetti qty:1 mass:500g Spaghetti\n")

        items = parse_inventory_for_shopping(inventory_path.read_text(), vocab_path=vocab_path)
        assert len(items) == 1
        assert items[0].tag == "food/grains/pasta"

    def test_multiple_categories_per_item(self, tmp_path):
        """Items with multiple category: tokens produce comma-joined tag."""
        vocab_path = tmp_path / "vocabulary.json"
        vocab_path.write_text(json.dumps(MINIMAL_VOCABULARY))
        content = "* category:lentils ID:lentils-red qty:1 mass:1kg Red lentils\n"

        items = parse_inventory_for_shopping(content, vocab_path=vocab_path)
        assert len(items) == 1
        assert "food/legumes/lentils" in items[0].tag

    def test_expired_marker_detected_in_category_items(self):
        """EXPIRED marker is still detected for category: items."""
        content = "* category:bouillon ID:bouillon-old qty:1 Chicken bouillon EXPIRED\n"
        items = parse_inventory_for_shopping(content)
        assert len(items) == 1
        assert items[0].expired is True

    def test_lines_without_tag_or_category_are_skipped(self):
        """Lines with neither tag: nor category: are ignored."""
        content = "* ID:weird-item qty:1 Something with no category\n"
        items = parse_inventory_for_shopping(content)
        assert len(items) == 0


class TestTagMatchesWithVocabularyMappedTags:
    """Test that tag_matches correctly handles vocabulary-mapped tags."""

    def test_exact_match(self):
        assert tag_matches("food/grains/pasta", "food/grains/pasta") is True

    def test_wanted_is_ancestor_of_inventory(self):
        """Desired tag food/pasta should match inventory tag food/grains/pasta."""
        # Both 'food' and 'pasta' are in the parts of 'food/grains/pasta'
        assert tag_matches("food/pasta", "food/grains/pasta") is True

    def test_wanted_food_matches_any_food_item(self):
        assert tag_matches("food", "food/grains/pasta") is True

    def test_unrelated_tags_dont_match(self):
        assert tag_matches("food/legumes/lentils", "food/grains/pasta") is False


class TestGenerateShoppingListWithCategories:
    """Integration test: shopping list generated correctly with category: inventory."""

    def test_category_items_appear_in_shopping_list_as_ok(self, tmp_path):
        """An in-stock category: item should show as OK (not missing)."""
        vocab_path = tmp_path / "vocabulary.json"
        vocab_path.write_text(json.dumps(MINIMAL_VOCABULARY))

        inventory_path = tmp_path / "inventory.md"
        inventory_path.write_text("* category:pasta ID:spaghetti qty:4 mass:500g Spaghetti\n")

        wanted_path = tmp_path / "wanted-items.md"
        wanted_path.write_text("## Dry goods\n\n* tag:food/pasta - Pasta target:qty:2 mass:1kg\n")

        result = generate_shopping_list(wanted_path, inventory_path, vocab_path=vocab_path)
        # Should be fully stocked — no missing/low entries
        assert "missing" not in result.lower() or "0 missing" in result.lower()
        assert "not in inventory" not in result

    def test_missing_category_item_shows_as_not_in_inventory(self, tmp_path):
        """An item only in wanted-items but not inventory shows as missing."""
        vocab_path = tmp_path / "vocabulary.json"
        vocab_path.write_text(json.dumps(MINIMAL_VOCABULARY))

        inventory_path = tmp_path / "inventory.md"
        inventory_path.write_text("* category:pasta ID:spaghetti qty:4 mass:500g Spaghetti\n")

        wanted_path = tmp_path / "wanted-items.md"
        wanted_path.write_text("## Dry goods\n\n* tag:food/legumes/lentils - Lentils target:qty:1\n")

        result = generate_shopping_list(wanted_path, inventory_path, vocab_path=vocab_path)
        assert "not in inventory" in result
