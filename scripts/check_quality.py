#!/usr/bin/env python3
"""
Inventory Data Quality Checker

Checks an inventory.json file for data quality issues including:
- Duplicate container IDs
- Missing parent references
- Items tagged TODO
- Items without a category
- Items whose category doesn't resolve in the vocabulary / tingbok
- Empty containers
- Missing descriptions

Usage:
    python check_quality.py [--tingbok-url URL] [path/to/inventory.json]

If no path is provided, looks for inventory.json in current directory.
Tingbok URL defaults to https://tingbok.plann.no.

Exit codes:
    0 - No issues found
    1 - Issues found (printed to stdout)
    2 - File not found or other error
"""

import json
import sys
from collections import Counter
from pathlib import Path

try:
    from inventory_md import vocabulary as _vocabulary

    _VOCAB_AVAILABLE = True
except ImportError:
    _VOCAB_AVAILABLE = False

DEFAULT_TINGBOK_URL = "https://tingbok.plann.no"


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


def check_items_without_category(data: dict) -> list:
    """Find items without any category."""
    containers = data.get("containers", [])
    count = sum(1 for c in containers for item in c.get("items", []) if not item.get("metadata", {}).get("categories"))
    if not count:
        return []
    return [f"Items without category: {count} items have no category"]


def check_unresolvable_categories(data: dict, concepts: dict, tingbok_url: str | None) -> list:
    """Find items whose category doesn't resolve locally or via tingbok lookup."""
    import niquests

    containers = data.get("containers", [])
    counts: Counter = Counter()

    for container in containers:
        for item in container.get("items", []):
            for cat in item.get("metadata", {}).get("categories", []):
                if _vocabulary.resolve_category(cat, concepts) is None:
                    counts[cat] += 1

    if not counts:
        return []

    # For each locally-unresolvable unique category, try the tingbok lookup endpoint
    unresolvable: Counter = Counter()
    if tingbok_url:
        base = tingbok_url.rstrip("/")
        for cat, n in counts.items():
            leaf = cat.split("/")[-1]
            try:
                resp = niquests.get(f"{base}/api/lookup/{leaf}", timeout=10)
                if resp.status_code == 404:
                    unresolvable[cat] = n
            except Exception:
                unresolvable[cat] = n
    else:
        unresolvable = counts

    if not unresolvable:
        return []

    total = sum(unresolvable.values())
    top = ", ".join(f"{cat!r} ({n})" for cat, n in unresolvable.most_common(5))
    return [f"Unresolvable categories: {total} items use unknown categories — top: {top}"]


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


def load_vocabulary(inventory_path: Path, tingbok_url: str | None) -> dict:
    """Load vocabulary from tingbok and local files next to the inventory."""
    if not _VOCAB_AVAILABLE:
        return {}
    try:
        concepts = _vocabulary.load_global_vocabulary(tingbok_url=tingbok_url)
        local_vocab_path = inventory_path.parent / "vocabulary.json"
        if local_vocab_path.exists():
            local = _vocabulary.load_local_vocabulary(local_vocab_path)
            concepts.update(local)
        return concepts
    except Exception as e:
        print(f"[WARN] Could not load vocabulary: {e}", file=sys.stderr)
        return {}


def run_all_checks(data: dict, concepts: dict, tingbok_url: str | None) -> dict:
    """Run all quality checks and return categorized results."""
    warnings = list(check_todo_items(data)) + list(check_items_without_category(data))
    if concepts:
        warnings += check_unresolvable_categories(data, concepts, tingbok_url)

    return {
        "errors": (check_duplicate_ids(data) + check_missing_parents(data)),
        "warnings": warnings,
        "info": (
            check_empty_containers(data) + check_missing_descriptions(data) + check_containers_without_images(data)
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
    args = sys.argv[1:]

    verbose = "-v" in args or "--verbose" in args
    args = [a for a in args if a not in ("-v", "--verbose")]

    tingbok_url: str | None = DEFAULT_TINGBOK_URL
    if "--no-tingbok" in args:
        tingbok_url = None
        args = [a for a in args if a != "--no-tingbok"]
    elif "--tingbok-url" in args:
        idx = args.index("--tingbok-url")
        tingbok_url = args[idx + 1]
        args = args[:idx] + args[idx + 2 :]

    inventory_path = Path(args[0]) if args else Path("inventory.json")

    if not inventory_path.exists():
        print(f"Error: {inventory_path} not found", file=sys.stderr)
        print(f"Usage: {sys.argv[0]} [-v] [--tingbok-url URL] [--no-tingbok] [path/to/inventory.json]", file=sys.stderr)
        sys.exit(2)

    print(f"Checking: {inventory_path}")
    if _VOCAB_AVAILABLE:
        print(f"Vocabulary: {tingbok_url or 'local only'}")
    else:
        print("Vocabulary: unavailable (inventory_md not importable)")
    print()

    data = load_inventory(inventory_path)
    concepts = load_vocabulary(inventory_path, tingbok_url)
    results = run_all_checks(data, concepts, tingbok_url)
    print_results(results, verbose)

    sys.exit(1 if results["errors"] else 0)


if __name__ == "__main__":
    main()
