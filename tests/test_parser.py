"""Tests for parser module."""

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

        assert len(result['containers']) == 1
        container = result['containers'][0]
        assert container['id'] == 'box1'
        assert container['heading'] == 'Storage Box'
        assert 'Description of the box' in container['description']
        assert len(container['items']) == 2

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

        assert len(result['containers']) == 3

        # Find containers by ID
        containers = {c['id']: c for c in result['containers']}

        assert 'garage' in containers
        assert 'shelf1' in containers
        assert 'box1' in containers

        # Check parent relationships
        assert containers['garage']['parent'] is None
        assert containers['shelf1']['parent'] == 'garage'
        assert containers['box1']['parent'] == 'shelf1'

    def test_parse_item_metadata(self, tmp_path):
        """Test parsing items with metadata tags."""
        md_file = tmp_path / "inventory.md"
        md_file.write_text("""# ID:box1 Box

* tag:tools,hardware Screwdriver set
* ID:wrench My wrench
""")
        result = parser.parse_inventory(md_file)

        container = result['containers'][0]
        assert len(container['items']) == 2

        # First item has tags
        assert container['items'][0]['metadata'].get('tags') == ['tools', 'hardware']
        assert container['items'][0]['name'] == 'Screwdriver set'

        # Second item has ID
        assert container['items'][1]['metadata'].get('id') == 'wrench'
        assert container['items'][1]['name'] == 'My wrench'

    def test_parse_intro_section(self, tmp_path):
        """Test that Intro section is extracted."""
        md_file = tmp_path / "inventory.md"
        md_file.write_text("""# Intro

This is the introduction.

# ID:box1 Box

* item
""")
        result = parser.parse_inventory(md_file)

        assert result['intro'] == 'This is the introduction.'
        assert len(result['containers']) == 1

    def test_parse_indented_items(self, tmp_path):
        """Test parsing indented (nested) items."""
        md_file = tmp_path / "inventory.md"
        md_file.write_text("""# ID:box1 Box

* Main item
  * Nested item 1
  * Nested item 2
""")
        result = parser.parse_inventory(md_file)

        container = result['containers'][0]
        assert len(container['items']) == 3
        assert container['items'][0]['indented'] is False
        assert container['items'][1]['indented'] is True
        assert container['items'][2]['indented'] is True

    def test_parse_item_categories(self, tmp_path):
        """Test parsing items with category metadata."""
        md_file = tmp_path / "inventory.md"
        md_file.write_text("""# ID:box1 Box

* category:food/vegetables/potatoes Potatoes from garden
* category:tools/hand-tools Hammer
""")
        result = parser.parse_inventory(md_file)

        container = result['containers'][0]
        assert len(container['items']) == 2

        # First item has category
        assert container['items'][0]['metadata'].get('categories') == ['food/vegetables/potatoes']
        assert container['items'][0]['name'] == 'Potatoes from garden'

        # Second item has category
        assert container['items'][1]['metadata'].get('categories') == ['tools/hand-tools']
        assert container['items'][1]['name'] == 'Hammer'

    def test_parse_item_multiple_categories(self, tmp_path):
        """Test parsing items with multiple categories."""
        md_file = tmp_path / "inventory.md"
        md_file.write_text("""# ID:box1 Box

* category:food/vegetables,food/staples Potatoes
""")
        result = parser.parse_inventory(md_file)

        container = result['containers'][0]
        assert container['items'][0]['metadata'].get('categories') == ['food/vegetables', 'food/staples']

    def test_parse_item_with_category_and_tag(self, tmp_path):
        """Test parsing items with both category and tag metadata."""
        md_file = tmp_path / "inventory.md"
        md_file.write_text("""# ID:box1 Box

* category:food/vegetables tag:condition:new,packaging:glass Organic potatoes
""")
        result = parser.parse_inventory(md_file)

        container = result['containers'][0]
        item = container['items'][0]

        assert item['metadata'].get('categories') == ['food/vegetables']
        assert item['metadata'].get('tags') == ['condition:new', 'packaging:glass']
        assert item['name'] == 'Organic potatoes'


class TestExtractMetadata:
    """Tests for extract_metadata function."""

    def test_extract_simple_category(self):
        """Test extracting a simple category."""
        result = parser.extract_metadata("category:food/vegetables Potatoes")
        assert result['metadata'].get('categories') == ['food/vegetables']
        assert result['name'] == 'Potatoes'

    def test_extract_multiple_categories(self):
        """Test extracting multiple categories."""
        result = parser.extract_metadata("category:food/vegetables,food/staples Potatoes")
        assert result['metadata'].get('categories') == ['food/vegetables', 'food/staples']
        assert result['name'] == 'Potatoes'

    def test_extract_category_and_tag(self):
        """Test extracting both category and tag."""
        result = parser.extract_metadata("category:tools/hand-tools tag:condition:new Hammer")
        assert result['metadata'].get('categories') == ['tools/hand-tools']
        assert result['metadata'].get('tags') == ['condition:new']
        assert result['name'] == 'Hammer'

    def test_extract_category_with_id(self):
        """Test extracting category with ID."""
        result = parser.extract_metadata("ID:item1 category:food/vegetables Potatoes")
        assert result['metadata'].get('id') == 'item1'
        assert result['metadata'].get('categories') == ['food/vegetables']
        assert result['name'] == 'Potatoes'

    def test_extract_no_category(self):
        """Test extracting without category."""
        result = parser.extract_metadata("tag:tools Hammer")
        assert result['metadata'].get('categories') is None
        assert result['metadata'].get('tags') == ['tools']
        assert result['name'] == 'Hammer'
