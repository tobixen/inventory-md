"""Tests for parser module."""

import pytest

from inventory_md import parser


class TestParseInventoryMarkdownItPy:
    """Tests for the markdown-it-py based parser."""

    def test_parse_simple_container(self, tmp_path):
        """Test parsing a simple container with items."""
        md_file = tmp_path / "inventory.md"
        md_file.write_text("""# ID:box1 Storage Box

Description of the box

* Item one
* Item two
""")
        result = parser.parse_inventory(md_file)

        assert len(result["containers"]) == 1
        container = result["containers"][0]
        assert container["id"] == "box1"
        assert container["heading"] == "Storage Box"
        assert "Description of the box" in container["description"]
        assert len(container["items"]) == 2

    def test_parse_nested_hierarchy(self, tmp_path):
        """Test parsing nested container hierarchy."""
        md_file = tmp_path / "inventory.md"
        md_file.write_text("""# ID:garage Garage

## ID:shelf1 Shelf 1

* Item on shelf

### ID:box1 Box on Shelf

* Item in box
""")
        result = parser.parse_inventory(md_file)

        assert len(result["containers"]) == 3

        # Find containers by ID
        containers = {c["id"]: c for c in result["containers"]}

        assert "garage" in containers
        assert "shelf1" in containers
        assert "box1" in containers

        # Check parent relationships
        assert containers["garage"]["parent"] is None
        assert containers["shelf1"]["parent"] == "garage"
        assert containers["box1"]["parent"] == "shelf1"

    def test_parse_item_metadata(self, tmp_path):
        """Test parsing items with metadata tags."""
        md_file = tmp_path / "inventory.md"
        md_file.write_text("""# ID:box1 Box

* tag:tools,hardware Screwdriver set
* ID:wrench My wrench
""")
        result = parser.parse_inventory(md_file)

        container = result["containers"][0]
        assert len(container["items"]) == 2

        # First item has tags
        assert container["items"][0]["metadata"].get("tags") == ["tools", "hardware"]
        assert container["items"][0]["name"] == "Screwdriver set"

        # Second item has ID
        assert container["items"][1]["metadata"].get("id") == "wrench"
        assert container["items"][1]["name"] == "My wrench"

    def test_parse_intro_section(self, tmp_path):
        """Test that Intro section is extracted."""
        md_file = tmp_path / "inventory.md"
        md_file.write_text("""# Intro

This is the introduction.

# ID:box1 Box

* item
""")
        result = parser.parse_inventory(md_file)

        assert result["intro"] == "This is the introduction."
        assert len(result["containers"]) == 1

    def test_structural_wrapper_section_not_a_container(self, tmp_path):
        """Sections without ID are structural wrappers - not containers, but their subsections are."""
        md_file = tmp_path / "inventory.md"
        md_file.write_text("""# Storage overview

## ID:box1 Box 1

* item1

## ID:box2 Box 2

* item2
""")
        result = parser.parse_inventory(md_file)

        container_ids = [c["id"] for c in result["containers"]]
        assert "box1" in container_ids
        assert "box2" in container_ids
        # The wrapper itself is not a container
        assert "Storage-overview" not in container_ids
        assert len(result["containers"]) == 2

    def test_structural_wrapper_items_are_found(self, tmp_path):
        """Items inside containers under a structural wrapper section are found."""
        md_file = tmp_path / "inventory.md"
        md_file.write_text("""# Attic storage

## ID:A1 Box A1

* category:electronics USB cable
* category:electronics USB charger

## ID:A2 Box A2

* category:tools Hammer
""")
        result = parser.parse_inventory(md_file)

        all_items = [item for c in result["containers"] for item in c["items"]]
        item_names = [i["name"] for i in all_items]
        assert "USB cable" in item_names
        assert "USB charger" in item_names
        assert "Hammer" in item_names

    def test_configurable_intro_section_name(self, tmp_path):
        """Intro section name is configurable via config dict."""
        md_file = tmp_path / "inventory.md"
        md_file.write_text("""# Preface

Custom intro text.

# ID:box1 Box

* item
""")
        config = {"sections": {"intro": "Preface", "numbering_scheme": "Numbering"}}
        result = parser.parse_inventory(md_file, config=config)

        assert result["intro"] == "Custom intro text."
        assert len(result["containers"]) == 1

    def test_default_intro_section_name(self, tmp_path):
        """Default intro section name is 'Intro'."""
        md_file = tmp_path / "inventory.md"
        md_file.write_text("""# Intro

Default intro text.

# ID:box1 Box

* item
""")
        result = parser.parse_inventory(md_file)

        assert result["intro"] == "Default intro text."

    def test_parse_indented_items(self, tmp_path):
        """Test parsing indented (nested) items."""
        md_file = tmp_path / "inventory.md"
        md_file.write_text("""# ID:box1 Box

* Main item
  * Nested item 1
  * Nested item 2
""")
        result = parser.parse_inventory(md_file)

        container = result["containers"][0]
        assert len(container["items"]) == 3
        assert container["items"][0]["indented"] is False
        assert container["items"][1]["indented"] is True
        assert container["items"][2]["indented"] is True

    def test_parse_item_categories(self, tmp_path):
        """Test parsing items with category metadata."""
        md_file = tmp_path / "inventory.md"
        md_file.write_text("""# ID:box1 Box

* category:food/vegetables/potatoes Potatoes from garden
* category:tools/hand-tools Hammer
""")
        result = parser.parse_inventory(md_file)

        container = result["containers"][0]
        assert len(container["items"]) == 2

        # Categories are stored as-is (no normalization)
        assert container["items"][0]["metadata"].get("categories") == ["food/vegetables/potatoes"]
        assert container["items"][0]["name"] == "Potatoes from garden"

        assert container["items"][1]["metadata"].get("categories") == ["tools/hand-tools"]
        assert container["items"][1]["name"] == "Hammer"

    def test_parse_item_multiple_categories(self, tmp_path):
        """Test parsing items with multiple categories."""
        md_file = tmp_path / "inventory.md"
        md_file.write_text("""# ID:box1 Box

* category:food/vegetables,food/staples Potatoes
""")
        result = parser.parse_inventory(md_file)

        container = result["containers"][0]
        # Categories are stored as-is (no normalization)
        assert container["items"][0]["metadata"].get("categories") == ["food/vegetables", "food/staples"]

    def test_parse_item_with_category_and_tag(self, tmp_path):
        """Test parsing items with both category and tag metadata."""
        md_file = tmp_path / "inventory.md"
        md_file.write_text("""# ID:box1 Box

* category:food/vegetables tag:condition:new,packaging:glass Organic potatoes
""")
        result = parser.parse_inventory(md_file)

        container = result["containers"][0]
        item = container["items"][0]

        # Categories are stored as-is (no normalization)
        assert item["metadata"].get("categories") == ["food/vegetables"]
        assert item["metadata"].get("tags") == ["condition:new", "packaging:glass"]
        assert item["name"] == "Organic potatoes"


class TestExtractMetadata:
    """Tests for extract_metadata function."""

    def test_extract_simple_category(self):
        """Test extracting a simple category."""
        result = parser.extract_metadata("category:food/vegetables Potatoes")
        # Categories are stored as-is (no normalization)
        assert result["metadata"].get("categories") == ["food/vegetables"]
        assert result["name"] == "Potatoes"

    def test_extract_multiple_categories(self):
        """Test extracting multiple categories."""
        result = parser.extract_metadata("category:food/vegetables,food/staples Potatoes")
        # Categories are stored as-is (no normalization)
        assert result["metadata"].get("categories") == ["food/vegetables", "food/staples"]
        assert result["name"] == "Potatoes"

    def test_extract_category_and_tag(self):
        """Test extracting both category and tag."""
        result = parser.extract_metadata("category:tools/hand-tools tag:condition:new Hammer")
        # Categories are stored as-is (no normalization)
        assert result["metadata"].get("categories") == ["tools/hand-tools"]
        assert result["metadata"].get("tags") == ["condition:new"]
        assert result["name"] == "Hammer"

    def test_extract_category_with_id(self):
        """Test extracting category with ID."""
        result = parser.extract_metadata("ID:item1 category:food/vegetables Potatoes")
        assert result["metadata"].get("id") == "item1"
        # Categories are stored as-is (no normalization)
        assert result["metadata"].get("categories") == ["food/vegetables"]
        assert result["name"] == "Potatoes"

    def test_extract_no_category(self):
        """Test extracting without category."""
        result = parser.extract_metadata("tag:tools Hammer")
        assert result["metadata"].get("categories") is None
        assert result["metadata"].get("tags") == ["tools"]
        assert result["name"] == "Hammer"


class TestExtractMetadataTypedFields:
    """Tests for typed field parsing in extract_metadata."""

    def test_qty_parsed_as_float(self):
        result = parser.extract_metadata("qty:3 Spaghetti")
        assert result["metadata"]["qty"] == 3.0
        assert isinstance(result["metadata"]["qty"], float)

    def test_qty_fractional(self):
        result = parser.extract_metadata("qty:0.5 Pasta (opened)")
        assert result["metadata"]["qty"] == 0.5

    def test_mass_kg_normalized_to_grams(self):
        result = parser.extract_metadata("mass:1.5kg Pasta")
        assert result["metadata"]["mass_g"] == 1500.0
        assert "mass" not in result["metadata"]

    def test_mass_g_stored_as_float(self):
        result = parser.extract_metadata("mass:500g Pasta")
        assert result["metadata"]["mass_g"] == 500.0

    def test_volume_ml_normalized_to_liters(self):
        result = parser.extract_metadata("volume:500ml Juice")
        assert result["metadata"]["volume_l"] == pytest.approx(0.5)
        assert "volume" not in result["metadata"]

    def test_volume_l_stored_as_float(self):
        result = parser.extract_metadata("volume:1.5l Juice")
        assert result["metadata"]["volume_l"] == 1.5

    def test_volume_cl_normalized_to_liters(self):
        result = parser.extract_metadata("volume:33cl Beer")
        assert result["metadata"]["volume_l"] == pytest.approx(0.33)

    def test_bb_full_date_unchanged(self):
        result = parser.extract_metadata("bb:2026-03-15 Pasta")
        assert result["metadata"]["bb"] == "2026-03-15"

    def test_bb_year_month_extended_to_last_day(self):
        result = parser.extract_metadata("bb:2026-03 Pasta")
        assert result["metadata"]["bb"] == "2026-03-31"

    def test_bb_year_only_extended_to_dec_31(self):
        result = parser.extract_metadata("bb:2026 Pasta")
        assert result["metadata"]["bb"] == "2026-12-31"

    def test_bb_feb_last_day_non_leap(self):
        result = parser.extract_metadata("bb:2025-02 Pasta")
        assert result["metadata"]["bb"] == "2025-02-28"

    def test_bb_feb_last_day_leap_year(self):
        result = parser.extract_metadata("bb:2024-02 Pasta")
        assert result["metadata"]["bb"] == "2024-02-29"

    def test_bb_est_flag_sets_bb_inferred(self):
        result = parser.extract_metadata("bb:2026-03 EST Pasta")
        assert result["metadata"]["bb"] == "2026-03-31"
        assert result["metadata"]["bb_inferred"] is True
        assert "EST" not in result["name"]

    def test_bb_without_est_has_no_bb_inferred(self):
        result = parser.extract_metadata("bb:2026-03 Pasta")
        assert "bb_inferred" not in result["metadata"]

    def test_name_cleaned_of_typed_fields(self):
        result = parser.extract_metadata("category:pasta qty:2 mass:500g bb:2026-03 EST Spaghetti")
        assert result["name"] == "Spaghetti"
        assert "EST" not in result["name"]
