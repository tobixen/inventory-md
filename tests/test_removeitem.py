"""Tests for the `inventory-md remove` write path (removeitem module)."""

from __future__ import annotations

from pathlib import Path

import pytest

from inventory_md import removeitem

_MD = """# ID:box1 First box

* category:rice ID:rice-1 Rice 1kg
* category:peel-ply ID:peel-1 Peel ply
  * 83 g/m2 plain
  * 105 g/m2 twill
* category:pasta ID:pasta-1 qty:3 Pasta

# ID:box2 Second box

* category:milk ID:milk-1 Milk
"""


@pytest.fixture
def md_path(tmp_path: Path) -> Path:
    p = tmp_path / "inventory.md"
    p.write_text(_MD, encoding="utf-8")
    return p


def test_remove_item_deletes_line(md_path: Path):
    result = removeitem.remove_item(md_path, item_id="rice-1")
    assert result.errors == []
    assert result.written
    assert result.removed == ["* category:rice ID:rice-1 Rice 1kg"]
    assert result.from_container == "box1"
    text = md_path.read_text(encoding="utf-8")
    assert "rice-1" not in text
    assert text == _MD.replace("* category:rice ID:rice-1 Rice 1kg\n", "")


def test_remove_item_takes_subbullets_along(md_path: Path):
    result = removeitem.remove_item(md_path, item_id="peel-1")
    assert result.errors == []
    assert len(result.removed) == 3
    text = md_path.read_text(encoding="utf-8")
    assert "g/m2" not in text
    assert "* category:pasta ID:pasta-1 qty:3 Pasta" in text


def test_remove_item_unknown_errors_file_unchanged(md_path: Path):
    result = removeitem.remove_item(md_path, item_id="nope")
    assert result.errors
    assert not result.written
    assert md_path.read_text(encoding="utf-8") == _MD


def test_remove_item_duplicate_id_refused(md_path: Path):
    dup = _MD + "* category:rice ID:rice-1 Rice again\n"
    md_path.write_text(dup, encoding="utf-8")
    result = removeitem.remove_item(md_path, item_id="rice-1")
    assert result.errors
    assert "more than once" in result.errors[0]
    assert md_path.read_text(encoding="utf-8") == dup


def test_remove_item_qty_above_one_refused(md_path: Path):
    result = removeitem.remove_item(md_path, item_id="pasta-1")
    assert result.errors
    assert "qty" in result.errors[0]
    assert md_path.read_text(encoding="utf-8") == _MD


def test_remove_item_qty_above_one_with_all(md_path: Path):
    result = removeitem.remove_item(md_path, item_id="pasta-1", remove_all=True)
    assert result.errors == []
    assert "pasta-1" not in md_path.read_text(encoding="utf-8")


def test_remove_item_dry_run_leaves_file(md_path: Path):
    result = removeitem.remove_item(md_path, item_id="rice-1", dry_run=True)
    assert result.errors == []
    assert not result.written
    assert result.removed == ["* category:rice ID:rice-1 Rice 1kg"]
    assert md_path.read_text(encoding="utf-8") == _MD


_NESTED_MD = """# ID:cabin Cabin

* ID:cabin-sb Starboard side
  * ID:cabin-sb1 Storage behind artwork
    * category:shoes ID:shoes-1 Shoes
  * plain note without ID
* category:towel ID:towel-1 Towel
"""


def test_remove_item_refuses_nested_ids(tmp_path: Path):
    md = tmp_path / "inventory.md"
    md.write_text(_NESTED_MD, encoding="utf-8")
    result = removeitem.remove_item(md, item_id="cabin-sb")
    assert result.errors
    assert "cabin-sb1" in result.errors[0]
    assert "shoes-1" in result.errors[0]
    assert md.read_text(encoding="utf-8") == _NESTED_MD


def test_remove_item_leaf_under_bullet_container(tmp_path: Path):
    md = tmp_path / "inventory.md"
    md.write_text(_NESTED_MD, encoding="utf-8")
    result = removeitem.remove_item(md, item_id="shoes-1")
    assert result.errors == []
    assert md.read_text(encoding="utf-8") == _NESTED_MD.replace("    * category:shoes ID:shoes-1 Shoes\n", "")


@pytest.mark.parametrize("qty", ["4-5", "3pcs", "1.5"])
def test_remove_item_unclear_or_plural_qty_refused(md_path: Path, qty: str):
    text = _MD.replace("ID:rice-1", f"ID:rice-1 qty:{qty}")
    md_path.write_text(text, encoding="utf-8")
    result = removeitem.remove_item(md_path, item_id="rice-1")
    assert result.errors
    assert md_path.read_text(encoding="utf-8") == text


def test_remove_item_qty_one_allowed(md_path: Path):
    md_path.write_text(_MD.replace("ID:rice-1", "ID:rice-1 qty:1"), encoding="utf-8")
    assert removeitem.remove_item(md_path, item_id="rice-1").errors == []


def test_remove_item_qty_refused_also_in_dry_run(md_path: Path):
    result = removeitem.remove_item(md_path, item_id="pasta-1", dry_run=True)
    assert result.errors


def test_remove_item_last_line_without_trailing_newline(md_path: Path):
    md_path.write_text(_MD.rstrip("\n"), encoding="utf-8")
    result = removeitem.remove_item(md_path, item_id="milk-1")
    assert result.errors == []
    assert md_path.read_text(encoding="utf-8") == _MD.replace("\n* category:milk ID:milk-1 Milk\n", "")


def test_remove_item_heading_id_not_a_bullet(md_path: Path):
    result = removeitem.remove_item(md_path, item_id="box2")
    assert result.errors
    assert "not found as a bullet" in result.errors[0]
    assert md_path.read_text(encoding="utf-8") == _MD


def test_remove_item_missing_file(tmp_path: Path):
    result = removeitem.remove_item(tmp_path / "nope.md", item_id="rice-1")
    assert result.errors
    assert not result.written
