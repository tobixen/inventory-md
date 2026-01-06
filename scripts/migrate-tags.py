#!/usr/bin/env python3
"""
Migrate inventory tags from comma-separated to hierarchical format.

Usage:
    ./migrate-tags.py [--dry-run] [inventory.md]

Examples:
    ./migrate-tags.py --dry-run inventory.md    # Preview changes
    ./migrate-tags.py inventory.md              # Apply changes
"""

import json
import re
import sys
from pathlib import Path


def load_tag_mapping(mapping_file: Path) -> dict:
    """Load tag conversion mapping from JSON."""
    with open(mapping_file, encoding="utf-8") as f:
        return json.load(f)


def convert_tag(old_tag: str, mapping: dict) -> str:
    """
    Convert a comma-separated tag to hierarchical format.

    Rules:
    1. If exact match in tag_conversions, use that
    2. If two parts where second is subcategory of first, use first/second
    3. If first is cross-cutting, keep as category,cross-cutting
    4. Otherwise keep as-is
    """
    old_tag = old_tag.strip()
    conversions = mapping.get("tag_conversions_no", {})
    categories = mapping.get("categories_no", {})
    cross_cutting = mapping.get("cross_cutting_tags", {}).get("no", {})

    # Check for exact match first
    if old_tag in conversions:
        return conversions[old_tag]

    # No comma = single tag, keep as-is
    if "," not in old_tag:
        return old_tag

    parts = [p.strip() for p in old_tag.split(",")]

    # Two-part tags
    if len(parts) == 2:
        first, second = parts

        # Check if second is subcategory of first
        if first in categories:
            subcats = categories[first].get("subcategories", {})
            if second in subcats:
                return f"{first}/{second}"

        # Check if first is subcategory of second (reversed)
        if second in categories:
            subcats = categories[second].get("subcategories", {})
            if first in subcats:
                return f"{second}/{first}"

        # Check if second is cross-cutting (keep comma)
        if second in cross_cutting:
            return f"{first},{second}"

        # Check if first is cross-cutting (reorder: category,cross-cutting)
        if first in cross_cutting and second in categories:
            return f"{second},{first}"

    # Three-part tags
    if len(parts) == 3:
        first, second, third = parts

        # Pattern: category, subcategory, cross-cutting
        if first in categories:
            subcats = categories[first].get("subcategories", {})
            if second in subcats and third in cross_cutting:
                return f"{first}/{second},{third}"

    # Default: keep original
    return old_tag


def migrate_line(line: str, mapping: dict) -> tuple[str, bool]:
    """
    Migrate tags in a single line.
    Returns (new_line, changed).
    """
    # Match tag:xxx pattern
    match = re.search(r'\btag:(\S+)', line)
    if not match:
        return line, False

    old_tag = match.group(1)
    new_tag = convert_tag(old_tag, mapping)

    if old_tag == new_tag:
        return line, False

    new_line = line[:match.start(1)] + new_tag + line[match.end(1):]
    return new_line, True


def migrate_file(inventory_path: Path, mapping: dict, dry_run: bool = False) -> dict:
    """
    Migrate all tags in an inventory file.
    Returns statistics about the migration.
    """
    content = inventory_path.read_text(encoding="utf-8")
    lines = content.split("\n")

    stats = {
        "total_lines": len(lines),
        "lines_with_tags": 0,
        "lines_changed": 0,
        "changes": []
    }

    new_lines = []
    for i, line in enumerate(lines, 1):
        if "tag:" in line:
            stats["lines_with_tags"] += 1
            new_line, changed = migrate_line(line, mapping)
            if changed:
                stats["lines_changed"] += 1
                stats["changes"].append({
                    "line": i,
                    "old": line.strip(),
                    "new": new_line.strip()
                })
            new_lines.append(new_line)
        else:
            new_lines.append(line)

    if not dry_run and stats["lines_changed"] > 0:
        inventory_path.write_text("\n".join(new_lines), encoding="utf-8")

    return stats


def main():
    dry_run = "--dry-run" in sys.argv

    # Find inventory file
    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    if not args:
        print("Usage: migrate-tags.py [--dry-run] <inventory.md>")
        sys.exit(1)

    inventory_path = Path(args[0])

    # Find mapping file (in inventory-system directory)
    script_dir = Path(__file__).parent.parent  # Go up from scripts/
    mapping_path = script_dir / "tag-mapping.json"

    if not inventory_path.exists():
        print(f"Error: {inventory_path} not found")
        sys.exit(1)

    if not mapping_path.exists():
        print(f"Error: {mapping_path} not found")
        sys.exit(1)

    mapping = load_tag_mapping(mapping_path)
    stats = migrate_file(inventory_path, mapping, dry_run)

    print("=" * 70)
    print(f"TAG MIGRATION {'(DRY RUN)' if dry_run else ''}")
    print("=" * 70)
    print(f"File: {inventory_path}")
    print(f"Total lines: {stats['total_lines']}")
    print(f"Lines with tags: {stats['lines_with_tags']}")
    print(f"Lines changed: {stats['lines_changed']}")
    print()

    if stats["changes"]:
        print("Changes:")
        for change in stats["changes"][:50]:  # Show first 50
            print(f"  Line {change['line']}:")
            print(f"    - {change['old']}")
            print(f"    + {change['new']}")
            print()

        if len(stats["changes"]) > 50:
            print(f"  ... and {len(stats['changes']) - 50} more changes")

    if dry_run:
        print("\nThis was a dry run. Run without --dry-run to apply changes.")
    else:
        print(f"\n{'Changes applied!' if stats['lines_changed'] > 0 else 'No changes needed.'}")


if __name__ == "__main__":
    main()
