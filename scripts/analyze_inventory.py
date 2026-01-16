#!/usr/bin/env python3
"""
Inventory Analysis Script

Analyzes an inventory.json file and prints statistics about containers,
items, images, tags, and hierarchy.

Usage:
    python analyze_inventory.py [path/to/inventory.json]

If no path is provided, looks for inventory.json in current directory.
"""

import json
import sys
from collections import Counter
from pathlib import Path


def load_inventory(path: Path) -> dict:
    """Load inventory data from JSON file."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def analyze_containers(data: dict) -> dict:
    """Analyze container statistics."""
    containers = data.get("containers", [])

    return {
        "total": len(containers),
        "with_items": sum(1 for c in containers if c.get("items")),
        "empty": sum(1 for c in containers if not c.get("items")),
        "with_images": sum(1 for c in containers if c.get("images")),
        "without_images": sum(1 for c in containers if not c.get("images")),
        "with_description": sum(1 for c in containers if c.get("description", "").strip()),
        "without_description": sum(1 for c in containers if not c.get("description", "").strip()),
    }


def analyze_items(data: dict) -> dict:
    """Analyze item statistics."""
    containers = data.get("containers", [])

    total_items = 0
    items_with_tags = 0
    items_without_tags = 0
    all_tags = Counter()

    for container in containers:
        for item in container.get("items", []):
            total_items += 1
            tags = item.get("metadata", {}).get("tags", [])
            if tags:
                items_with_tags += 1
                all_tags.update(tags)
            else:
                items_without_tags += 1

    return {
        "total": total_items,
        "with_tags": items_with_tags,
        "without_tags": items_without_tags,
        "tag_coverage_pct": round(items_with_tags / total_items * 100, 1) if total_items else 0,
        "unique_tags": len(all_tags),
        "top_tags": all_tags.most_common(20),
    }


def analyze_images(data: dict) -> dict:
    """Analyze image statistics."""
    containers = data.get("containers", [])

    total_images = sum(len(c.get("images", [])) for c in containers)

    return {
        "total": total_images,
    }


def analyze_hierarchy(data: dict) -> dict:
    """Analyze container hierarchy."""
    containers = data.get("containers", [])

    all_ids = {c["id"] for c in containers}
    parents = Counter()
    orphans = []
    missing_parents = []

    for container in containers:
        parent = container.get("parent")
        if parent:
            parents[parent] += 1
            if parent not in all_ids:
                missing_parents.append((container["id"], parent))
        else:
            orphans.append(container["id"])

    return {
        "with_parent": len(containers) - len(orphans),
        "top_level": len(orphans),
        "top_level_ids": orphans,
        "unique_parents": len(parents),
        "missing_parents": missing_parents,
    }


def check_duplicates(data: dict) -> list:
    """Check for duplicate container IDs."""
    containers = data.get("containers", [])
    ids = [c["id"] for c in containers]
    return [id for id, count in Counter(ids).items() if count > 1]


def find_todo_items(data: dict) -> list:
    """Find items tagged with TODO."""
    containers = data.get("containers", [])
    todo_items = []

    for container in containers:
        for item in container.get("items", []):
            tags = item.get("metadata", {}).get("tags", [])
            if "TODO" in tags:
                name = item.get("name") or item.get("raw_text", "")
                todo_items.append((container["id"], name[:60]))

    return todo_items


def print_report(inventory_path: Path, data: dict):
    """Print analysis report."""
    print("=" * 60)
    print(f"Inventory Analysis: {inventory_path.name}")
    print("=" * 60)
    print()

    # Container stats
    containers = analyze_containers(data)
    print("CONTAINERS")
    print(f"  Total:              {containers['total']}")
    print(f"  With items:         {containers['with_items']}")
    print(f"  Empty:              {containers['empty']}")
    print(f"  With images:        {containers['with_images']}")
    print(f"  Without images:     {containers['without_images']}")
    print(f"  With description:   {containers['with_description']}")
    print(f"  Without description:{containers['without_description']}")
    print()

    # Item stats
    items = analyze_items(data)
    print("ITEMS")
    print(f"  Total:              {items['total']}")
    print(f"  With tags:          {items['with_tags']} ({items['tag_coverage_pct']}%)")
    print(f"  Without tags:       {items['without_tags']}")
    print(f"  Unique tags:        {items['unique_tags']}")
    print()

    # Top tags
    print("TOP 15 TAGS")
    for tag, count in items["top_tags"][:15]:
        print(f"  {tag:20} {count}")
    print()

    # Images
    images = analyze_images(data)
    print("IMAGES")
    print(f"  Total linked:       {images['total']}")
    print()

    # Hierarchy
    hierarchy = analyze_hierarchy(data)
    print("HIERARCHY")
    print(f"  Top-level containers: {hierarchy['top_level']}")
    print(f"  Containers with parent: {hierarchy['with_parent']}")
    print(f"  Unique parent locations: {hierarchy['unique_parents']}")
    if hierarchy["missing_parents"]:
        print(f"  Missing parent refs: {len(hierarchy['missing_parents'])}")
        for cid, parent in hierarchy["missing_parents"][:5]:
            print(f"    {cid} -> {parent} (not found)")
    print()

    # Data quality
    print("DATA QUALITY")
    duplicates = check_duplicates(data)
    if duplicates:
        print(f"  Duplicate IDs: {duplicates}")
    else:
        print("  Duplicate IDs: None")

    todo_items = find_todo_items(data)
    print(f"  TODO items: {len(todo_items)}")
    if todo_items:
        for cid, name in todo_items[:5]:
            print(f"    {cid}: {name}")
        if len(todo_items) > 5:
            print(f"    ... and {len(todo_items) - 5} more")
    print()


def main():
    # Determine inventory path
    if len(sys.argv) > 1:
        inventory_path = Path(sys.argv[1])
    else:
        inventory_path = Path("inventory.json")

    if not inventory_path.exists():
        print(f"Error: {inventory_path} not found", file=sys.stderr)
        print(f"Usage: {sys.argv[0]} [path/to/inventory.json]", file=sys.stderr)
        sys.exit(1)

    # Load and analyze
    data = load_inventory(inventory_path)
    print_report(inventory_path, data)


if __name__ == "__main__":
    main()
