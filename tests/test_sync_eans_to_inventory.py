"""Tests for sync_eans_to_inventory.py — verifies deduplication from extract_barcodes."""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import sync_eans_to_inventory as sync  # noqa: E402


class TestNoDuplicatedFunctions:
    """The functions that were duplicates of extract_barcodes.py must be gone."""

    def test_extract_barcodes_from_image_not_defined(self):
        assert not hasattr(sync, "extract_barcodes_from_image"), (
            "extract_barcodes_from_image is a duplicate of extract_barcodes.extract_barcodes — should be removed"
        )

    def test_is_ean_is_the_canonical_one(self):
        import extract_barcodes as eb

        # is_ean may be imported into the namespace, but must be the same object
        # (i.e., no locally-defined copy with the missing checksum validation)
        if hasattr(sync, "is_ean"):
            assert sync.is_ean is eb.is_ean, "sync.is_ean must be extract_barcodes.is_ean, not a local copy"

    def test_lookup_ean_not_defined(self):
        assert not hasattr(sync, "lookup_ean"), (
            "lookup_ean queried OFF directly — should use lookup_tingbok from extract_barcodes"
        )


class TestExtractBarcodesFromDirectory:
    """extract_barcodes_from_directory must delegate to extract_barcodes.extract_barcodes."""

    def test_uses_extract_barcodes_from_module(self, tmp_path):
        import extract_barcodes as eb

        fake_barcode = {"type": "EAN13", "data": "5700000000000", "polygon": None}
        (tmp_path / "test.jpg").write_bytes(b"fake")

        with patch.object(eb, "extract_barcodes", return_value=[fake_barcode]) as mock_extract:
            result = sync.extract_barcodes_from_directory(tmp_path)

        mock_extract.assert_called_once()
        assert len(result) == 1
        assert result[0]["data"] == "5700000000000"


class TestGetExistingEans:
    def test_finds_ean_from_metadata(self):
        data = {
            "containers": [
                {
                    "id": "BOX1",
                    "items": [{"metadata": {"ean": "1234567890123"}}],
                }
            ]
        }
        eans = sync.get_existing_eans(data, "BOX1")
        assert "1234567890123" in eans

    def test_finds_ean_from_raw_text(self):
        data = {
            "containers": [
                {
                    "id": "BOX1",
                    "items": [{"raw_text": "EAN:9876543210987 some item", "metadata": {}}],
                }
            ]
        }
        eans = sync.get_existing_eans(data, "BOX1")
        assert "9876543210987" in eans
