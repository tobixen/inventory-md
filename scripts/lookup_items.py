#!/usr/bin/env python3
"""Look up specific inventory items by ID or text.

Thin wrapper around ``inventory-md lookup`` — the logic now lives in the
``inventory_md.queries`` module. Unlike find_expiring_items.py, this also reports
items that have *no* best-before date (e.g. fresh produce just bought), which is
exactly what you need when assembling a recipe ingredient list.

Usage:
    ./lookup_items.py [inventory.json] [--id ID ...] [--match TEXT ...]

Run ``inventory-md lookup --help`` for full documentation.
"""

import sys

from inventory_md.cli import main

if __name__ == "__main__":
    sys.exit(main(["lookup", *sys.argv[1:]]))
