"""Tests for the markdown-it-py adapter module."""

from inventory_md import md_adapter


class TestParseMarkdownString:
    """Tests for parse_markdown_string function."""

    def test_simple_structure(self):
        """Test parsing simple heading structure."""
        content = """# Main

## Sub1

Content here.

## Sub2

More content.
"""
        sections = md_adapter.parse_markdown_string(content)

        assert len(sections) == 1
        assert sections[0].heading == "Main"
        assert len(sections[0].subsections) == 2
        assert sections[0].subsections[0].heading == "Sub1"
        assert sections[0].subsections[1].heading == "Sub2"

    def test_paragraphs(self):
        """Test paragraph extraction."""
        content = """# Section

First paragraph.

Second paragraph.
"""
        sections = md_adapter.parse_markdown_string(content)

        assert sections[0].paragraphs == ["First paragraph.", "Second paragraph."]

    def test_list_items(self):
        """Test list item extraction."""
        content = """# Section

* Item 1
* Item 2
* Item 3
"""
        sections = md_adapter.parse_markdown_string(content)

        assert len(sections[0].list_items) == 3
        assert sections[0].list_items[0]["text"] == "Item 1"
        assert sections[0].list_items[1]["text"] == "Item 2"
        assert sections[0].list_items[2]["text"] == "Item 3"

    def test_nested_lists(self):
        """Test nested list item extraction."""
        content = """# Section

* Main item
  * Nested item 1
  * Nested item 2
* Another main item
"""
        sections = md_adapter.parse_markdown_string(content)

        assert len(sections[0].list_items) == 2
        assert sections[0].list_items[0]["text"] == "Main item"
        assert len(sections[0].list_items[0]["nested"]) == 2
        assert sections[0].list_items[0]["nested"][0]["text"] == "Nested item 1"
        assert sections[0].list_items[0]["nested"][1]["text"] == "Nested item 2"

    def test_mixed_content(self):
        """Test mixed paragraphs and lists."""
        content = """# Section

First paragraph.

* Item 1
* Item 2

Second paragraph.

* Item 3
* Item 4
"""
        sections = md_adapter.parse_markdown_string(content)

        assert len(sections[0].paragraphs) == 2
        assert sections[0].paragraphs[0] == "First paragraph."
        assert sections[0].paragraphs[1] == "Second paragraph."
        assert len(sections[0].list_items) == 4

    def test_heading_hierarchy(self):
        """Test correct heading hierarchy is maintained."""
        content = """# H1

## H2

### H3

Content

## Another H2

More content
"""
        sections = md_adapter.parse_markdown_string(content)

        assert len(sections) == 1  # One H1
        h1 = sections[0]
        assert h1.level == 1
        assert len(h1.subsections) == 2  # Two H2s

        h2_first = h1.subsections[0]
        assert h2_first.level == 2
        assert len(h2_first.subsections) == 1  # One H3

        h3 = h2_first.subsections[0]
        assert h3.level == 3
        assert h3.parent == h2_first


class TestIterAllSections:
    """Tests for iter_all_sections function."""

    def test_flattens_hierarchy(self):
        """Test that sections are flattened correctly."""
        content = """# A

## B

### C

## D
"""
        sections = md_adapter.parse_markdown_string(content)
        all_sections = md_adapter.iter_all_sections(sections)

        headings = [s.heading for s in all_sections]
        assert headings == ["A", "B", "C", "D"]


class TestFindSection:
    """Tests for find_section function."""

    def test_finds_by_partial_match(self):
        """Test finding section by partial heading match."""
        content = """# Main Section

## ID:box1 Storage Box

Content
"""
        sections = md_adapter.parse_markdown_string(content)
        found = md_adapter.find_section(sections, "box1")

        assert found is not None
        assert "box1" in found.heading

    def test_case_insensitive(self):
        """Test case-insensitive search."""
        content = """# MySection

Content
"""
        sections = md_adapter.parse_markdown_string(content)
        found = md_adapter.find_section(sections, "mysection")

        assert found is not None
        assert found.heading == "MySection"

    def test_returns_none_if_not_found(self):
        """Test returns None when section not found."""
        content = """# Section

Content
"""
        sections = md_adapter.parse_markdown_string(content)
        found = md_adapter.find_section(sections, "nonexistent")

        assert found is None


class TestGetAllListItems:
    """Tests for get_all_list_items function."""

    def test_gets_all_items(self):
        """Test getting all list items including nested."""
        content = """# Section

* Item 1
  * Nested 1
  * Nested 2
* Item 2
"""
        sections = md_adapter.parse_markdown_string(content)
        items = md_adapter.get_all_list_items(sections[0])

        assert items == ["Item 1", "Nested 1", "Nested 2", "Item 2"]

    def test_exclude_nested(self):
        """Test getting only top-level items."""
        content = """# Section

* Item 1
  * Nested 1
* Item 2
"""
        sections = md_adapter.parse_markdown_string(content)
        items = md_adapter.get_all_list_items(sections[0], include_nested=False)

        assert items == ["Item 1", "Item 2"]
