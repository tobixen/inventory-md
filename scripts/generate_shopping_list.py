#!/usr/bin/env python3
"""
Generate a shopping list by comparing wanted-items.md (target stock levels)
with inventory.md (actual items).

Outputs organized by section from the wanted-items file.

Supports multiple wanted-items files:
- Main file: wanted-items.md (permanent target stock)
- Dated files: wanted-items-YYYY-MM-DD.md (temporary items for specific day)

Usage:
    ./generate_shopping_list.py wanted-items.md inventory.md [--output shopping-list.md]
    ./generate_shopping_list.py wanted-items.md inventory.md --include-dated
"""

import argparse
import glob
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


def parse_amount(value: str | None) -> tuple[float | None, str | None]:
    """
    Parse a mass/volume string into (amount, unit).

    Examples:
        "500g" -> (500.0, "g")
        "1kg" -> (1000.0, "g")  # normalized to grams
        "1l" -> (1000.0, "ml")  # normalized to ml
        "2" -> (2.0, None)      # bare number
        None -> (None, None)
    """
    if not value:
        return None, None

    value = value.lower().strip()

    match = re.match(r'^([\d.]+)\s*([a-z]*)', value)
    if not match:
        return None, None

    amount = float(match.group(1))
    unit = match.group(2) or None

    # Normalize units
    if unit == "kg":
        return amount * 1000, "g"
    elif unit == "l":
        return amount * 1000, "ml"
    elif unit in ("g", "ml"):
        return amount, unit
    elif unit is None:
        return amount, None
    else:
        return amount, unit


def format_amount(amount: float, unit: str | None) -> str:
    """Format amount with appropriate unit (kg/l for large amounts)."""
    if unit == "g" and amount >= 1000:
        return f"{amount/1000:.1f}kg"
    elif unit == "ml" and amount >= 1000:
        return f"{amount/1000:.1f}l"
    elif unit:
        return f"{amount:.0f}{unit}"
    else:
        return f"{amount:.0f}"


@dataclass
class DesiredItem:
    """An item from wanted-items.md with target quantities."""
    tag: str
    description: str
    section: str = ""
    target_qty: int | None = None
    target_mass_g: float | None = None
    target_volume_ml: float | None = None


@dataclass
class InventoryItem:
    """An item from inventory.md."""
    tag: str
    item_id: str
    description: str
    qty: int = 1
    mass_g: float | None = None
    volume_ml: float | None = None
    bb: str | None = None
    expired: bool = False


@dataclass
class Section:
    """A section from the wanted-items file."""
    name: str
    items: list[DesiredItem] = field(default_factory=list)


def parse_wanted_items(content: str) -> list[Section]:
    """Extract desired items from wanted-items.md, organized by section."""
    sections = []
    current_section = Section(name="Uncategorized")

    for line in content.split("\n"):
        # Check for section header (## heading)
        header_match = re.match(r'^##\s+(.+)$', line)
        if header_match:
            # Save previous section if it has items
            if current_section.items:
                sections.append(current_section)
            current_section = Section(name=header_match.group(1).strip())
            continue

        line = line.strip()
        if not line.startswith("* tag:"):
            continue

        # Extract tag (handle comma-separated multiple tags)
        tag_match = re.search(r'tag:(\S+)', line)
        if not tag_match:
            continue
        tag = tag_match.group(1)

        # Extract description (after the dash), or use tag as fallback
        desc_match = re.search(r' - (.+?)(?:\s+target:|$)', line)
        if desc_match:
            description = desc_match.group(1).strip()
        else:
            # Use last part of tag as fallback description
            # e.g., "consumables/toiletpaper" -> "toiletpaper"
            tag_parts = tag.split(",")[0].split("/")
            description = tag_parts[-1].replace("-", " ").replace("_", " ").title()

        # Extract target quantities
        target_qty = None
        target_mass_g = None
        target_volume_ml = None

        # Handle target:qty:Xkg or target:qty:X formats
        qty_match = re.search(r'target:qty:(\S+)', line)
        if qty_match:
            qty_str = qty_match.group(1)
            amount, unit = parse_amount(qty_str)
            if unit == "g":
                target_mass_g = amount
            elif unit == "ml":
                target_volume_ml = amount
            elif amount is not None:
                target_qty = int(amount)

        # Handle explicit mass: target
        mass_match = re.search(r'mass:(\S+)', line)
        if mass_match:
            amount, unit = parse_amount(mass_match.group(1))
            if amount is not None and target_mass_g is None:
                target_mass_g = amount

        # Handle explicit volume: target
        volume_match = re.search(r'volume:(\S+)', line)
        if volume_match:
            amount, unit = parse_amount(volume_match.group(1))
            if amount is not None and target_volume_ml is None:
                target_volume_ml = amount

        current_section.items.append(DesiredItem(
            tag=tag,
            description=description,
            section=current_section.name,
            target_qty=target_qty,
            target_mass_g=target_mass_g,
            target_volume_ml=target_volume_ml,
        ))

    # Don't forget the last section
    if current_section.items:
        sections.append(current_section)

    return sections


def parse_inventory(content: str) -> list[InventoryItem]:
    """Extract all tagged items from inventory.md."""
    items = []

    for line in content.split("\n"):
        # Match any line with a tag
        if "tag:" not in line.lower():
            continue

        # Must be a list item
        if not line.strip().startswith("*"):
            continue

        # Extract tag
        tag_match = re.search(r'tag:(\S+)', line)
        if not tag_match:
            continue
        tag = tag_match.group(1).lower()

        # Extract ID
        id_match = re.search(r'ID:(\S+)', line)
        item_id = id_match.group(1) if id_match else ""

        # Extract quantity (default 1)
        qty = 1
        qty_match = re.search(r'qty:(\d+)', line)
        if qty_match:
            qty = int(qty_match.group(1))

        # Extract and normalize mass
        mass_g = None
        mass_match = re.search(r'mass:(\S+)', line)
        if mass_match:
            amount, unit = parse_amount(mass_match.group(1))
            if amount is not None:
                mass_g = amount

        # Extract and normalize volume
        volume_ml = None
        volume_match = re.search(r'volume:(\S+)', line)
        if volume_match:
            amount, unit = parse_amount(volume_match.group(1))
            if amount is not None:
                volume_ml = amount

        # Extract best-before
        bb_match = re.search(r'bb:(\S+)', line)
        bb = bb_match.group(1) if bb_match else None

        # Check if expired
        expired = "expired" in line.lower()

        # Get description (everything after the metadata)
        desc = re.sub(r'\*\s*', '', line)
        desc = re.sub(r'tag:\S+\s*', '', desc)
        desc = re.sub(r'ID:\S+\s*', '', desc)
        desc = re.sub(r'qty:\d+\s*', '', desc)
        desc = re.sub(r'mass:\S+\s*', '', desc)
        desc = re.sub(r'volume:\S+\s*', '', desc)
        desc = re.sub(r'bb:\S+\s*', '', desc)
        desc = re.sub(r'EAN:\S+\s*', '', desc)
        desc = re.sub(r'price:\S+\s*', '', desc)
        desc = desc.strip()

        items.append(InventoryItem(
            tag=tag,
            item_id=item_id,
            description=desc,
            qty=qty,
            mass_g=mass_g,
            volume_ml=volume_ml,
            bb=bb,
            expired=expired,
        ))

    return items


def tag_matches(desired_tag: str, inventory_tag: str) -> bool:
    """Check if inventory tag matches desired tag (hierarchical matching)."""
    desired = desired_tag.lower()
    inventory = inventory_tag.lower()

    # Direct match
    if desired == inventory:
        return True

    # Hierarchical: food/cereal matches food/cereal/oats
    if inventory.startswith(desired + "/"):
        return True

    # Handle comma-separated tags (both in desired and inventory)
    # e.g., "food/canned,food/tomato" matches "food/canned" or "food/tomato"
    desired_tags = [t.strip() for t in desired.split(",")]
    inventory_tags = [t.strip() for t in inventory.split(",")]

    for dt in desired_tags:
        for it in inventory_tags:
            if dt == it or it.startswith(dt + "/"):
                return True
            # Handle old comma-separated format within a single tag
            it_parts = it.replace(",", "/").split("/")
            dt_parts = dt.split("/")
            if all(p in it_parts for p in dt_parts):
                return True

    return False


def find_matches(desired: DesiredItem, inventory: list[InventoryItem]) -> list[InventoryItem]:
    """Find inventory items matching a desired item."""
    matches = []
    for item in inventory:
        if tag_matches(desired.tag, item.tag):
            matches.append(item)
    return matches


def evaluate_item(desired: DesiredItem, inventory: list[InventoryItem]) -> tuple[str, str]:
    """
    Evaluate an item's stock status.

    Returns (status, detail_text) where status is one of:
    - "ok": fully stocked
    - "low": below target but not empty
    - "missing": not in inventory, all expired, or zero quantity
    """
    matches = find_matches(desired, inventory)
    non_expired = [m for m in matches if not m.expired]

    # Calculate totals
    total_qty = sum(m.qty for m in non_expired)
    total_mass_g = sum((m.mass_g or 0) * m.qty for m in non_expired)
    total_volume_ml = sum((m.volume_ml or 0) * m.qty for m in non_expired)

    # Determine comparison type and check satisfaction
    if desired.target_mass_g is not None:
        have = total_mass_g
        need = desired.target_mass_g
        unit = "g"
        is_satisfied = have >= need
    elif desired.target_volume_ml is not None:
        have = total_volume_ml
        need = desired.target_volume_ml
        unit = "ml"
        is_satisfied = have >= need
    else:
        have = total_qty
        need = desired.target_qty or 1
        unit = None
        is_satisfied = have >= need

    # Determine status
    if not matches:
        reason = "not in inventory"
        if unit:
            detail = f"need {format_amount(need, unit)}"
        elif need > 1:
            detail = f"need {need}"
        else:
            detail = ""
        return "missing", f"{detail} - {reason}" if detail else reason

    if not non_expired:
        return "missing", "all expired"

    if total_qty == 0:
        return "missing", "out of stock"

    if not is_satisfied:
        have_str = format_amount(have, unit) if unit else str(int(have))
        need_str = format_amount(need, unit) if unit else str(int(need))
        # Show fallback info if tracking by mass/volume but no data
        if unit and have == 0 and total_qty > 0:
            have_str = f"{have_str} ({total_qty} items without {unit})"
        return "low", f"have {have_str}, need {need_str}"

    return "ok", ""


def generate_shopping_list(sections: list[Section], inventory: list[InventoryItem]) -> str:
    """Generate the shopping list markdown."""
    lines = []
    lines.append("# Shopping List")
    lines.append("")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    total_missing = 0
    total_low = 0
    total_ok = 0

    for section in sections:
        section_items = []

        for desired in section.items:
            status, detail = evaluate_item(desired, inventory)

            if status == "missing":
                total_missing += 1
                prefix = "[!]"
                if detail:
                    text = f"{prefix} {desired.description} ({detail})"
                else:
                    text = f"{prefix} {desired.description}"
                section_items.append((0, text))  # Priority 0 = missing
            elif status == "low":
                total_low += 1
                text = f"[ ] {desired.description}: {detail}"
                section_items.append((1, text))  # Priority 1 = low
            else:
                total_ok += 1
                # Don't show stocked items

        if section_items:
            lines.append(f"## {section.name}")
            lines.append("")
            # Sort by priority (missing first, then low)
            section_items.sort(key=lambda x: x[0])
            for _, text in section_items:
                lines.append(text)
            lines.append("")

    # Summary
    lines.append("---")
    lines.append("")
    lines.append(f"**Summary:** {total_missing} missing, {total_low} low stock, {total_ok} fully stocked")

    return "\n".join(lines)


def find_dated_wanted_files(base_path: Path) -> list[Path]:
    """
    Find dated wanted-items files in the same directory as the main file.

    Looks for files matching wanted-items-YYYY-MM-DD.md pattern.
    Returns sorted list (oldest first).
    """
    directory = base_path.parent
    pattern = directory / "wanted-items-*.md"

    dated_files = []
    for filepath in glob.glob(str(pattern)):
        path = Path(filepath)
        # Verify it matches the date pattern
        if re.match(r'wanted-items-\d{4}-\d{2}-\d{2}\.md$', path.name):
            dated_files.append(path)

    return sorted(dated_files)


def merge_sections(all_sections: list[list[Section]]) -> list[Section]:
    """
    Merge sections from multiple wanted-items files.

    Sections with the same name are combined.
    """
    merged: dict[str, Section] = {}

    for sections in all_sections:
        for section in sections:
            if section.name in merged:
                # Add items to existing section
                merged[section.name].items.extend(section.items)
            else:
                # Create new section (copy to avoid mutation)
                merged[section.name] = Section(
                    name=section.name,
                    items=list(section.items)
                )

    return list(merged.values())


def main():
    parser = argparse.ArgumentParser(
        description="Generate shopping list from wanted-items and inventory"
    )
    parser.add_argument("wanted_items", help="Path to wanted-items.md")
    parser.add_argument("inventory", help="Path to inventory.md")
    parser.add_argument("--output", "-o", help="Output file (default: stdout)")
    parser.add_argument(
        "--include-dated", "-d",
        action="store_true",
        help="Include dated wanted-items files (wanted-items-YYYY-MM-DD.md)"
    )

    args = parser.parse_args()

    wanted_path = Path(args.wanted_items)
    inventory_path = Path(args.inventory)

    if not wanted_path.exists():
        print(f"Error: {wanted_path} not found", file=sys.stderr)
        sys.exit(1)
    if not inventory_path.exists():
        print(f"Error: {inventory_path} not found", file=sys.stderr)
        sys.exit(1)

    # Parse main wanted-items file
    all_sections = [parse_wanted_items(wanted_path.read_text(encoding="utf-8"))]

    # Optionally include dated wanted-items files
    if args.include_dated:
        dated_files = find_dated_wanted_files(wanted_path)
        for dated_path in dated_files:
            if dated_path.exists():
                print(f"Including: {dated_path.name}", file=sys.stderr)
                all_sections.append(parse_wanted_items(dated_path.read_text(encoding="utf-8")))

    # Merge all sections
    sections = merge_sections(all_sections)
    inventory = parse_inventory(inventory_path.read_text(encoding="utf-8"))

    output = generate_shopping_list(sections, inventory)

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Shopping list written to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
