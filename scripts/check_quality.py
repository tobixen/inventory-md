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
    python check_quality.py [--tingbok-url URL] [--no-tingbok] [--fix-categories] [path/to/inventory.json]

If no path is provided, looks for inventory.json in current directory.
Tingbok URL defaults to https://tingbok.plann.no.
Language is read from inventory-md.yaml next to the inventory file.

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
    from inventory_md.config import Config as _Config

    _VOCAB_AVAILABLE = True
except ImportError:
    _VOCAB_AVAILABLE = False

DEFAULT_TINGBOK_URL = "https://tingbok.plann.no"

_NB_LANGS = {"nb", "no", "nn"}


def load_inventory(path: Path) -> dict:
    """Load inventory data from JSON file."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_inventory_lang(inventory_path: Path) -> str:
    """Read the lang setting from inventory-md.yaml next to the inventory file."""
    if not _VOCAB_AVAILABLE:
        return "en"
    for name in ("inventory-md.yaml", "inventory-md.json", "config.yaml", "config.json"):
        cfg_path = inventory_path.parent / name
        if cfg_path.exists():
            try:
                return _Config(path=cfg_path).lang
            except Exception:
                pass
    return "en"


def _nb_eq(a: str, b: str) -> bool:
    """Treat nb/no/nn as equivalent for language comparison."""
    if a == b:
        return True
    return a in _NB_LANGS and b in _NB_LANGS


def _preferred_label(concept_data: dict, lang: str) -> str:
    """Return the preferred category string for a concept in the given language.

    For English: the canonical concept ID.
    For other languages: the first altLabel in that language, falling back to the ID.
    """
    canonical = concept_data.get("id", "")
    if lang == "en":
        return canonical
    alt_labels = concept_data.get("altLabel", {})
    for alt_lang, labels in alt_labels.items():
        if _nb_eq(alt_lang, lang) and labels:
            return labels[0]
    return canonical


def _is_valid_label_for_lang(label: str, concept_data: dict, lang: str) -> bool:
    """Check whether a label is the canonical form for the given language.

    For English: label must equal the concept ID (or its leaf component).
    For other languages: label must appear in altLabels[lang].
    """
    canonical = concept_data.get("id", "")
    label_lower = label.lower()
    if lang == "en":
        return label_lower == canonical.lower() or label_lower == canonical.split("/")[-1].lower()
    alt_labels = concept_data.get("altLabel", {})
    for alt_lang, labels in alt_labels.items():
        if _nb_eq(alt_lang, lang):
            if any(lbl.lower() == label_lower for lbl in labels):
                return True
    return False


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


def _lookup_tingbok(leaf: str, base: str) -> dict | None:
    """GET /api/lookup/{leaf}; return parsed JSON or None on 404/error."""
    import niquests

    try:
        resp = niquests.get(f"{base}/api/lookup/{leaf}", timeout=10)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def check_unresolvable_categories(
    data: dict,
    concepts: dict,
    lang: str,
    tingbok_url: str | None,
) -> tuple[list, list, dict[str, str]]:
    """Check that every category resolves, and suggest canonical/lang fixes.

    Returns:
        (warnings, infos, fix_map)
        fix_map: {old_category: new_category} for --fix-categories
    """
    containers = data.get("containers", [])

    # Collect unique categories that don't resolve locally
    locally_unresolved: Counter = Counter()
    for container in containers:
        for item in container.get("items", []):
            for cat in item.get("metadata", {}).get("categories", []):
                if _vocabulary.resolve_category(cat, concepts, lang=lang) is None:
                    locally_unresolved[cat] += 1

    if not locally_unresolved:
        return [], [], {}

    base = tingbok_url.rstrip("/") if tingbok_url else None
    unresolvable: Counter = Counter()
    infos: list[str] = []
    fix_map: dict[str, str] = {}

    for cat, n in locally_unresolved.items():
        parts = cat.split("/")

        if len(parts) == 1:
            # Simple label: look it up directly
            concept_data = _lookup_tingbok(cat, base) if base else None
            if concept_data is None:
                unresolvable[cat] = n
                continue
            if _is_valid_label_for_lang(cat, concept_data, lang):
                # Already the right form for this language
                continue
            preferred = _preferred_label(concept_data, lang)
            if preferred.lower() != cat.lower():
                infos.append(f"Non-canonical category {cat!r} ({n}×) → consider using {preferred!r}")
                fix_map[cat] = preferred
        else:
            # Path: validate each component and hierarchy
            path_warnings, path_infos, path_fixes = _check_category_path(cat, n, lang, base, concepts)
            unresolvable.update(path_warnings)
            infos.extend(path_infos)
            fix_map.update(path_fixes)

    warnings = []
    if unresolvable:
        total = sum(unresolvable.values())
        top = ", ".join(f"{cat!r} ({n})" for cat, n in unresolvable.most_common(5))
        warnings.append(f"Unresolvable categories: {total} items use unknown categories — top: {top}")

    return warnings, infos, fix_map


def _check_category_path(
    cat: str,
    n: int,
    lang: str,
    base: str | None,
    concepts: dict,
) -> tuple[Counter, list[str], dict[str, str]]:
    """Validate a multi-component category path.

    Checks:
    - Each component resolves to a concept
    - Each concept is a valid broader of the next
    - Each component is the preferred label for the inventory language

    Returns (unresolvable_counter, infos, fix_map).
    """
    parts = cat.split("/")
    resolved: list[dict | None] = []

    if base:
        for part in parts:
            resolved.append(_lookup_tingbok(part, base))
    else:
        resolved = [None] * len(parts)

    # Check each component resolves
    unresolvable: Counter = Counter()
    bad_parts = [p for p, r in zip(parts, resolved, strict=False) if r is None]
    if bad_parts:
        unresolvable[cat] = n
        return unresolvable, [], {}

    # Validate hierarchy: each concept should be broader than the next
    hierarchy_ok = True
    for i in range(len(resolved) - 1):
        parent_id = resolved[i]["id"]
        child_broader = resolved[i + 1].get("broader", [])
        if parent_id not in child_broader:
            hierarchy_ok = False
            break

    if not hierarchy_ok:
        return Counter({cat: n}), [f"Invalid category path {cat!r} ({n}×): hierarchy mismatch"], {}

    # Check each component is the preferred label for lang, build fix if needed
    preferred_parts = [_preferred_label(r, lang) for r in resolved]
    preferred_path = "/".join(preferred_parts)

    infos: list[str] = []
    fix_map: dict[str, str] = {}

    if preferred_path.lower() != cat.lower():
        infos.append(f"Non-canonical path {cat!r} ({n}×) → consider using {preferred_path!r}")
        fix_map[cat] = preferred_path

    return Counter(), infos, fix_map


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


def apply_fixes(inventory_path: Path, fix_map: dict[str, str]) -> int:
    """Apply category replacements to inventory.json in-place.

    Returns the number of individual category strings replaced.
    """
    data = load_inventory(inventory_path)
    count = 0

    for container in data.get("containers", []):
        for item in container.get("items", []):
            cats = item.get("metadata", {}).get("categories", [])
            new_cats = []
            for cat in cats:
                if cat in fix_map:
                    new_cats.append(fix_map[cat])
                    count += 1
                else:
                    new_cats.append(cat)
            if new_cats != cats:
                item["metadata"]["categories"] = new_cats

    with open(inventory_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    return count


def run_all_checks(data: dict, concepts: dict, lang: str, tingbok_url: str | None) -> tuple[dict, dict[str, str]]:
    """Run all quality checks and return (results, fix_map)."""
    warnings = list(check_todo_items(data)) + list(check_items_without_category(data))
    infos = check_empty_containers(data) + check_missing_descriptions(data) + check_containers_without_images(data)
    fix_map: dict[str, str] = {}

    if concepts:
        cat_warnings, cat_infos, cat_fixes = check_unresolvable_categories(data, concepts, lang, tingbok_url)
        warnings += cat_warnings
        infos += cat_infos
        fix_map.update(cat_fixes)

    results = {
        "errors": check_duplicate_ids(data) + check_missing_parents(data),
        "warnings": warnings,
        "info": infos,
    }
    return results, fix_map


def print_results(results: dict) -> bool:
    """Print check results. Returns True if there are errors or warnings."""
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

    fix_categories = "--fix-categories" in args
    args = [a for a in args if a != "--fix-categories"]

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
        print(
            f"Usage: {sys.argv[0]} [-v] [--tingbok-url URL] [--no-tingbok] [--fix-categories] [path/to/inventory.json]",
            file=sys.stderr,
        )
        sys.exit(2)

    lang = load_inventory_lang(inventory_path)

    print(f"Checking: {inventory_path}")
    print(f"Language: {lang}")
    if _VOCAB_AVAILABLE:
        print(f"Vocabulary: {tingbok_url or 'local only'}")
    else:
        print("Vocabulary: unavailable (inventory_md not importable)")
    print()

    data = load_inventory(inventory_path)
    concepts = load_vocabulary(inventory_path, tingbok_url)
    results, fix_map = run_all_checks(data, concepts, lang, tingbok_url)
    print_results(results)

    if fix_categories:
        if fix_map:
            print(f"Applying {len(fix_map)} category fix(es)...")
            count = apply_fixes(inventory_path, fix_map)
            print(f"  Replaced {count} category string(s) in {inventory_path}")
        else:
            print("No category fixes to apply.")

    sys.exit(1 if results["errors"] else 0)


if __name__ == "__main__":
    main()
