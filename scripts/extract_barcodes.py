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
    --no-cache      Skip local cache, always query online
    --json          Output as JSON
    -h, --help      Show this help message

Local Cache:
    Lookups are cached in ean_cache.json in the current directory.
    You can manually add entries for products not found online:

    {
      "5202336150151": {
        "name": "Greek product name",
        "brand": "Brand",
        "quantity": "500g",
        "source": "manual"
      }
    }
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


# Default cache file location
CACHE_FILE = Path('ean_cache.json')


def load_cache(cache_path: Path) -> dict:
    """Load the local EAN cache."""
    if cache_path.exists():
        try:
            with open(cache_path) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load cache: {e}", file=sys.stderr)
    return {}


def save_cache(cache: dict, cache_path: Path):
    """Save the local EAN cache."""
    try:
        with open(cache_path, 'w') as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except IOError as e:
        print(f"Warning: Could not save cache: {e}", file=sys.stderr)


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


def lookup_ean_online(ean: str) -> dict | None:
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
            'source': 'openfoodfacts',
        }
    except requests.RequestException as e:
        print(f"Lookup failed for {ean}: {e}", file=sys.stderr)
        return None


def lookup_ean(ean: str, cache: dict, use_cache: bool = True) -> tuple[dict | None, bool]:
    """
    Look up an EAN, checking cache first.

    Returns (product_info, was_cached).
    """
    # Check cache first
    if use_cache and ean in cache:
        cached = cache[ean]
        # None in cache means "looked up but not found"
        if cached is None:
            return None, True
        return cached, True

    # Look up online
    product = lookup_ean_online(ean)

    return product, False


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
    use_cache = True
    output_json = False
    single_lookup = None
    image_paths = []

    i = 0
    while i < len(args):
        arg = args[i]
        if arg == '--no-lookup':
            do_lookup = False
        elif arg == '--no-cache':
            use_cache = False
        elif arg == '--json':
            output_json = True
        elif arg == '--lookup' and i + 1 < len(args):
            i += 1
            single_lookup = args[i]
        elif not arg.startswith('-'):
            image_paths.append(Path(arg))
        i += 1

    # Load cache
    cache = load_cache(CACHE_FILE) if use_cache else {}
    cache_modified = False

    # Single EAN lookup mode
    if single_lookup:
        if not HAS_REQUESTS and single_lookup not in cache:
            print("Error: requests package required for lookup", file=sys.stderr)
            print("Run: pip install requests", file=sys.stderr)
            sys.exit(1)

        product, was_cached = lookup_ean(single_lookup, cache, use_cache)

        # Save to cache if new lookup
        if not was_cached and use_cache:
            cache[single_lookup] = product
            save_cache(cache, CACHE_FILE)

        if output_json:
            print(json.dumps(product, indent=2))
        elif product:
            print(f"EAN: {single_lookup}")
            print(f"Name: {product.get('name', 'Unknown')}")
            print(f"Brand: {product.get('brand', 'Unknown')}")
            print(f"Quantity: {product.get('quantity', 'Unknown')}")
            print(f"Categories: {product.get('categories', 'Unknown')}")
            print(f"Source: {product.get('source', 'unknown')}")
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
                ean = barcode['data']
                product, was_cached = lookup_ean(ean, cache, use_cache)
                result['product'] = product

                # Save to cache if new lookup
                if not was_cached and use_cache:
                    cache[ean] = product
                    cache_modified = True
                    # Rate limit only for online lookups
                    time.sleep(0.5)

            all_results.append(result)

    # Save cache if modified
    if cache_modified:
        save_cache(cache, CACHE_FILE)

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
