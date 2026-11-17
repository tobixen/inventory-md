"""Tests for the `inventory-md edit` write path (edititem module)."""

from __future__ import annotations

from pathlib import Path

import pytest

from inventory_md import edititem

_MD = """# Intro

Demo

# ID:box1 First box

* category:rice ID:rice-1 EAN:7038010000000 bb:2027-01 qty:2 Rice 1kg
* category:peel-ply ID:peel-1 Peel ply
  * 83 g/m2 plain
  * 105 g/m2 twill
* category:milk ID:milk-1 bb:2026-07 Whole milk

# ID:box2 Second box

* category:hammer ID:hammer-1 A hammer
"""


# --- rewrite_item_line ------------------------------------------------------


def test_rewrite_replaces_existing_field_in_place():
    line = "* category:rice ID:rice-1 EAN:7038010000000 bb:2027-01 qty:2 Rice 1kg"
    out = edititem.rewrite_item_line(line, {"ean": "1234567890123"})
    assert out == "* category:rice ID:rice-1 EAN:1234567890123 bb:2027-01 qty:2 Rice 1kg"


def test_rewrite_inserts_missing_field_in_canonical_position():
    line = "* category:rice ID:rice-1 EAN:7038010000000 qty:2 Rice 1kg"
    out = edititem.rewrite_item_line(line, {"bb": "2027-01"})
    # bb sits between EAN and qty, and the name stays last
    assert out == "* category:rice ID:rice-1 EAN:7038010000000 bb:2027-01 qty:2 Rice 1kg"


def test_rewrite_appends_field_after_last_when_none_follow():
    line = "* category:rice ID:rice-1 Rice 1kg"
    out = edititem.rewrite_item_line(line, {"price": "EUR:1.29/pcs"})
    assert out == "* category:rice ID:rice-1 price:EUR:1.29/pcs Rice 1kg"


def test_rewrite_removes_field_with_empty_value():
    line = "* category:rice ID:rice-1 EAN:7038010000000 qty:2 Rice 1kg"
    out = edititem.rewrite_item_line(line, {"qty": None})
    assert out == "* category:rice ID:rice-1 EAN:7038010000000 Rice 1kg"


def test_rewrite_removing_absent_field_is_a_noop():
    line = "* category:rice ID:rice-1 Rice 1kg"
    assert edititem.rewrite_item_line(line, {"qty": None}) == line


def test_rewrite_preserves_indentation_and_bullet_marker():
    line = "  - category:rice ID:rice-1 Rice 1kg"
    out = edititem.rewrite_item_line(line, {"qty": "3"})
    assert out.startswith("  - category:rice ID:rice-1 qty:3 ")


def test_rewrite_name_replaces_trailing_text_only():
    line = "* category:rice ID:rice-1 qty:2 Rice 1kg"
    out = edititem.rewrite_item_line(line, {}, name="Basmati rice")
    assert out == "* category:rice ID:rice-1 qty:2 Basmati rice"


def test_rewrite_tags_replace_the_whole_set():
    line = "* category:drill ID:drill-1 tag:condition:used tag:owner:tb EAN:123 A drill"
    out = edititem.rewrite_item_line(line, {}, tags=["condition:new"])
    assert out == "* category:drill ID:drill-1 tag:condition:new EAN:123 A drill"


def test_rewrite_leaves_other_fields_byte_identical():
    line = "* category:rice ID:rice-1 EAN:7038010000000 bb:2027-01 price:EUR:1.29/pcs Rice 1kg (top shelf)"
    out = edititem.rewrite_item_line(line, {"bb": "2028-02"})
    assert out.replace("2028-02", "2027-01") == line


def test_rewrite_category_replaces_every_category_token():
    # category repeats on a line; replacing it must drop the later tokens too,
    # or the old categories survive next to the new one.
    line = "* category:canning category:dinner ID:vl-1 bb:2027-01 Stuffed vine leaves"
    out = edititem.rewrite_item_line(line, {"category": "canning,dolma"})
    assert out == "* category:canning,dolma ID:vl-1 bb:2027-01 Stuffed vine leaves"


def test_rewrite_fills_an_empty_placeholder_field():
    # "EAN:" with no value is a placeholder for a barcode still to be read; the
    # value goes there instead of a second EAN: field being added.
    line = "* category:tinned-meat ID:hash-1 Beef hash bb:2026-06-01:EST EAN:"
    out = edititem.rewrite_item_line(line, {"ean": "3850104020353"})
    assert out == "* category:tinned-meat ID:hash-1 Beef hash bb:2026-06-01:EST EAN:3850104020353"


def test_rewrite_category_drops_non_adjacent_category_tokens():
    line = "* category:a ID:x category:b Foo category:c"
    out = edititem.rewrite_item_line(line, {"category": "d"})
    assert out == "* category:d ID:x Foo"


def test_rewrite_removing_a_field_removes_its_empty_placeholder():
    line = "* category:tinned-meat ID:hash-1 Beef hash EAN:"
    out = edititem.rewrite_item_line(line, {"ean": None})
    assert out == "* category:tinned-meat ID:hash-1 Beef hash"


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        # "Notes:"/"Type:" end in a colon but are words of the name, as the parser
        # reads them; a new name replaces them with the rest.
        ("* category:x ID:a Box Notes: fragile", "* category:x ID:a New name"),
        ("* category:x ID:a Type: B cable", "* category:x ID:a New name"),
        # An empty "ID:" in the name must not hide the real ID behind it.
        ("* category:x Garmin ID: sticker ID:gps-1", "* category:x ID:gps-1 New name"),
    ],
)
def test_rewrite_name_replaces_colon_words_in_the_name(line: str, expected: str):
    assert edititem.rewrite_item_line(line, {}, name="New name") == expected


def test_rewrite_does_not_fill_a_capitalised_word_in_the_name():
    # Only the canonical spelling ("price:", "EAN:") is a placeholder; "Price:" in
    # prose stays prose and the field goes in its canonical place.
    line = "* category:knife ID:a Price: high-end knife"
    out = edititem.rewrite_item_line(line, {"price": "EUR:5/pcs"})
    assert out == "* category:knife ID:a price:EUR:5/pcs Price: high-end knife"


def test_rewrite_fills_placeholder_and_replaces_name_together():
    line = "* category:x ID:a Beef hash EAN:"
    out = edititem.rewrite_item_line(line, {"ean": "123"}, name="Hash")
    assert out == "* category:x ID:a EAN:123 Hash"


def test_field_value_skips_an_empty_placeholder():
    line = "* category:x ID:a bb: bb:2026-01 Foo"
    assert edititem.field_value(line, "bb") == "2026-01"


def test_rewrite_does_not_touch_colon_tokens_in_the_name():
    # A second ID: inside the description is free text, not a field (same rule as
    # the parser); editing must not rewrite or consume it.
    line = "* category:tracker ID:gps-1 EAN:123 GPS tracker (IMEI:490154, ID:280425160522)"
    out = edititem.rewrite_item_line(line, {"ean": "999"})
    assert "ID:280425160522" in out
    assert "ID:gps-1" in out
    assert "EAN:999" in out


# --- edit_item end to end ---------------------------------------------------


@pytest.fixture
def inventory_dir(tmp_path: Path) -> Path:
    (tmp_path / "inventory.md").write_text(_MD, encoding="utf-8")
    example_vocab = Path(__file__).parent.parent / "example" / "vocabulary.json"
    (tmp_path / "vocabulary.json").write_text(example_vocab.read_text(encoding="utf-8"), encoding="utf-8")
    return tmp_path


@pytest.fixture
def md_path(inventory_dir: Path) -> Path:
    return inventory_dir / "inventory.md"


def test_edit_item_updates_ean(md_path: Path):
    result = edititem.edit_item(md_path, item_id="rice-1", ean="1234567890128")
    assert not result.errors
    assert result.written
    assert "EAN:1234567890128" in md_path.read_text(encoding="utf-8")
    assert result.before != result.after


def test_edit_item_fills_ean_placeholder(md_path: Path):
    md_path.write_text("# ID:box1 Box\n\n* category:hammer ID:hammer-1 A hammer EAN:\n", encoding="utf-8")
    result = edititem.edit_item(md_path, item_id="hammer-1", ean="1234567890128")
    assert not result.errors
    assert result.after == "* category:hammer ID:hammer-1 A hammer EAN:1234567890128"


def test_edit_item_category_replaces_every_category(md_path: Path):
    md_path.write_text("# ID:box1 Box\n\n* category:hammer category:tool ID:hammer-1 A hammer\n", encoding="utf-8")
    result = edititem.edit_item(md_path, item_id="hammer-1", category="hammer")
    assert not result.errors
    assert result.after == "* category:hammer ID:hammer-1 A hammer"


def test_edit_item_name_over_an_empty_id_word(md_path: Path):
    md_path.write_text("# ID:box1 Box\n\n* category:hammer Garmin ID: sticker ID:hammer-1\n", encoding="utf-8")
    result = edititem.edit_item(md_path, item_id="hammer-1", name="A hammer")
    assert not result.errors
    assert result.after == "* category:hammer ID:hammer-1 A hammer"


def test_edit_item_reports_before_and_after(md_path: Path):
    result = edititem.edit_item(md_path, item_id="rice-1", qty="5")
    assert result.before == "* category:rice ID:rice-1 EAN:7038010000000 bb:2027-01 qty:2 Rice 1kg"
    assert result.after == "* category:rice ID:rice-1 EAN:7038010000000 bb:2027-01 qty:5 Rice 1kg"
    assert result.container == "box1"


def test_edit_item_dry_run_leaves_file(md_path: Path):
    before = md_path.read_text(encoding="utf-8")
    result = edititem.edit_item(md_path, item_id="rice-1", qty="5", dry_run=True)
    assert not result.errors
    assert not result.written
    assert result.after != result.before
    assert md_path.read_text(encoding="utf-8") == before


def test_edit_item_preserves_subbullets(md_path: Path):
    result = edititem.edit_item(md_path, item_id="peel-1", mass="500g", check_bb=False)
    assert not result.errors
    text = md_path.read_text(encoding="utf-8")
    assert "  * 83 g/m2 plain" in text
    assert "  * 105 g/m2 twill" in text
    assert "mass:500g" in text


def test_edit_item_unknown_id_errors(md_path: Path):
    before = md_path.read_text(encoding="utf-8")
    result = edititem.edit_item(md_path, item_id="nope-1", qty="5")
    assert result.errors
    assert not result.written
    assert md_path.read_text(encoding="utf-8") == before


def test_edit_item_ambiguous_id_errors(tmp_path: Path):
    md = tmp_path / "inventory.md"
    md.write_text(
        "# ID:box1 Box\n\n* category:rice ID:dup Rice\n* category:pasta ID:dup Pasta\n",
        encoding="utf-8",
    )
    before = md.read_text(encoding="utf-8")
    result = edititem.edit_item(md, item_id="dup", qty="5", check_bb=False)
    assert result.errors
    assert "more than once" in result.errors[0] or "2" in result.errors[0]
    assert not result.written
    assert md.read_text(encoding="utf-8") == before


def test_edit_item_container_heading_id_is_not_an_item(md_path: Path):
    result = edititem.edit_item(md_path, item_id="box1", qty="5")
    assert result.errors
    assert not result.written


def test_edit_item_no_changes_requested_errors(md_path: Path):
    result = edititem.edit_item(md_path, item_id="rice-1")
    assert result.errors
    assert not result.written


def test_edit_item_bb_est_suffix(md_path: Path):
    result = edititem.edit_item(md_path, item_id="rice-1", bb="2027-02:EST")
    assert not result.errors
    assert "bb:2027-02:EST" in md_path.read_text(encoding="utf-8")


def test_edit_item_bb_est_flag(md_path: Path):
    result = edititem.edit_item(md_path, item_id="rice-1", bb="2027-02", bb_est=True)
    assert not result.errors
    assert "bb:2027-02:EST" in md_path.read_text(encoding="utf-8")


def test_edit_item_bb_est_conflict_errors(md_path: Path):
    result = edititem.edit_item(md_path, item_id="rice-1", bb="2027-02:EST", bb_est=False)
    assert result.errors
    assert not result.written


def test_edit_item_est_flag_alone_marks_existing_bb(md_path: Path):
    # The repair case: a date already on the line was a guess, not a printed date.
    result = edititem.edit_item(md_path, item_id="milk-1", bb_est=True)
    assert not result.errors
    assert "bb:2026-07:EST" in md_path.read_text(encoding="utf-8")


def test_edit_item_no_est_flag_alone_clears_marker(md_path: Path):
    edititem.edit_item(md_path, item_id="milk-1", bb_est=True)
    result = edititem.edit_item(md_path, item_id="milk-1", bb_est=False)
    assert not result.errors
    text = md_path.read_text(encoding="utf-8")
    assert "bb:2026-07 " in text
    assert ":EST" not in text


def test_edit_item_est_flag_without_any_bb_errors(md_path: Path):
    result = edititem.edit_item(md_path, item_id="peel-1", bb_est=True)
    assert result.errors
    assert not result.written


def test_edit_item_invalid_bb_format_errors(md_path: Path):
    result = edititem.edit_item(md_path, item_id="rice-1", bb="soon")
    assert result.errors
    assert not result.written


def test_edit_item_removing_bb_from_food_errors(md_path: Path):
    result = edititem.edit_item(md_path, item_id="milk-1", bb="")
    assert result.errors
    assert not result.written


def test_edit_item_removing_bb_from_food_allowed_with_flag(md_path: Path):
    result = edititem.edit_item(md_path, item_id="milk-1", bb="", check_bb=False)
    assert not result.errors
    assert "bb:" not in result.after


def test_edit_item_unknown_category_warns(md_path: Path):
    result = edititem.edit_item(md_path, item_id="peel-1", category="zzz-unknown-thing", check_bb=False)
    assert not result.errors
    assert result.warnings
    assert result.written


def test_edit_item_unknown_category_strict_errors(md_path: Path):
    result = edititem.edit_item(md_path, item_id="peel-1", category="zzz-unknown-thing", strict=True, check_bb=False)
    assert result.errors
    assert not result.written


def test_edit_item_name_change(md_path: Path):
    result = edititem.edit_item(md_path, item_id="rice-1", name="Basmati rice 1kg")
    assert not result.errors
    assert result.after.endswith("Basmati rice 1kg")
    assert "EAN:7038010000000" in result.after


def test_edit_item_tags_replace(md_path: Path):
    result = edititem.edit_item(md_path, item_id="peel-1", tags=["condition:new"], check_bb=False)
    assert not result.errors
    assert "tag:condition:new" in md_path.read_text(encoding="utf-8")


def test_edit_item_missing_file_errors(tmp_path: Path):
    result = edititem.edit_item(tmp_path / "nope.md", item_id="rice-1", qty="1")
    assert result.errors
    assert not result.written


def test_edit_item_keeps_the_rest_of_the_file_intact(md_path: Path):
    before = md_path.read_text(encoding="utf-8")
    edititem.edit_item(md_path, item_id="rice-1", qty="9")
    after = md_path.read_text(encoding="utf-8")
    assert len(after.splitlines()) == len(before.splitlines())
    changed = [(a, b) for a, b in zip(before.splitlines(), after.splitlines(), strict=True) if a != b]
    assert len(changed) == 1
