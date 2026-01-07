#!/usr/bin/env python3
"""
Extract barcodes and QR codes from images and look up product information.

Requires: pip install pyzbar pillow requests

Usage:
    ./extract_barcodes.py image.jpg [image2.jpg ...]
    ./extract_barcodes.py photos/F-01/*.jpg
    ./extract_barcodes.py --lookup 5701234567890

Options:
    --lookup EAN    Look up a single EAN without image processing
    --no-lookup     Extract barcodes but skip online lookup
    --json          Output as JSON
    -h, --help      Show this help message
"""

import sys
import json
import time
from pathlib import Path

try:
    from PIL import Image
    from pyzbar.pyzbar import decode, ZBarSymbol
except ImportError:
    print("Error: Required packages not installed.", file=sys.stderr)
    print("Run: pip install pyzbar pillow", file=sys.stderr)
    sys.exit(1)

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


def extract_barcodes(image_path: Path) -> list[dict]:
    """
    Extract all barcodes and QR codes from an image.

    Returns list of dicts with: type, data, polygon
    """
    try:
        image = Image.open(image_path)
    except Exception as e:
        print(f"Error reading {image_path}: {e}", file=sys.stderr)
        return []

    # Decode all barcode types
    decoded = decode(image)

    results = []
    for barcode in decoded:
        results.append({
            'type': barcode.type,  # EAN13, EAN8, UPCA, QRCODE, CODE128, etc.
            'data': barcode.data.decode('utf-8'),
            'polygon': [(p.x, p.y) for p in barcode.polygon] if barcode.polygon else None,
        })

    return results


def lookup_ean(ean: str) -> dict | None:
    """
    Look up an EAN using Open Food Facts API.

    Returns product info dict or None if not found.
    """
    if not HAS_REQUESTS:
        return None

    # Open Food Facts API (free, no API key needed)
    url = f"https://world.openfoodfacts.org/api/v2/product/{ean}.json"

    try:
        response = requests.get(url, timeout=10, headers={
            'User-Agent': 'InventorySystem/1.0 (https://github.com/tobixen/inventory-system)'
        })
        response.raise_for_status()
        data = response.json()

        if data.get('status') != 1:
            return None

        product = data.get('product', {})
        return {
            'ean': ean,
            'name': product.get('product_name') or product.get('product_name_en'),
            'brand': product.get('brands'),
            'quantity': product.get('quantity'),
            'categories': product.get('categories'),
            'image_url': product.get('image_url'),
            'nutriscore': product.get('nutriscore_grade'),
        }
    except requests.RequestException as e:
        print(f"Lookup failed for {ean}: {e}", file=sys.stderr)
        return None


def is_ean(barcode_type: str, data: str) -> bool:
    """Check if barcode is a product EAN/UPC that can be looked up."""
    if barcode_type in ('EAN13', 'EAN8', 'UPCA', 'UPCE'):
        return True
    # Some barcodes encode EANs as other types
    if barcode_type == 'CODE128' and data.isdigit() and len(data) in (8, 12, 13):
        return True
    return False


def format_for_inventory(barcode: dict, product: dict | None) -> str:
    """Format barcode info for inventory.md."""
    ean = barcode['data']
    barcode_type = barcode['type']

    if product and product.get('name'):
        name = product['name']
        brand = product.get('brand', '')
        quantity = product.get('quantity', '')

        parts = []
        if brand:
            parts.append(brand)
        parts.append(name)
        if quantity:
            parts.append(f"({quantity})")

        desc = ' '.join(parts)
        return f"* EAN:{ean} {desc}"
    else:
        return f"* EAN:{ean} (unknown product, type: {barcode_type})"


def main():
    args = sys.argv[1:]

    if not args or '-h' in args or '--help' in args:
        print(__doc__)
        sys.exit(0)

    do_lookup = True
    output_json = False
    single_lookup = None
    image_paths = []

    i = 0
    while i < len(args):
        arg = args[i]
        if arg == '--no-lookup':
            do_lookup = False
        elif arg == '--json':
            output_json = True
        elif arg == '--lookup' and i + 1 < len(args):
            i += 1
            single_lookup = args[i]
        elif not arg.startswith('-'):
            image_paths.append(Path(arg))
        i += 1

    # Single EAN lookup mode
    if single_lookup:
        if not HAS_REQUESTS:
            print("Error: requests package required for lookup", file=sys.stderr)
            print("Run: pip install requests", file=sys.stderr)
            sys.exit(1)

        product = lookup_ean(single_lookup)
        if output_json:
            print(json.dumps(product, indent=2))
        elif product:
            print(f"EAN: {single_lookup}")
            print(f"Name: {product.get('name', 'Unknown')}")
            print(f"Brand: {product.get('brand', 'Unknown')}")
            print(f"Quantity: {product.get('quantity', 'Unknown')}")
            print(f"Categories: {product.get('categories', 'Unknown')}")
        else:
            print(f"Product not found: {single_lookup}")
        sys.exit(0)

    if not image_paths:
        print("Error: No image files specified", file=sys.stderr)
        sys.exit(1)

    all_results = []

    for image_path in image_paths:
        if not image_path.exists():
            print(f"Warning: {image_path} not found", file=sys.stderr)
            continue

        barcodes = extract_barcodes(image_path)

        if not barcodes:
            continue

        for barcode in barcodes:
            result = {
                'file': str(image_path),
                'type': barcode['type'],
                'data': barcode['data'],
                'product': None,
            }

            # Look up EANs
            if do_lookup and is_ean(barcode['type'], barcode['data']):
                product = lookup_ean(barcode['data'])
                result['product'] = product
                # Rate limit to be nice to the API
                time.sleep(0.5)

            all_results.append(result)

    if output_json:
        print(json.dumps(all_results, indent=2))
    else:
        # Human-readable output
        seen_eans = set()

        for result in all_results:
            ean = result['data']
            if ean in seen_eans:
                continue
            seen_eans.add(ean)

            barcode = {'type': result['type'], 'data': ean}
            print(format_for_inventory(barcode, result.get('product')))
            print(f"    # Found in: {result['file']}")
            print()


if __name__ == '__main__':
    main()
