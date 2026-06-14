"""Tests for the `inventory-md add` write path (additem module)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from inventory_md import additem

# --- format_item_line -------------------------------------------------------


def test_format_item_line_minimal():
    line = additem.format_item_line("milk", "milk-2026-06-14")
    assert line == "* category:milk ID:milk-2026-06-14"


def test_format_item_line_full_field_order():
    line = additem.format_item_line(
        "milk",
        "milk-1",
        ean="7038010000000",
        bb="2026-07",
        bb_est=False,
        qty=2,
        mass="1000g",
        volume="1l",
        price="EUR:1.29/pcs",
        tags=["condition:new"],
        name="Whole milk 1l",
    )
    # category, ID, tag, EAN, bb, qty, mass, volume, price, then name last
    assert line == (
        "* category:milk ID:milk-1 tag:condition:new EAN:7038010000000 "
        "bb:2026-07 qty:2 mass:1000g volume:1l price:EUR:1.29/pcs Whole milk 1l"
    )


def test_format_item_line_bb_est_appends_flag():
    line = additem.format_item_line("potatoes", "potatoes-1", bb="2026-09", bb_est=True, name="Potatoes")
    assert "bb:2026-09:EST" in line
    assert line.endswith("Potatoes")


def test_format_item_line_lowercases_category():
    line = additem.format_item_line("Food/Vegetables/Potatoes", "p1")
    assert "category:food/vegetables/potatoes" in line


def test_format_item_line_multiple_categories_preserved():
    line = additem.format_item_line("oatmeal,breakfast", "oats-1")
    assert "category:oatmeal,breakfast" in line


# --- validate_bb_format -----------------------------------------------------


@pytest.mark.parametrize("bb", ["2026", "2026-07", "2026-07-15", "2026-07-15T08:30"])
def test_validate_bb_format_accepts(bb):
    assert additem.validate_bb_format(bb) is True


@pytest.mark.parametrize("bb", ["july", "2026/07", "26-07", "2026-13-40x"])
def test_validate_bb_format_rejects(bb):
    assert additem.validate_bb_format(bb) is False


# --- collect_existing_ids ---------------------------------------------------


def test_collect_existing_ids_includes_containers_and_items():
    data = {
        "containers": [
            {"id": "food1", "items": [{"id": "milk-1"}, {"id": None}, {"id": "eggs-1"}]},
            {"id": "food2", "items": []},
        ]
    }
    assert additem.collect_existing_ids(data) == {"food1", "food2", "milk-1", "eggs-1"}


# --- generate_item_id -------------------------------------------------------


def test_generate_item_id_food_appends_date():
    item_id = additem.generate_item_id("milk", "Whole milk 1l", set(), is_food=True, today=date(2026, 6, 14))
    assert item_id == "milk-2026-06-14"


def test_generate_item_id_nonfood_no_date():
    item_id = additem.generate_item_id("hammer", "Bosch hammer", set(), is_food=False)
    assert item_id == "hammer"


def test_generate_item_id_avoids_collision():
    existing = {"milk-2026-06-14"}
    item_id = additem.generate_item_id("milk", "milk", existing, is_food=True, today=date(2026, 6, 14))
    assert item_id == "milk-2026-06-14-2"


# --- insert_item_line -------------------------------------------------------

_MD = """# Intro

Demo

# ID:food1 Pantry

Some text.

* category:rice ID:rice-1 bb:2027-01 Rice 1kg
* category:pasta ID:pasta-1 bb:2027-03 Pasta

# ID:food2 Fridge

* category:milk ID:milk-old bb:2026-06 Milk
"""


def test_insert_item_line_after_last_bullet():
    lines = _MD.splitlines()
    new = additem.insert_item_line(lines, "food1", "* category:beans ID:beans-1 bb:2028-01 Beans")
    text = "\n".join(new)
    # inserted into food1, right after pasta line, before the food2 heading
    food1_block = text.split("# ID:food2")[0]
    assert "* category:beans ID:beans-1 bb:2028-01 Beans" in food1_block
    # order preserved: beans comes after pasta
    assert food1_block.index("pasta-1") < food1_block.index("beans-1")


def test_insert_item_line_unknown_container_raises():
    lines = _MD.splitlines()
    with pytest.raises(ValueError, match="nope"):
        additem.insert_item_line(lines, "nope", "* category:x ID:x")


def test_insert_item_line_empty_container():
    md = "# ID:empty Empty container\n\nNo items yet.\n"
    lines = md.splitlines()
    new = additem.insert_item_line(lines, "empty", "* category:milk ID:m1")
    assert "* category:milk ID:m1" in new


# --- end-to-end command -----------------------------------------------------


@pytest.fixture
def inventory_dir(tmp_path: Path) -> Path:
    """A minimal inventory.md + vocabulary.json copied from the example."""
    (tmp_path / "inventory.md").write_text(_MD, encoding="utf-8")
    example_vocab = Path(__file__).parent.parent / "example" / "vocabulary.json"
    (tmp_path / "vocabulary.json").write_text(example_vocab.read_text(encoding="utf-8"), encoding="utf-8")
    return tmp_path


def test_add_item_writes_line(inventory_dir: Path):
    md_path = inventory_dir / "inventory.md"
    result = additem.add_item(
        md_path,
        container_id="food1",
        category="milk",
        item_id="milk-new",
        bb="2026-07",
        name="Fresh milk",
    )
    assert not result.errors
    text = md_path.read_text(encoding="utf-8")
    assert "ID:milk-new" in text
    assert result.item_line in text


def test_add_item_rejects_duplicate_id(inventory_dir: Path):
    md_path = inventory_dir / "inventory.md"
    result = additem.add_item(
        md_path,
        container_id="food1",
        category="milk",
        item_id="rice-1",  # already present
        bb="2026-07",
    )
    assert any("rice-1" in e for e in result.errors)
    # file unchanged
    assert md_path.read_text(encoding="utf-8") == _MD


def test_add_item_food_without_bb_is_error(inventory_dir: Path):
    md_path = inventory_dir / "inventory.md"
    result = additem.add_item(
        md_path,
        container_id="food1",
        category="milk",
        item_id="milk-x",
    )
    assert any("bb" in e.lower() for e in result.errors)
    assert "milk-x" not in md_path.read_text(encoding="utf-8")


def test_add_item_food_without_bb_allowed_with_flag(inventory_dir: Path):
    md_path = inventory_dir / "inventory.md"
    result = additem.add_item(
        md_path,
        container_id="food1",
        category="milk",
        item_id="milk-x",
        check_bb=False,
    )
    assert not result.errors
    assert "milk-x" in md_path.read_text(encoding="utf-8")


def test_add_item_nonfood_without_bb_ok(inventory_dir: Path):
    md_path = inventory_dir / "inventory.md"
    result = additem.add_item(
        md_path,
        container_id="food1",
        category="hammer",
        item_id="hammer-1",
        name="A hammer in the pantry, weird but valid",
    )
    assert not result.errors
    assert "hammer-1" in md_path.read_text(encoding="utf-8")


def test_add_item_unknown_category_warns(inventory_dir: Path):
    md_path = inventory_dir / "inventory.md"
    result = additem.add_item(
        md_path,
        container_id="food1",
        category="zzznotacategory",
        item_id="weird-1",
        name="Mystery",
    )
    assert not result.errors  # warning, not error
    assert any("zzznotacategory" in w for w in result.warnings)
    assert "weird-1" in md_path.read_text(encoding="utf-8")


def test_add_item_unknown_category_strict_errors(inventory_dir: Path):
    md_path = inventory_dir / "inventory.md"
    result = additem.add_item(
        md_path,
        container_id="food1",
        category="zzznotacategory",
        item_id="weird-1",
        name="Mystery",
        strict=True,
    )
    assert any("zzznotacategory" in e for e in result.errors)
    assert "weird-1" not in md_path.read_text(encoding="utf-8")


def test_add_item_autogenerates_id_for_food(inventory_dir: Path):
    md_path = inventory_dir / "inventory.md"
    result = additem.add_item(
        md_path,
        container_id="food1",
        category="milk",
        bb="2026-07",
        name="Some milk",
        today=date(2026, 6, 14),
    )
    assert not result.errors
    assert result.item_id == "milk-2026-06-14"
    assert "ID:milk-2026-06-14" in md_path.read_text(encoding="utf-8")


def test_add_item_unknown_container_errors(inventory_dir: Path):
    md_path = inventory_dir / "inventory.md"
    result = additem.add_item(
        md_path,
        container_id="does-not-exist",
        category="milk",
        item_id="m1",
        bb="2026-07",
    )
    assert any("does-not-exist" in e for e in result.errors)
