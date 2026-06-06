#!/usr/bin/env python3
"""Find items sorted by expiry date.

Thin wrapper around ``inventory-md expiring`` — the logic now lives in the
``inventory_md.queries`` module so it is shipped, importable and unit-tested.
This wrapper is kept so existing paths (and the suggest-recipe skill) keep working.

Usage:
    ./find_expiring_items.py [inventory.json] [--food] [--limit N] [--all] [--before DATE]

Run ``inventory-md expiring --help`` for full documentation.
"""

import sys

from inventory_md.cli import main

if __name__ == "__main__":
    sys.exit(main(["expiring", *sys.argv[1:]]))
