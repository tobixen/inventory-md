#!/usr/bin/env python3
"""
Inventory Data Quality Checker

Checks an inventory.json file for data quality issues including:
- Duplicate container IDs
- Missing parent references
- Items tagged TODO
- Untagged items
- Empty containers
- Missing descriptions

Usage:
    python check_quality.py [path/to/inventory.json]

If no path is provided, looks for inventory.json in current directory.

Exit codes:
    0 - No issues found
    1 - Issues found (printed to stdout)
    2 - File not found or other error
"""

import json
import sys
from collections import Counter
from pathlib import Path


def load_inventory(path: Path) -> dict:
    """Load inventory data from JSON file."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def check_duplicate_ids(data: dict) -> list:
    """Check for duplicate container IDs."""
    containers = data.get("containers", [])
    ids = [c["id"] for c in containers]
    duplicates = [id for id, count in Counter(ids).items() if count > 1]
    return [f"Duplicate container ID: {id}" for id in duplicates]


def check_missing_parents(data: dict) -> list:
    """Check for parent references that don't exist."""
    containers = data.get("containers", [])
    all_ids = {c["id"] for c in containers}

    issues = []
    for container in containers:
        parent = container.get("parent")
        if parent and parent not in all_ids:
            issues.append(f"Missing parent: {container['id']} -> {parent} (not found)")
    return issues


def check_todo_items(data: dict) -> list:
    """Find items tagged with TODO."""
    containers = data.get("containers", [])
    issues = []

    for container in containers:
        for item in container.get("items", []):
            tags = item.get("metadata", {}).get("tags", [])
            if "TODO" in tags:
                name = item.get("name") or item.get("raw_text", "")
                issues.append(f"TODO item in {container['id']}: {name[:50]}")
    return issues


def check_untagged_items(data: dict) -> list:
    """Find items without any tags."""
    containers = data.get("containers", [])
    untagged = []

    for container in containers:
        for item in container.get("items", []):
            tags = item.get("metadata", {}).get("tags", [])
            if not tags:
                name = item.get("name") or item.get("raw_text", "")
                untagged.append((container["id"], name[:40]))

    if not untagged:
        return []

    # Return summary, not individual items
    return [f"Untagged items: {len(untagged)} items have no tags"]


def check_empty_containers(data: dict) -> list:
    """Find containers with no items."""
    containers = data.get("containers", [])
    empty = [c["id"] for c in containers if not c.get("items")]

    if not empty:
        return []

    return [f"Empty containers: {len(empty)} ({', '.join(empty[:10])}{'...' if len(empty) > 10 else ''})"]


def check_missing_descriptions(data: dict) -> list:
    """Find containers without descriptions."""
    containers = data.get("containers", [])
    missing = [c["id"] for c in containers if not c.get("description", "").strip()]

    if not missing:
        return []

    return [f"Missing descriptions: {len(missing)} containers have no description"]


def check_containers_without_images(data: dict) -> list:
    """Find containers without any images."""
    containers = data.get("containers", [])
    no_images = [c["id"] for c in containers if not c.get("images")]

    if not no_images:
        return []

    return [f"No images: {len(no_images)} containers have no photos"]


def run_all_checks(data: dict) -> dict:
    """Run all quality checks and return categorized results."""
    return {
        "errors": (
            check_duplicate_ids(data) +
            check_missing_parents(data)
        ),
        "warnings": (
            check_todo_items(data)
        ),
        "info": (
            check_untagged_items(data) +
            check_empty_containers(data) +
            check_missing_descriptions(data) +
            check_containers_without_images(data)
        ),
    }


def print_results(results: dict, verbose: bool = False):
    """Print check results."""
    has_issues = False

    if results["errors"]:
        has_issues = True
        print("ERRORS:")
        for error in results["errors"]:
            print(f"  [ERROR] {error}")
        print()

    if results["warnings"]:
        has_issues = True
        print("WARNINGS:")
        for warning in results["warnings"]:
            print(f"  [WARN]  {warning}")
        print()

    if results["info"]:
        print("INFO:")
        for info in results["info"]:
            print(f"  [INFO]  {info}")
        print()

    if not has_issues and not results["info"]:
        print("All checks passed!")

    return has_issues


def main():
    # Parse arguments
    verbose = "-v" in sys.argv or "--verbose" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("-")]

    # Determine inventory path
    if args:
        inventory_path = Path(args[0])
    else:
        inventory_path = Path("inventory.json")

    if not inventory_path.exists():
        print(f"Error: {inventory_path} not found", file=sys.stderr)
        print(f"Usage: {sys.argv[0]} [-v] [path/to/inventory.json]", file=sys.stderr)
        sys.exit(2)

    # Load and check
    print(f"Checking: {inventory_path}")
    print()

    data = load_inventory(inventory_path)
    results = run_all_checks(data)
    print_results(results, verbose)

    # Exit code
    sys.exit(1 if results["errors"] else 0)


if __name__ == "__main__":
    main()
