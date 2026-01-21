"""Tests for photo_registry module."""
from inventory_md import photo_registry


class TestParsePhotoRegistry:
    """Tests for parse_photo_registry function."""

    def test_parse_empty_file(self, tmp_path):
        """Test parsing an empty file."""
        registry_file = tmp_path / "photo-registry.md"
        registry_file.write_text("")

        result = photo_registry.parse_photo_registry(registry_file)

        assert result["photos"] == {}
        assert result["items"] == {}
        assert result["containers"] == {}

    def test_parse_nonexistent_file(self, tmp_path):
        """Test parsing a file that doesn't exist."""
        registry_file = tmp_path / "nonexistent.md"

        result = photo_registry.parse_photo_registry(registry_file)

        assert result["photos"] == {}
        assert result["items"] == {}
        assert result["containers"] == {}

    def test_parse_basic_registry(self, tmp_path):
        """Test parsing a basic registry with one session and container."""
        registry_file = tmp_path / "photo-registry.md"
        registry_file.write_text("""# Photo-Item Registry

## Session: 2026-01-03

### TB-03

| Photo | Item IDs |
|-------|----------|
| IMG_001.jpg | ID:drill-bosch |
| IMG_002.jpg | ID:wrench-force17, ID:drill-bosch |
| IMG_003.jpg | (overview) |
""")

        result = photo_registry.parse_photo_registry(registry_file)

        # Check photos
        assert "IMG_001.jpg" in result["photos"]
        assert result["photos"]["IMG_001.jpg"]["items"] == ["drill-bosch"]
        assert result["photos"]["IMG_001.jpg"]["container"] == "TB-03"
        assert result["photos"]["IMG_001.jpg"]["session"] == "2026-01-03"

        assert "IMG_002.jpg" in result["photos"]
        assert result["photos"]["IMG_002.jpg"]["items"] == ["wrench-force17", "drill-bosch"]

        assert "IMG_003.jpg" in result["photos"]
        assert result["photos"]["IMG_003.jpg"]["items"] == []
        assert result["photos"]["IMG_003.jpg"]["notes"] == "overview"

        # Check items reverse index
        assert "drill-bosch" in result["items"]
        assert set(result["items"]["drill-bosch"]) == {"IMG_001.jpg", "IMG_002.jpg"}

        assert "wrench-force17" in result["items"]
        assert result["items"]["wrench-force17"] == ["IMG_002.jpg"]

        # Check containers
        assert "TB-03" in result["containers"]
        assert len(result["containers"]["TB-03"]) == 3

    def test_parse_multiple_sessions(self, tmp_path):
        """Test parsing registry with multiple sessions."""
        registry_file = tmp_path / "photo-registry.md"
        registry_file.write_text("""# Photo-Item Registry

## Session: 2026-01-03

### BOX-A

| Photo | Item IDs |
|-------|----------|
| IMG_001.jpg | ID:item-a |

## Session: 2026-01-04

### BOX-A

| Photo | Item IDs |
|-------|----------|
| IMG_002.jpg | ID:item-b |
""")

        result = photo_registry.parse_photo_registry(registry_file)

        assert result["photos"]["IMG_001.jpg"]["session"] == "2026-01-03"
        assert result["photos"]["IMG_002.jpg"]["session"] == "2026-01-04"

    def test_parse_multiple_containers(self, tmp_path):
        """Test parsing registry with multiple containers."""
        registry_file = tmp_path / "photo-registry.md"
        registry_file.write_text("""# Photo-Item Registry

## Session: 2026-01-03

### BOX-A

| Photo | Item IDs |
|-------|----------|
| IMG_001.jpg | ID:item-a |

### BOX-B

| Photo | Item IDs |
|-------|----------|
| IMG_002.jpg | ID:item-b |
""")

        result = photo_registry.parse_photo_registry(registry_file)

        assert result["photos"]["IMG_001.jpg"]["container"] == "BOX-A"
        assert result["photos"]["IMG_002.jpg"]["container"] == "BOX-B"
        assert "BOX-A" in result["containers"]
        assert "BOX-B" in result["containers"]

    def test_parse_notes_with_items(self, tmp_path):
        """Test parsing items with notes in parentheses."""
        registry_file = tmp_path / "photo-registry.md"
        registry_file.write_text("""# Photo-Item Registry

## Session: 2026-01-03

### food3

| Photo | Item IDs |
|-------|----------|
| IMG_001.jpg | ID:tea-caykur (best-before: 2028-10-04) |
| IMG_002.jpg | (blurry) |
| IMG_003.jpg | ID:item-a, ID:item-b (overview) |
""")

        result = photo_registry.parse_photo_registry(registry_file)

        assert result["photos"]["IMG_001.jpg"]["items"] == ["tea-caykur"]
        assert result["photos"]["IMG_001.jpg"]["notes"] == "best-before: 2028-10-04"

        assert result["photos"]["IMG_002.jpg"]["items"] == []
        assert result["photos"]["IMG_002.jpg"]["notes"] == "blurry"

        assert result["photos"]["IMG_003.jpg"]["items"] == ["item-a", "item-b"]
        assert result["photos"]["IMG_003.jpg"]["notes"] == "overview"

    def test_item_ids_lowercase(self, tmp_path):
        """Test that item IDs are normalized to lowercase."""
        registry_file = tmp_path / "photo-registry.md"
        registry_file.write_text("""# Photo-Item Registry

## Session: 2026-01-03

### BOX-A

| Photo | Item IDs |
|-------|----------|
| IMG_001.jpg | ID:Drill-BOSCH, ID:WRENCH-Force17 |
""")

        result = photo_registry.parse_photo_registry(registry_file)

        assert result["photos"]["IMG_001.jpg"]["items"] == ["drill-bosch", "wrench-force17"]
        assert "drill-bosch" in result["items"]
        assert "wrench-force17" in result["items"]


class TestIsPhotoFilename:
    """Tests for _is_photo_filename function."""

    def test_valid_extensions(self):
        """Test valid photo extensions."""
        assert photo_registry._is_photo_filename("IMG_001.jpg")
        assert photo_registry._is_photo_filename("photo.jpeg")
        assert photo_registry._is_photo_filename("image.png")
        assert photo_registry._is_photo_filename("pic.gif")
        assert photo_registry._is_photo_filename("shot.heic")
        assert photo_registry._is_photo_filename("web.webp")
        assert photo_registry._is_photo_filename("PHOTO.JPG")

    def test_invalid_extensions(self):
        """Test invalid extensions."""
        assert not photo_registry._is_photo_filename("document.pdf")
        assert not photo_registry._is_photo_filename("file.txt")
        assert not photo_registry._is_photo_filename("Photo")
        assert not photo_registry._is_photo_filename("-------")


class TestParseItemsCell:
    """Tests for _parse_items_cell function."""

    def test_single_item(self):
        """Test parsing single item."""
        items, notes = photo_registry._parse_items_cell("ID:drill-bosch")
        assert items == ["drill-bosch"]
        assert notes is None

    def test_multiple_items(self):
        """Test parsing multiple items."""
        items, notes = photo_registry._parse_items_cell("ID:drill-bosch, ID:wrench-force17")
        assert items == ["drill-bosch", "wrench-force17"]
        assert notes is None

    def test_note_only(self):
        """Test parsing note only."""
        items, notes = photo_registry._parse_items_cell("(overview)")
        assert items == []
        assert notes == "overview"

    def test_items_with_notes(self):
        """Test parsing items with notes."""
        items, notes = photo_registry._parse_items_cell("ID:item-a (best-before: 2026)")
        assert items == ["item-a"]
        assert notes == "best-before: 2026"

    def test_empty_cell(self):
        """Test parsing empty cell."""
        items, notes = photo_registry._parse_items_cell("")
        assert items == []
        assert notes is None


class TestGetPhotosForItems:
    """Tests for get_photos_for_items function."""

    def test_single_item(self):
        """Test getting photos for a single item."""
        registry = {
            "photos": {
                "IMG_001.jpg": {"container": "BOX-A", "items": ["item-a"]},
                "IMG_002.jpg": {"container": "BOX-A", "items": ["item-a", "item-b"]},
            },
            "items": {
                "item-a": ["IMG_001.jpg", "IMG_002.jpg"],
                "item-b": ["IMG_002.jpg"],
            },
        }

        result = photo_registry.get_photos_for_items(registry, ["item-a"])

        assert len(result) == 2
        filenames = [r["filename"] for r in result]
        assert "IMG_001.jpg" in filenames
        assert "IMG_002.jpg" in filenames

    def test_multiple_items(self):
        """Test getting photos for multiple items."""
        registry = {
            "photos": {
                "IMG_001.jpg": {"container": "BOX-A", "items": ["item-a"]},
                "IMG_002.jpg": {"container": "BOX-A", "items": ["item-b"]},
            },
            "items": {
                "item-a": ["IMG_001.jpg"],
                "item-b": ["IMG_002.jpg"],
            },
        }

        result = photo_registry.get_photos_for_items(registry, ["item-a", "item-b"])

        assert len(result) == 2

    def test_no_duplicates(self):
        """Test that shared photos are not duplicated."""
        registry = {
            "photos": {
                "IMG_001.jpg": {"container": "BOX-A", "items": ["item-a", "item-b"]},
            },
            "items": {
                "item-a": ["IMG_001.jpg"],
                "item-b": ["IMG_001.jpg"],
            },
        }

        result = photo_registry.get_photos_for_items(registry, ["item-a", "item-b"])

        assert len(result) == 1

    def test_nonexistent_item(self):
        """Test getting photos for nonexistent item."""
        registry = {"photos": {}, "items": {}}

        result = photo_registry.get_photos_for_items(registry, ["nonexistent"])

        assert len(result) == 0


class TestGetItemPhotoCount:
    """Tests for get_item_photo_count function."""

    def test_photo_count(self):
        """Test getting photo count per item."""
        registry = {
            "items": {
                "item-a": ["IMG_001.jpg", "IMG_002.jpg"],
                "item-b": ["IMG_003.jpg"],
            },
        }

        result = photo_registry.get_item_photo_count(registry)

        assert result["item-a"] == 2
        assert result["item-b"] == 1

    def test_empty_registry(self):
        """Test with empty registry."""
        result = photo_registry.get_item_photo_count({"items": {}})
        assert result == {}
