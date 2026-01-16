"""
Shopping list generator for inventory system.

Compares wanted-items.md (target stock levels) with inventory.md to generate
a shopping list organized by section.

Supports dated wanted-items files (wanted-items-YYYY-MM-DD.md) for temporary
shopping needs like recipe ingredients.
"""

import glob
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


def parse_amount(value: str | None) -> tuple[float | None, str | None]:
    """Parse a mass/volume string into (amount, unit)."""
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
            if current_section.items:
                sections.append(current_section)
            current_section = Section(name=header_match.group(1).strip())
            continue

        line = line.strip()
        if not line.startswith("* tag:"):
            continue

        # Extract tag
        tag_match = re.search(r'tag:(\S+)', line)
        if not tag_match:
            continue
        tag = tag_match.group(1)

        # Extract description or use tag as fallback
        desc_match = re.search(r' - (.+?)(?:\s+target:|$)', line)
        if desc_match:
            description = desc_match.group(1).strip()
        else:
            tag_parts = tag.split(",")[0].split("/")
            description = tag_parts[-1].replace("-", " ").replace("_", " ").title()

        # Extract target quantities
        target_qty = None
        target_mass_g = None
        target_volume_ml = None

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

        mass_match = re.search(r'mass:(\S+)', line)
        if mass_match:
            amount, unit = parse_amount(mass_match.group(1))
            if amount is not None and target_mass_g is None:
                target_mass_g = amount

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

    if current_section.items:
        sections.append(current_section)

    return sections


def parse_inventory_for_shopping(content: str) -> list[InventoryItem]:
    """Extract all tagged items from inventory.md."""
    items = []

    for line in content.split("\n"):
        if "tag:" not in line.lower():
            continue
        if not line.strip().startswith("*"):
            continue

        tag_match = re.search(r'tag:(\S+)', line)
        if not tag_match:
            continue
        tag = tag_match.group(1).lower()

        id_match = re.search(r'ID:(\S+)', line)
        item_id = id_match.group(1) if id_match else ""

        qty = 1
        qty_match = re.search(r'qty:(\d+)', line)
        if qty_match:
            qty = int(qty_match.group(1))

        mass_g = None
        mass_match = re.search(r'mass:(\S+)', line)
        if mass_match:
            amount, unit = parse_amount(mass_match.group(1))
            if amount is not None:
                mass_g = amount

        volume_ml = None
        volume_match = re.search(r'volume:(\S+)', line)
        if volume_match:
            amount, unit = parse_amount(volume_match.group(1))
            if amount is not None:
                volume_ml = amount

        bb_match = re.search(r'bb:(\S+)', line)
        bb = bb_match.group(1) if bb_match else None

        expired = "expired" in line.lower()

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

    if desired == inventory:
        return True

    if inventory.startswith(desired + "/"):
        return True

    desired_tags = [t.strip() for t in desired.split(",")]
    inventory_tags = [t.strip() for t in inventory.split(",")]

    for dt in desired_tags:
        for it in inventory_tags:
            if dt == it or it.startswith(dt + "/"):
                return True
            it_parts = it.replace(",", "/").split("/")
            dt_parts = dt.split("/")
            if all(p in it_parts for p in dt_parts):
                return True

    return False


def find_matches(desired: DesiredItem, inventory: list[InventoryItem]) -> list[InventoryItem]:
    """Find inventory items matching a desired item."""
    return [item for item in inventory if tag_matches(desired.tag, item.tag)]


def evaluate_item(desired: DesiredItem, inventory: list[InventoryItem]) -> tuple[str, str]:
    """Evaluate an item's stock status. Returns (status, detail_text)."""
    matches = find_matches(desired, inventory)
    non_expired = [m for m in matches if not m.expired]

    total_qty = sum(m.qty for m in non_expired)
    total_mass_g = sum((m.mass_g or 0) * m.qty for m in non_expired)
    total_volume_ml = sum((m.volume_ml or 0) * m.qty for m in non_expired)

    if desired.target_mass_g is not None:
        have, need, unit = total_mass_g, desired.target_mass_g, "g"
        is_satisfied = have >= need
    elif desired.target_volume_ml is not None:
        have, need, unit = total_volume_ml, desired.target_volume_ml, "ml"
        is_satisfied = have >= need
    else:
        have, need, unit = total_qty, desired.target_qty or 1, None
        is_satisfied = have >= need

    if not matches:
        detail = f"need {format_amount(need, unit)}" if unit else (f"need {need}" if need > 1 else "")
        return "missing", f"{detail} - not in inventory" if detail else "not in inventory"

    if not non_expired:
        return "missing", "all expired"

    if total_qty == 0:
        return "missing", "out of stock"

    if not is_satisfied:
        have_str = format_amount(have, unit) if unit else str(int(have))
        need_str = format_amount(need, unit) if unit else str(int(need))
        if unit and have == 0 and total_qty > 0:
            have_str = f"{have_str} ({total_qty} items without {unit})"
        return "low", f"have {have_str}, need {need_str}"

    return "ok", ""


def find_dated_wanted_files(base_path: Path) -> list[Path]:
    """Find dated wanted-items files in same directory (wanted-items-YYYY-MM-DD.md)."""
    directory = base_path.parent
    pattern = directory / "wanted-items-*.md"

    dated_files = []
    for filepath in glob.glob(str(pattern)):
        path = Path(filepath)
        if re.match(r'wanted-items-\d{4}-\d{2}-\d{2}\.md$', path.name):
            dated_files.append(path)

    return sorted(dated_files)


def merge_sections(all_sections: list[list[Section]]) -> list[Section]:
    """Merge sections from multiple wanted-items files."""
    merged: dict[str, Section] = {}

    for sections in all_sections:
        for section in sections:
            if section.name in merged:
                merged[section.name].items.extend(section.items)
            else:
                merged[section.name] = Section(
                    name=section.name,
                    items=list(section.items)
                )

    return list(merged.values())


def generate_shopping_list(wanted_path: Path, inventory_path: Path, include_dated: bool = False) -> str:
    """Generate shopping list markdown from wanted-items.md and inventory.md.

    If include_dated=True, also includes any wanted-items-YYYY-MM-DD.md files.
    """
    all_sections = [parse_wanted_items(wanted_path.read_text(encoding="utf-8"))]

    if include_dated:
        for dated_path in find_dated_wanted_files(wanted_path):
            if dated_path.exists():
                all_sections.append(parse_wanted_items(dated_path.read_text(encoding="utf-8")))

    sections = merge_sections(all_sections) if include_dated else all_sections[0]
    inventory = parse_inventory_for_shopping(inventory_path.read_text(encoding="utf-8"))

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
                text = f"{prefix} {desired.description} ({detail})" if detail else f"{prefix} {desired.description}"
                section_items.append((0, text))
            elif status == "low":
                total_low += 1
                text = f"[ ] {desired.description}: {detail}"
                section_items.append((1, text))
            else:
                total_ok += 1

        if section_items:
            lines.append(f"## {section.name}")
            lines.append("")
            section_items.sort(key=lambda x: x[0])
            for _, text in section_items:
                lines.append(text)
            lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"**Summary:** {total_missing} missing, {total_low} low stock, {total_ok} fully stocked")

    return "\n".join(lines)


def generate_shopping_list_if_needed(inventory_dir: Path, include_dated: bool = True) -> bool:
    """Generate shopping list if wanted-items.md exists. Returns True if generated.

    By default, includes dated wanted-items files (wanted-items-YYYY-MM-DD.md).
    """
    wanted_path = inventory_dir / "wanted-items.md"
    inventory_path = inventory_dir / "inventory.md"
    output_path = inventory_dir / "shopping-list.md"

    if not wanted_path.exists():
        return False

    if not inventory_path.exists():
        return False

    output = generate_shopping_list(wanted_path, inventory_path, include_dated=include_dated)
    output_path.write_text(output, encoding="utf-8")
    return True
