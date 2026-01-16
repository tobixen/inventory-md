#!/usr/bin/env python3
"""
Find food items sorted by expiry date.

Usage:
    ./find_expiring_food.py [inventory.json] [options]

Options:
    --limit N       Show top N items sorted by expiry (no date filtering)
    --all           Show all food items with expiry dates
    --before DATE   Show items expiring before DATE (YYYY-MM-DD or YYYY-MM)
    -h, --help      Show this help message

By default (no options), shows only items that have already expired.

Examples:
    ./find_expiring_food.py                          # Show expired items only
    ./find_expiring_food.py --limit 10               # Top 10 items by expiry date
    ./find_expiring_food.py --all                    # All food with expiry dates
    ./find_expiring_food.py --before 2026-06         # Items expiring before June 2026
    ./find_expiring_food.py ~/solveig-inventory/inventory.json
"""

import json
import sys
from datetime import datetime
from pathlib import Path


def find_expiring_food(inventory_path: Path, limit: int = 5) -> list:
    """
    Find food items sorted by expiry date (oldest first).

    Returns list of dicts with: id, name, container, bb, days, expired
    """
    with open(inventory_path) as f:
        data = json.load(f)

    today = datetime.now()
    food_items = []

    for container in data['containers']:
        container_id = container.get('id', 'unknown')
        parent_id = container.get('parent', '')

        for item in container.get('items', []):
            tags = item.get('metadata', {}).get('tags', [])

            # Only food items
            if not any(t.startswith('food/') for t in tags):
                continue

            bb = item.get('metadata', {}).get('bb')
            if bb:
                try:
                    # Parse date (formats: 2024-04, 2024-04-15)
                    if len(bb) == 7:  # YYYY-MM
                        exp_date = datetime.strptime(bb + '-01', '%Y-%m-%d')
                    else:
                        exp_date = datetime.strptime(bb, '%Y-%m-%d')

                    days_until = (exp_date - today).days

                    location = container_id
                    if parent_id:
                        location = f"{container_id}, {parent_id}"

                    food_items.append({
                        'id': item.get('id') or item.get('name', 'unknown')[:20],
                        'name': item.get('name', ''),
                        'container': container_id,
                        'parent': parent_id,
                        'location': location,
                        'bb': bb,
                        'days': days_until,
                        'expired': days_until < 0,
                        'tags': tags,
                    })
                except ValueError:
                    pass

    # Sort by expiry date (oldest/most expired first)
    food_items.sort(key=lambda x: x['days'])

    return food_items[:limit] if limit else food_items


def main():
    # Parse arguments
    limit = None
    before_date = None
    show_all = False
    inventory_path = Path('inventory.json')

    args = sys.argv[1:]
    while args:
        arg = args.pop(0)
        if arg in ('-h', '--help'):
            print(__doc__)
            sys.exit(0)
        elif arg == '--limit' and args:
            limit = int(args.pop(0))
        elif arg == '--before' and args:
            before_date = args.pop(0)
        elif arg == '--all':
            show_all = True
        elif not arg.startswith('-'):
            inventory_path = Path(arg)

    if not inventory_path.exists():
        print(f"Error: {inventory_path} not found", file=sys.stderr)
        print("Run: inventory-system parse inventory.md", file=sys.stderr)
        sys.exit(1)

    items = find_expiring_food(inventory_path, limit=0)  # Get all items

    if not items:
        print("No food items with expiry dates found.")
        sys.exit(0)

    # Apply filtering based on options
    if before_date:
        # Parse before_date
        if len(before_date) == 7:  # YYYY-MM
            cutoff = datetime.strptime(before_date + '-01', '%Y-%m-%d')
        else:
            cutoff = datetime.strptime(before_date, '%Y-%m-%d')
        cutoff_days = (cutoff - datetime.now()).days
        items = [i for i in items if i['days'] < cutoff_days]
    elif limit is not None:
        # --limit: no date filtering, just limit count
        items = items[:limit]
    elif not show_all:
        # Default: only show expired items
        items = [i for i in items if i['expired']]

    if not items:
        print("No matching food items found.")
        sys.exit(0)

    print("Food items to use first (by expiry date):")
    print()

    for item in items:
        if item['expired']:
            status = f"EXPIRED {-item['days']}d ago"
        elif item['days'] <= 30:
            status = f"{item['days']}d left ⚠️"
        else:
            status = f"{item['days']}d left"

        name = item['name'][:45] if len(item['name']) > 45 else item['name']
        print(f"  {item['id']}")
        print(f"    {name}")
        print(f"    Location: {item['location']}")
        print(f"    Expires: {item['bb']} [{status}]")
        print()


if __name__ == '__main__':
    main()
