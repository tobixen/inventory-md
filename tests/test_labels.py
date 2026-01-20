"""Tests for labels module."""
import pytest

from inventory_md import labels


class TestValidateLabelId:
    """Tests for validate_label_id function."""

    def test_valid_ids(self):
        """Test valid label IDs."""
        assert labels.validate_label_id("AA0") is True
        assert labels.validate_label_id("ZZ9") is True
        assert labels.validate_label_id("AB5") is True
        assert labels.validate_label_id("CA3") is True

    def test_valid_ids_lowercase(self):
        """Test that lowercase IDs are accepted (normalized internally)."""
        assert labels.validate_label_id("aa0") is True
        assert labels.validate_label_id("Ab5") is True

    def test_invalid_ids_wrong_length(self):
        """Test invalid IDs with wrong length."""
        assert labels.validate_label_id("A0") is False
        assert labels.validate_label_id("AAAA") is False
        assert labels.validate_label_id("AA") is False
        assert labels.validate_label_id("") is False

    def test_invalid_ids_wrong_format(self):
        """Test invalid IDs with wrong character types."""
        assert labels.validate_label_id("AAA") is False  # No digit
        assert labels.validate_label_id("A00") is False  # Two digits
        assert labels.validate_label_id("1A0") is False  # Digit first
        assert labels.validate_label_id("A10") is False  # Two digits

    def test_invalid_ids_non_string(self):
        """Test invalid non-string inputs."""
        assert labels.validate_label_id(None) is False
        assert labels.validate_label_id(123) is False
        assert labels.validate_label_id(["AA0"]) is False


class TestNextId:
    """Tests for next_id function."""

    def test_increment_digit(self):
        """Test incrementing the digit."""
        assert labels.next_id("AA0") == "AA1"
        assert labels.next_id("AA8") == "AA9"
        assert labels.next_id("ZZ0") == "ZZ1"

    def test_increment_letter(self):
        """Test rolling over digit to increment letter."""
        assert labels.next_id("AA9") == "AB0"
        assert labels.next_id("AB9") == "AC0"
        assert labels.next_id("AY9") == "AZ0"

    def test_series_exhausted(self):
        """Test that series exhaustion raises ValueError."""
        with pytest.raises(ValueError, match="Series A exhausted"):
            labels.next_id("AZ9")
        with pytest.raises(ValueError, match="Series B exhausted"):
            labels.next_id("BZ9")

    def test_lowercase_input(self):
        """Test that lowercase input works."""
        assert labels.next_id("aa0") == "AA1"
        assert labels.next_id("ab9") == "AC0"

    def test_invalid_input(self):
        """Test that invalid input raises ValueError."""
        with pytest.raises(ValueError, match="Invalid label ID"):
            labels.next_id("invalid")
        with pytest.raises(ValueError, match="Invalid label ID"):
            labels.next_id("A0")


class TestGenerateIdSequence:
    """Tests for generate_id_sequence function."""

    def test_series_start(self):
        """Test generating from series."""
        result = labels.generate_id_sequence(series="A", count=3)
        assert result == ["AA0", "AA1", "AA2"]

    def test_series_start_lowercase(self):
        """Test series with lowercase input."""
        result = labels.generate_id_sequence(series="b", count=2)
        assert result == ["BA0", "BA1"]

    def test_start_id(self):
        """Test generating from specific start ID."""
        result = labels.generate_id_sequence(start="AB5", count=3)
        assert result == ["AB5", "AB6", "AB7"]

    def test_start_id_rollover(self):
        """Test sequence that rolls over to next letter."""
        result = labels.generate_id_sequence(start="AA8", count=4)
        assert result == ["AA8", "AA9", "AB0", "AB1"]

    def test_single_id(self):
        """Test generating single ID."""
        result = labels.generate_id_sequence(series="C", count=1)
        assert result == ["CA0"]

    def test_no_args_raises(self):
        """Test that no args raises ValueError."""
        with pytest.raises(ValueError, match="Must provide either series or start"):
            labels.generate_id_sequence(count=5)

    def test_invalid_series(self):
        """Test invalid series raises ValueError."""
        with pytest.raises(ValueError, match="Series must be a single letter"):
            labels.generate_id_sequence(series="AB", count=1)
        with pytest.raises(ValueError, match="Series must be a single letter"):
            labels.generate_id_sequence(series="1", count=1)

    def test_invalid_start(self):
        """Test invalid start ID raises ValueError."""
        with pytest.raises(ValueError, match="Invalid start ID"):
            labels.generate_id_sequence(start="invalid", count=1)

    def test_invalid_count(self):
        """Test invalid count raises ValueError."""
        with pytest.raises(ValueError, match="Count must be at least 1"):
            labels.generate_id_sequence(series="A", count=0)
        with pytest.raises(ValueError, match="Count must be at least 1"):
            labels.generate_id_sequence(series="A", count=-1)

    def test_series_exhaustion(self):
        """Test that generating too many IDs raises ValueError."""
        with pytest.raises(ValueError, match="exhausted"):
            labels.generate_id_sequence(start="AZ8", count=5)


class TestGenerateQr:
    """Tests for generate_qr function."""

    def test_qr_generated(self):
        """Test that QR code is generated."""
        img = labels.generate_qr("https://example.com/test")
        assert img is not None
        assert img.size[0] > 0
        assert img.size[1] > 0

    def test_qr_box_size(self):
        """Test that box_size affects image size."""
        img_small = labels.generate_qr("https://example.com/test", box_size=5)
        img_large = labels.generate_qr("https://example.com/test", box_size=20)
        assert img_large.size[0] > img_small.size[0]


class TestGenerateLabel:
    """Tests for generate_label function."""

    def test_standard_label(self):
        """Test generating standard label."""
        img = labels.generate_label(
            "AA0",
            "https://example.com/search.html",
            style="standard",
        )
        assert img is not None
        assert img.mode == "RGB"
        # Check dimensions are reasonable for 48.5x25.4mm at 300dpi
        assert img.size[0] > 500  # ~573px
        assert img.size[1] > 200  # ~300px

    def test_compact_label(self):
        """Test generating compact label."""
        img = labels.generate_label(
            "BB5",
            "https://example.com/search.html",
            style="compact",
        )
        assert img is not None
        assert img.mode == "RGB"

    def test_duplicate_label(self):
        """Test generating duplicate QR label."""
        img = labels.generate_label(
            "CC9",
            "https://example.com/search.html",
            style="duplicate",
        )
        assert img is not None
        assert img.mode == "RGB"

    def test_custom_dimensions(self):
        """Test generating label with custom dimensions."""
        img = labels.generate_label(
            "AA0",
            "https://example.com/search.html",
            width_mm=70,
            height_mm=36,
        )
        # Check dimensions are reasonable for 70x36mm at 300dpi
        assert img.size[0] > 800  # ~827px
        assert img.size[1] > 400  # ~425px

    def test_custom_date(self):
        """Test generating label with custom date."""
        img = labels.generate_label(
            "AA0",
            "https://example.com/search.html",
            label_date="2024-06-15",
        )
        assert img is not None


class TestGetSheetFormat:
    """Tests for get_sheet_format function."""

    def test_builtin_format(self):
        """Test getting built-in format."""
        fmt = labels.get_sheet_format("48x25-40")
        assert fmt["cols"] == 4
        assert fmt["rows"] == 10
        assert fmt["label_width_mm"] == 48.5
        assert fmt["label_height_mm"] == 25.4

    def test_custom_format(self):
        """Test getting custom format from config."""
        custom = {
            "my-labels": {
                "cols": 2,
                "rows": 5,
                "label_width_mm": 100,
                "label_height_mm": 50,
                "page_width_mm": 210,
                "page_height_mm": 297,
                "margin_top_mm": 10,
                "margin_left_mm": 5,
            }
        }
        fmt = labels.get_sheet_format("my-labels", custom_formats=custom)
        assert fmt["cols"] == 2
        assert fmt["rows"] == 5

    def test_custom_overrides_builtin(self):
        """Test that custom format overrides built-in."""
        custom = {
            "48x25-40": {
                "cols": 8,
                "rows": 20,
                "label_width_mm": 24.25,
                "label_height_mm": 12.7,
                "page_width_mm": 210,
                "page_height_mm": 297,
                "margin_top_mm": 6.5,
                "margin_left_mm": 2,
            }
        }
        fmt = labels.get_sheet_format("48x25-40", custom_formats=custom)
        assert fmt["cols"] == 8  # Custom, not built-in

    def test_unknown_format_raises(self):
        """Test that unknown format raises ValueError."""
        with pytest.raises(ValueError, match="Unknown sheet format"):
            labels.get_sheet_format("nonexistent")


class TestCreateLabelSheet:
    """Tests for create_label_sheet function."""

    def test_pdf_created(self):
        """Test that PDF is created."""
        pdf_bytes = labels.create_label_sheet(
            ["AA0", "AA1", "AA2"],
            "https://example.com/search.html",
        )
        assert pdf_bytes is not None
        assert len(pdf_bytes) > 0
        # Check PDF magic bytes
        assert pdf_bytes[:4] == b"%PDF"

    def test_pdf_multiple_pages(self):
        """Test PDF with multiple pages."""
        # Generate more labels than fit on one page (40 per page for 48x25-40)
        label_ids = labels.generate_id_sequence(series="A", count=50)
        pdf_bytes = labels.create_label_sheet(
            label_ids,
            "https://example.com/search.html",
        )
        assert pdf_bytes is not None
        assert len(pdf_bytes) > 0

    def test_pdf_with_style(self):
        """Test PDF with different styles."""
        for style in ["standard", "compact", "duplicate"]:
            pdf_bytes = labels.create_label_sheet(
                ["AA0", "AA1"],
                "https://example.com/search.html",
                style=style,
            )
            assert pdf_bytes[:4] == b"%PDF"


class TestSaveLabelsAsPng:
    """Tests for save_labels_as_png function."""

    def test_png_files_created(self, tmp_path):
        """Test that PNG files are created."""
        output_dir = tmp_path / "labels"
        created = labels.save_labels_as_png(
            ["AA0", "AA1", "AA2"],
            "https://example.com/search.html",
            str(output_dir),
        )
        assert len(created) == 3
        assert (output_dir / "AA0.png").exists()
        assert (output_dir / "AA1.png").exists()
        assert (output_dir / "AA2.png").exists()

    def test_png_creates_directory(self, tmp_path):
        """Test that output directory is created."""
        output_dir = tmp_path / "nested" / "labels"
        labels.save_labels_as_png(
            ["AA0"],
            "https://example.com/search.html",
            str(output_dir),
        )
        assert output_dir.exists()


class TestListFormats:
    """Tests for list_formats function."""

    def test_builtin_formats(self):
        """Test listing built-in formats."""
        formats = labels.list_formats()
        assert len(formats) > 0
        names = [f[0] for f in formats]
        assert "48x25-40" in names
        assert "70x36-24" in names

    def test_custom_formats_included(self):
        """Test that custom formats are included."""
        custom = {
            "my-format": {
                "cols": 2,
                "rows": 4,
                "description": "My custom format",
            }
        }
        formats = labels.list_formats(custom_formats=custom)
        names = [f[0] for f in formats]
        assert "my-format" in names


class TestSheetFormats:
    """Tests for SHEET_FORMATS constants."""

    def test_all_formats_have_required_keys(self):
        """Test that all formats have required keys."""
        required_keys = [
            "cols", "rows",
            "label_width_mm", "label_height_mm",
            "page_width_mm", "page_height_mm",
            "margin_top_mm", "margin_left_mm",
        ]
        for name, fmt in labels.SHEET_FORMATS.items():
            for key in required_keys:
                assert key in fmt, f"Format {name} missing key {key}"

    def test_all_formats_have_positive_values(self):
        """Test that all format values are positive."""
        for name, fmt in labels.SHEET_FORMATS.items():
            assert fmt["cols"] > 0, f"{name}: cols must be positive"
            assert fmt["rows"] > 0, f"{name}: rows must be positive"
            assert fmt["label_width_mm"] > 0, f"{name}: label_width_mm must be positive"
            assert fmt["label_height_mm"] > 0, f"{name}: label_height_mm must be positive"
            assert fmt["page_width_mm"] > 0, f"{name}: page_width_mm must be positive"
            assert fmt["page_height_mm"] > 0, f"{name}: page_height_mm must be positive"
            assert fmt["margin_top_mm"] >= 0, f"{name}: margin_top_mm must be non-negative"
            assert fmt["margin_left_mm"] >= 0, f"{name}: margin_left_mm must be non-negative"
