#!/usr/bin/env python3
"""Print the situational context for a shopping run — read-only.

The process-shopping skill needs, at the start of every trip, the same handful
of facts it otherwise rediscovers by grepping markdown and config: the shop's
cached Open Prices OSM object, one or two recent staging files for that shop (as
a schema/convention example to copy), and the shop's recent diary expense lines
(to mirror the wording/category convention). Gathering them with ad-hoc
``grep``/``cat``/``awk`` defeats the allowlist — a chained shell command can't be
pre-approved — so this single read-only command replaces all of it.

Usage::

    shopping_context.py "Praktiker"                       # everything for a shop
    shopping_context.py "Praktiker" --diary ~/solveig/diary-2026.md
    shopping_context.py                                   # just list recent staging

It writes nothing and touches no network. Pair it with ``pipeline.py`` (which
runs the commit stages) — between them the only thing left for a human is to
review the staging file.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

DEFAULT_OSM_CACHE = Path.home() / ".config" / "inventory-md" / "shop-osm.json"


def load_osm_cache(path: Path) -> dict[str, Any]:
    """Load the shop→OSM cache, returning ``{}`` if it does not exist."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def match_shop_osm(cache: dict[str, Any], shop: str) -> dict[str, Any] | None:
    """Find a cached OSM entry whose key matches *shop* (case-insensitive).

    Tries an exact (case-insensitive) match first, then a substring match in
    either direction, so ``"lidl"`` finds ``"Lidl Varna"``.
    """
    if not shop:
        return None
    want = shop.casefold()
    for key, val in cache.items():
        if key.casefold() == want:
            return val
    for key, val in cache.items():
        kf = key.casefold()
        if want in kf or kf in want:
            return val
    return None


def shop_of(path: Path) -> str | None:
    """Return the ``shop:`` field of a staging file without a YAML dependency."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    m = re.search(r"^shop:\s*(.+?)\s*$", text, re.MULTILINE)
    return m.group(1).strip().strip("'\"") if m else None


def find_staging_files(staging_dir: Path, shop: str | None, limit: int) -> list[Path]:
    """Recent ``shopping-*.yaml`` files (newest first), optionally filtered by shop.

    Filtering is a case-insensitive substring test against each file's ``shop:``
    field. Ordering is by filename descending — the files are date-stamped
    (``shopping-YYYY-MM-DD[-shop].yaml``), so lexical order is chronological.
    """
    files = sorted(staging_dir.glob("shopping-*.yaml"), key=lambda p: p.name, reverse=True)
    if shop:
        want = shop.casefold()
        files = [f for f in files if (s := shop_of(f)) and want in s.casefold()]
    return files[:limit]


def grep_diary_lines(diary_text: str, shop: str) -> list[str]:
    """Return diary lines mentioning *shop* (case-insensitive), stripped."""
    want = shop.casefold()
    return [line.strip() for line in diary_text.splitlines() if want in line.casefold()]


NEXT_COMMANDS = """\
Canonical next commands (run ONE per shell call — never chain with && / | / ;):
  1. extract_barcodes.py --best-before PHOTOS --json > staging/barcodes-DATE.json
  2. shop_import.py --receipt R.json --barcodes-json staging/barcodes-DATE.json \\
         --out staging/shopping-DATE[-shop].yaml
  3. (review the staging file by hand — the one human gate)
  4. pipeline.py staging/shopping-DATE[-shop].yaml            # dry run
  5. pipeline.py staging/shopping-DATE[-shop].yaml --commit   # ledger+inventory+tingbok+validate
  6. diary-update --directory DIARY_DIR -d DATE -a AMOUNT -c CUR -t TYPE --description "..."
  7. (optional, public) off_upload.py / openprices_publish.py --commit"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("shop", nargs="?", help="Shop name (or substring) to focus on")
    ap.add_argument("--staging-dir", type=Path, default=Path("staging"))
    ap.add_argument("--osm-cache", type=Path, default=DEFAULT_OSM_CACHE)
    ap.add_argument("--diary", type=Path, help="Diary file to grep for prior expense lines")
    ap.add_argument("--limit", type=int, default=2, help="How many recent staging files to show")
    ap.add_argument("--no-content", action="store_true", help="List staging files without dumping their content")
    args = ap.parse_args(argv)

    print(f"# Shopping context{f' — {args.shop}' if args.shop else ''}\n")

    print("## Shop OSM (Open Prices --osm)")
    if args.shop:
        hit = match_shop_osm(load_osm_cache(args.osm_cache), args.shop)
        if hit:
            print(f"  {args.shop} → {hit.get('osm_type')}:{hit.get('osm_id')}")
        else:
            print(f"  not cached for '{args.shop}' — pass --osm TYPE:ID to openprices_publish once (it caches).")
    else:
        cache = load_osm_cache(args.osm_cache)
        for k, v in cache.items():
            print(f"  {k} → {v.get('osm_type')}:{v.get('osm_id')}")
        if not cache:
            print("  (cache empty)")
    print()

    print(f"## Recent staging files{f' for {args.shop}' if args.shop else ''}")
    files = find_staging_files(args.staging_dir, args.shop, args.limit)
    if not files:
        print("  (none found)")
    for f in files:
        print(f"\n### {f}")
        if not args.no_content:
            print(f.read_text(encoding="utf-8").rstrip())
    print()

    if args.diary and args.shop:
        print(f"## Recent diary lines mentioning '{args.shop}'")
        try:
            lines = grep_diary_lines(args.diary.read_text(encoding="utf-8"), args.shop)
            for line in lines[-8:]:
                print(f"  {line}")
            if not lines:
                print("  (none)")
        except OSError as exc:
            print(f"  (could not read diary: {exc})")
        print()

    print(NEXT_COMMANDS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
