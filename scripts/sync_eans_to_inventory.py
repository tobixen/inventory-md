#!/usr/bin/env python3
"""
Sync EANs from photos to inventory.

Scans all photo directories, extracts barcodes, and adds missing EANs
to inventory.md for items not already in the corresponding container.

Requires: pip install pyzbar pillow requests

Usage:
    ./sync_eans_to_inventory.py                    # Dry-run (show what would be added)
    ./sync_eans_to_inventory.py --apply            # Actually update inventory.md
    ./sync_eans_to_inventory.py --container F-01   # Only process specific container

Options:
    --apply          Actually update inventory.md (default is dry-run)
    --container ID   Only process photos for this container
    --no-lookup      Skip Open Food Facts lookup
    -h, --help       Show this help message
"""

import json
import re
import sys
import time
from pathlib import Path

try:
    from PIL import Image
    from pyzbar.pyzbar import decode
except ImportError:
    print("Error: Required packages not installed.", file=sys.stderr)
    print("Run: pip install pyzbar pillow", file=sys.stderr)
    sys.exit(1)

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


def extract_barcodes_from_image(image_path: Path) -> list[dict]:
    """Extract barcodes from a single image."""
    try:
        image = Image.open(image_path)
        decoded = decode(image)
        return [
            {'type': b.type, 'data': b.data.decode('utf-8')}
            for b in decoded
        ]
    except Exception as e:
        print(f"  Warning: Could not read {image_path.name}: {e}", file=sys.stderr)
        return []


def extract_barcodes_from_directory(photo_dir: Path) -> list[dict]:
    """Extract all unique barcodes from a photo directory."""
    barcodes = []
    seen = set()

    for ext in ('*.jpg', '*.jpeg', '*.png', '*.JPG', '*.JPEG', '*.PNG'):
        for image_path in photo_dir.glob(ext):
            for barcode in extract_barcodes_from_image(image_path):
                if barcode['data'] not in seen:
                    seen.add(barcode['data'])
                    barcode['source_file'] = str(image_path)
                    barcodes.append(barcode)

    return barcodes


def is_ean(barcode_type: str, data: str) -> bool:
    """Check if barcode is a product EAN/UPC."""
    if barcode_type in ('EAN13', 'EAN8', 'UPCA', 'UPCE'):
        return True
    if barcode_type == 'CODE128' and data.isdigit() and len(data) in (8, 12, 13):
        return True
    return False


def lookup_ean(ean: str) -> dict | None:
    """Look up EAN in Open Food Facts."""
    if not HAS_REQUESTS:
        return None

    url = f"https://world.openfoodfacts.org/api/v2/product/{ean}.json"
    try:
        response = requests.get(url, timeout=10, headers={
            'User-Agent': 'InventorySystem/1.0'
        })
        response.raise_for_status()
        data = response.json()

        if data.get('status') != 1:
            return None

        product = data.get('product', {})
        return {
            'name': product.get('product_name') or product.get('product_name_en'),
            'brand': product.get('brands'),
            'quantity': product.get('quantity'),
        }
    except Exception:
        return None


def load_inventory_json(inventory_dir: Path) -> dict:
    """Load inventory.json."""
    json_path = inventory_dir / 'inventory.json'
    if not json_path.exists():
        print(f"Error: {json_path} not found. Run: inventory-system parse inventory.md", file=sys.stderr)
        sys.exit(1)

    with open(json_path) as f:
        return json.load(f)


def get_existing_eans(inventory_data: dict, container_id: str) -> set[str]:
    """Get all EANs already in a container."""
    eans = set()

    for container in inventory_data.get('containers', []):
        if container.get('id') == container_id:
            for item in container.get('items', []):
                # Check for EAN in metadata
                ean = item.get('metadata', {}).get('ean')
                if ean:
                    eans.add(str(ean))

                # Also check raw_text for EAN: pattern
                raw = item.get('raw_text', '')
                match = re.search(r'EAN:(\d+)', raw)
                if match:
                    eans.add(match.group(1))

    return eans


def find_container_section(inventory_md: str, container_id: str) -> tuple[int, int] | None:
    """Find the line range for a container in inventory.md."""
    lines = inventory_md.split('\n')
    start_line = None
    end_line = None

    for i, line in enumerate(lines):
        # Match container header: ## ID:container-id or ## container-id
        if re.match(rf'^##\s+.*\bID:{re.escape(container_id)}\b', line) or \
           re.match(rf'^##\s+{re.escape(container_id)}\b', line):
            start_line = i
        elif start_line is not None and line.startswith('## '):
            end_line = i
            break

    if start_line is not None and end_line is None:
        end_line = len(lines)

    return (start_line, end_line) if start_line is not None else None


def format_inventory_line(ean: str, product: dict | None) -> str:
    """Format an inventory.md line for a new EAN."""
    if product and product.get('name'):
        parts = []
        if product.get('brand'):
            parts.append(product['brand'])
        parts.append(product['name'])
        if product.get('quantity'):
            parts.append(f"({product['quantity']})")
        desc = ' '.join(parts)
        return f"* tag:food EAN:{ean} {desc}"
    else:
        return f"* tag:TODO EAN:{ean} (unknown product - identify from photo)"


def main():
    args = sys.argv[1:]

    if '-h' in args or '--help' in args:
        print(__doc__)
        sys.exit(0)

    apply_changes = '--apply' in args
    do_lookup = '--no-lookup' not in args
    target_container = None

    i = 0
    while i < len(args):
        if args[i] == '--container' and i + 1 < len(args):
            target_container = args[i + 1]
            i += 2
        else:
            i += 1

    # Determine inventory directory (current directory)
    inventory_dir = Path.cwd()
    photos_dir = inventory_dir / 'photos'
    inventory_md_path = inventory_dir / 'inventory.md'

    if not photos_dir.exists():
        print(f"Error: {photos_dir} not found", file=sys.stderr)
        sys.exit(1)

    if not inventory_md_path.exists():
        print(f"Error: {inventory_md_path} not found", file=sys.stderr)
        sys.exit(1)

    # Load inventory data
    inventory_data = load_inventory_json(inventory_dir)
    inventory_md = inventory_md_path.read_text(encoding='utf-8')

    # Track changes
    additions = []  # (container_id, line_to_add)

    # Process each photo directory
    photo_dirs = sorted(photos_dir.iterdir()) if photos_dir.is_dir() else []

    for photo_dir in photo_dirs:
        if not photo_dir.is_dir():
            continue

        container_id = photo_dir.name

        if target_container and container_id != target_container:
            continue

        print(f"Processing {container_id}...")

        # Get existing EANs for this container
        existing_eans = get_existing_eans(inventory_data, container_id)

        # Extract barcodes from photos
        barcodes = extract_barcodes_from_directory(photo_dir)

        if not barcodes:
            continue

        for barcode in barcodes:
            if not is_ean(barcode['type'], barcode['data']):
                continue

            ean = barcode['data']

            if ean in existing_eans:
                print(f"  EAN:{ean} - already in inventory")
                continue

            # Look up product info
            product = None
            if do_lookup:
                product = lookup_ean(ean)
                time.sleep(0.3)  # Rate limit

            line = format_inventory_line(ean, product)
            additions.append((container_id, line, barcode.get('source_file', '')))

            status = product['name'] if product and product.get('name') else 'unknown'
            print(f"  EAN:{ean} - NEW ({status})")

    # Summary
    print()
    print("=" * 60)

    if not additions:
        print("No new EANs found.")
        sys.exit(0)

    print(f"Found {len(additions)} new EAN(s) to add:")
    print()

    for container_id, line, source in additions:
        print(f"  [{container_id}] {line}")
        if source:
            print(f"           # From: {Path(source).name}")

    if not apply_changes:
        print()
        print("Dry-run mode. Use --apply to update inventory.md")
        sys.exit(0)

    # Apply changes to inventory.md
    print()
    print("Updating inventory.md...")

    lines = inventory_md.split('\n')

    # Group additions by container
    by_container = {}
    for container_id, line, source in additions:
        if container_id not in by_container:
            by_container[container_id] = []
        by_container[container_id].append(line)

    # Insert lines into each container section
    for container_id, new_lines in by_container.items():
        section = find_container_section('\n'.join(lines), container_id)
        if section is None:
            print(f"  Warning: Container {container_id} not found in inventory.md")
            continue

        start, end = section

        # Find the last item line in the section (starts with *)
        insert_pos = start + 1
        for i in range(end - 1, start, -1):
            if lines[i].strip().startswith('*'):
                insert_pos = i + 1
                break

        # Insert new lines
        for new_line in reversed(new_lines):
            lines.insert(insert_pos, new_line)

        print(f"  Added {len(new_lines)} item(s) to {container_id}")

    # Write updated inventory.md
    inventory_md_path.write_text('\n'.join(lines), encoding='utf-8')
    print()
    print("Done. Run 'inventory-system parse inventory.md' to update JSON.")


if __name__ == '__main__':
    main()
