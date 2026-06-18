"""Tests for shopping_context (read-only situational-awareness helper)."""

import sys
from pathlib import Path

sys.path.insert(0, str(__file__).rsplit("/tests/", 1)[0] + "/scripts")
from shopping_context import (  # noqa: E402
    find_staging_files,
    grep_diary_lines,
    match_shop_osm,
    shop_of,
)


class TestMatchShopOsm:
    CACHE = {
        "Billa Varna": {"osm_type": "WAY", "osm_id": 1016681733},
        "Lidl Varna": {"osm_type": "WAY", "osm_id": 235500005},
    }

    def test_exact(self):
        assert match_shop_osm(self.CACHE, "Lidl Varna")["osm_id"] == 235500005

    def test_case_insensitive_substring(self):
        assert match_shop_osm(self.CACHE, "lidl")["osm_id"] == 235500005

    def test_no_match(self):
        assert match_shop_osm(self.CACHE, "Praktiker Varna") is None


class TestStagingFiles:
    def _make(self, tmp_path: Path):
        d = tmp_path / "staging"
        d.mkdir()
        (d / "shopping-2026-06-13-praktiker.yaml").write_text("shop: Praktiker Varna\n")
        (d / "shopping-2026-06-16.yaml").write_text("shop: Lidl Varna\n")
        (d / "shopping-2026-06-18-praktiker.yaml").write_text("shop: Praktiker Varna\n")
        (d / "off-products-2026-06-16.yaml").write_text("products: []\n")
        return d

    def test_shop_of_reads_field(self, tmp_path):
        d = self._make(tmp_path)
        assert shop_of(d / "shopping-2026-06-16.yaml") == "Lidl Varna"

    def test_filters_by_shop_newest_first(self, tmp_path):
        d = self._make(tmp_path)
        files = find_staging_files(d, "praktiker", limit=5)
        names = [f.name for f in files]
        assert names == [
            "shopping-2026-06-18-praktiker.yaml",
            "shopping-2026-06-13-praktiker.yaml",
        ]

    def test_limit_respected(self, tmp_path):
        d = self._make(tmp_path)
        assert len(find_staging_files(d, "praktiker", limit=1)) == 1

    def test_no_shop_returns_all_shopping(self, tmp_path):
        d = self._make(tmp_path)
        files = find_staging_files(d, None, limit=10)
        # off-products-* is not a shopping file
        assert all(f.name.startswith("shopping-") for f in files)
        assert len(files) == 3


class TestGrepDiary:
    DIARY = """\
* EUR 19.75 - maintenance - Praktiker Varna (paint brushes)
* EUR 28.32 - food - Lidl Varna (groceries)
* EUR 25.50 - maintenance - Praktiker Varna (thinner, scissors)
"""

    def test_matches_shop_lines(self):
        lines = grep_diary_lines(self.DIARY, "Praktiker")
        assert len(lines) == 2
        assert all("Praktiker" in line for line in lines)

    def test_case_insensitive(self):
        assert len(grep_diary_lines(self.DIARY, "lidl")) == 1

    def test_empty_when_no_match(self):
        assert grep_diary_lines(self.DIARY, "Decathlon") == []
