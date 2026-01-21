"""Tests for parser module."""
from pathlib import Path

from inventory_md import parser


class TestExtractDocumentMetadata:
    """Tests for extract_document_metadata function."""

    def test_extract_lang(self):
        """Test extracting lang metadata."""
        lines = ['lang: no', '', '# Title']
        meta, consumed = parser.extract_document_metadata(lines)

        assert meta == {'lang': 'no'}
        assert consumed == 2  # lang line + empty line

    def test_extract_language_alias(self):
        """Test that 'language' is treated same as 'lang'."""
        lines = ['language: en', '# Title']
        meta, consumed = parser.extract_document_metadata(lines)

        assert meta == {'lang': 'en'}
        assert consumed == 1

    def test_extract_multiple_metadata(self):
        """Test extracting multiple metadata fields."""
        lines = ['lang: no', 'title: My Inventory', '', '# Intro']
        meta, consumed = parser.extract_document_metadata(lines)

        assert meta == {'lang': 'no', 'title': 'My Inventory'}
        assert consumed == 3

    def test_no_metadata(self):
        """Test file with no document metadata."""
        lines = ['# Title', '* item']
        meta, consumed = parser.extract_document_metadata(lines)

        assert meta == {}
        assert consumed == 0

    def test_stops_at_markdown_heading(self):
        """Test that metadata parsing stops at markdown headings."""
        lines = ['# Title', 'lang: no']
        meta, consumed = parser.extract_document_metadata(lines)

        assert meta == {}
        assert consumed == 0

    def test_stops_at_list_item(self):
        """Test that metadata parsing stops at list items."""
        lines = ['* item', 'lang: no']
        meta, consumed = parser.extract_document_metadata(lines)

        assert meta == {}
        assert consumed == 0

    def test_ignores_urls(self):
        """Test that URLs are not parsed as metadata."""
        lines = ['https://example.com', 'lang: no', '# Title']
        meta, consumed = parser.extract_document_metadata(lines)

        # Should stop at URL (not valid metadata)
        assert meta == {}
        assert consumed == 0

    def test_skips_empty_lines(self):
        """Test that empty lines at start are skipped."""
        lines = ['', '', 'lang: no', '# Title']
        meta, consumed = parser.extract_document_metadata(lines)

        assert meta == {'lang': 'no'}
        assert consumed == 3  # 2 empty + 1 lang


class TestParseInventoryDocumentMetadata:
    """Tests for document metadata in parse_inventory."""

    def test_parse_with_lang(self, tmp_path):
        """Test parsing inventory with lang metadata."""
        md_file = tmp_path / "inventory.md"
        md_file.write_text("lang: no\n\n# ID:test Test container\n\n* item 1\n")

        result = parser.parse_inventory(md_file)

        assert result.get('lang') == 'no'
        assert len(result['containers']) == 1

    def test_parse_with_title(self, tmp_path):
        """Test parsing inventory with title metadata."""
        md_file = tmp_path / "inventory.md"
        md_file.write_text("title: Home Inventory\nlang: en\n\n# ID:box1 Box 1\n")

        result = parser.parse_inventory(md_file)

        assert result.get('title') == 'Home Inventory'
        assert result.get('lang') == 'en'

    def test_parse_without_metadata(self, tmp_path):
        """Test parsing inventory without document metadata."""
        md_file = tmp_path / "inventory.md"
        md_file.write_text("# ID:test Test container\n\n* item 1\n")

        result = parser.parse_inventory(md_file)

        assert 'lang' not in result
        assert 'title' not in result
        assert len(result['containers']) == 1
