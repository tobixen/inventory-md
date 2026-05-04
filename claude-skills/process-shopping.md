# Process Shopping

Workflow for processing a shopping receipt and updating the inventory. Originally written for Lidl receipts; adapt as needed for other shops.

For item format details (categories, quantities, best-before, etc.) see `docs/ADDING-ITEMS.md`.

## Workflow

### 1. Read the receipt

Obtain the receipt data — either from a JSON file produced by a receipt parser, or from a photo. Key fields to extract:
- `purchase_date` — date of purchase (YYYY-MM-DD or YYYY.MM.DD)
- `store` — store name and location
- `total` — total amount with currency
- `items` — list of items with name, price, quantity

### 2. Extract barcodes and best-before dates from photos

If product photos were taken, run the barcode extraction script:

```bash
~/inventory-md/scripts/extract_barcodes.py PHOTO_FILES
```

Typically one photo will show the barcode; the next will show the best-before date.

### 3. Match receipt items to EANs

Use the `ean_cache.json` in the inventory directory and any per-instance matching scripts to correlate receipt item names with EAN codes. The `lidl_receipt_name` field in `ean_cache.json` maps receipt names to EAN codes.

### 4. Ask user for storage locations

Check if each item already exists in the inventory. Suggest suitable storage locations and confirm with the user.

### 5. Check expiry dates

Photos typically come in pairs: barcode photo + best-before photo. Try to read the date from the photo. Ask the user if it cannot be found. If no best-before is available at all, estimate one and append `:EST`.

See `docs/ADDING-ITEMS.md` for typical shelf-life estimates.

### 6. Update inventory.md

Add items to the appropriate container sections. Format:

```
* category:CONCEPT ID:ITEM-ID EAN:EANCODE bb:YYYY-MM qty:N mass:Xg volume:Xl price:CURRENCY:XXX/YYY PRODUCT NAME
```

See `docs/ADDING-ITEMS.md` for full field reference, category syntax, and quantity conventions.

### 7. Report EAN observations to tingbok

Send product observations (name, category, price, receipt name) to tingbok via PUT:

```bash
curl -s -X PUT https://tingbok.plann.no/api/ean/EAN_CODE \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Product name",
    "categories": ["food/dairy"],
    "quantity": "1l",
    "prices": [
      {"date": "YYYY-MM-DD", "shop": "Store Name", "price": 1.02, "currency": "EUR", "unit": "pcs"}
    ],
    "receipt_names": [
      {"name": "RECEIPT NAME AS PRINTED", "shop": "Store Name", "first_seen": "YYYY-MM-DD", "last_seen": "YYYY-MM-DD"}
    ]
  }'
```

All fields are optional — only include what is known. PUT merges new data (prices and receipt_names are appended, not replaced).

**Price format:**
- `unit`: `"pcs"` for per-piece, `"kg"` for per-kilogram

### 8. Copy photos to storage location directories

Organise photos by **storage location**, not by shopping trip. Only copy photos that show the product packaging/label with the product name or image — **not** close-up barcode scans or expiry date shots (even if those helped identify the product). Skip photos for items that will be consumed quickly (fresh produce, bread, etc.).

```bash
mkdir -p $INVENTORY_DIR/photos/LOCATION-ID/
cp PRODUCT_PHOTOS $INVENTORY_DIR/photos/LOCATION-ID/
```

Do **not** create shopping-date directories like `lidl-2026-01-24/`.

### 9. Commit changes

```bash
cd $INVENTORY_DIR
git add inventory.md photo-registry.md
git commit -m "Add shopping YYYY-MM-DD to inventory"
```

## Scripts

Per-instance matching scripts (e.g. `match_lidl_receipt.py`) live in the instance's `scripts/` directory. The barcode extraction script is at `~/inventory-md/scripts/extract_barcodes.py`.
