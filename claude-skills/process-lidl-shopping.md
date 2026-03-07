# Process Lidl Shopping

Process a Lidl shopping receipt and update the boat inventory.

## When to use

Use this skill when the user mentions:
- Lidl shopping/receipt
- Processing a shopping receipt
- Adding groceries to inventory

## Workflow

### 1. Read the receipt

The Lidl receipt is stored at `~/shopping-analyzer/lidl_receipts.json`. Read the most recent entry (last item in the array):
```bash
jq '.[-1]' ~/shopping-analyzer/lidl_receipts.json
```

Receipt fields:
- `purchase_date`: Date in format "YYYY.MM.DD"
- `total_price_no_saving`: Total amount in local currency. EUR for Bulgaria
- `store`: Store location
- `items`: Array of purchased items with `name`, `price`, `quantity`

### 2. Extract barcodes and best-before dates from photos

Run the barcode extraction script on recent photos:
```bash
~/inventory-md/scripts/extract_barcodes.py ~/s/photos.tobixen/newmi/IMG_*.jpg
```

Typically one photo will be with barcode, and the next with the best-before date

### 3. Match receipt items to EANs

Use the matching script to correlate receipt items with scanned barcodes:
```bash
~/solveig-inventory/scripts/match_lidl_receipt.py
```

This script uses the `lidl_receipt_name` field in `ean_cache.json` to match Bulgarian receipt names to EAN codes.

### 4. Ask user for storage locations

See if the item already exists in the inventory.  Suggest storage space for the items and ask the user where things are going.

Common locations on the boat:
- `ID:pantry-fridge` - Refrigerator (for milk, dairy, fresh items)
- 'ID:food1` - storage aft of mast
- `ID:food2` - Storage fore of mast (dry goods)
- `ID:food3` - Storage under floor (canned goods, preserves)
- `ID:pantry-behind-stove` - fruits and vegetables are often stored behind the stove


### 5. Check expiry dates

Photos typically comes in pairs, one photo with the bar code and the next photo will be with the expiry date.  Try to find it in the photo.  Ask the user if it's not found.  Finally, if no bb-dae is available, estimate one.

### 6. Update inventory.md

Add items to the appropriate sections in `~/solveig-inventory/inventory.md`.

Format for food items:
```
* category:CONCEPT ID:ITEM-ID EAN:EANCODE bb:YYYY-MM qty:N mass:Xg volume:Xl price:EUR:XXX/YYY PRODUCT NAME
```

**Category syntax:**
- Use `category:` prefix for SKOS hierarchy expansion
- Simple labels like `category:milk` get expanded to full paths (e.g., food/dairy/milk)
- Open Food Facts (OFF) is the primary source for food categories (~14K nodes)

Volume is typically used for liquids and mass for solid stuff.  They are rarely combined.

YYY is typically "pcs" or "kg"

Qty is typically not known and should not be specified for vegetables, fruits, etc.  The Lidl shopping receipt says "stk", but in the description it says "per kg", so then the unit is actually kilograms.

If Qty is given on a line, then mass is considered to be "per piece".  So 2 packages @ 500 gram (total mass 1kg) should be specified as `mass:500g qty:2`.

If the user is counting things and informing that he bought 4 onions and it says 521 grams on the receipt, then `qty:4 mass:521/4`

**Category examples** (simple labels auto-expand via OFF/AGROVOC):
- Dairy: `category:milk`, `category:cheese`, `category:yogurt`
- Vegetables: `category:potatoes`, `category:onions`, `category:carrots`
- Chocolate: `category:chocolate`
- Seafood: `category:salmon`, `category:tuna`, `category:shrimp`
- Bread: `category:bread`, `category:baguette`
- Fruit: `category:bananas`, `category:apples`
- Sauces: `category:soy sauce`, `category:ketchup`, `category:mayonnaise`

Best-before - check photos or estimate:
- Fresh milk: ~10 days from purchase
- Potatoes (cool/dark): ~3 months
- Chocolate: ~6-8 months
- Frozen seafood: check package, usually 1-3 months in fridge
- Fresh bread: 3-5 days
- Bananas: 5-7 days

If estimated, the best before should be postfixed with `:EST`.  `bb:2026-12-13:EST`

### 7. Report EAN observations to tingbok

Send product observations (name, category, price, receipt name) to tingbok via PUT.
Do **not** update `ean_cache.json` — that file is no longer used for this purpose.

```bash
curl -s -X PUT https://tingbok.plann.no/api/ean/EAN_CODE \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Product name",
    "categories": ["food/dairy"],
    "quantity": "1l",
    "prices": [
      {"date": "2026-01-24", "shop": "Lidl Varna", "price": 1.02, "currency": "EUR", "unit": "pcs"}
    ],
    "receipt_names": [
      {"name": "BULGARIAN RECEIPT NAME", "shop": "Lidl Varna", "first_seen": "2026-01-24", "last_seen": "2026-01-24"}
    ]
  }'
```

All fields are optional — only include what is known. For products already in tingbok,
the PUT merges in the new data (prices and receipt_names are appended, not replaced).

**Price format:**
- `date`: Purchase date (YYYY-MM-DD)
- `shop`: Store name/location (e.g. `"Lidl Varna"`)
- `price`: Unit price
- `currency`: Currency code (`"EUR"`, `"BGN"`, etc.)
- `unit`: `"pcs"` for per-piece, `"kg"` for per-kilogram

**Receipt name format:**
- `name`: Receipt text exactly as printed (e.g. `"БОНИ Сушеница"`)
- `shop`: Store where the receipt came from
- `first_seen` / `last_seen`: Purchase date (ISO format, both set to the same date initially)

### 8. Update diary with expenses

Use the `diary-update` command to add the expense:

```bash
diary-update -a 34.39 -c EUR -t food --description "Lidl groceries (rice, beans, lentils, beer, meat, milk, mayo, bread, vegetables)"
```

Options:
- `--amount` / `-a`: Amount spent
- `--currency` / `-c`: Currency (default: EUR)
- `--type` / `-t`: Expense type (default: groceries)
- `--description`: Brief description of what was bought
- `--date` / `-d`: Date if not today (YYYY-MM-DD)
- `--section` / `-s`: Section name (default: expenses)
- `--commit`: Auto-commit the diary change
- `--dry-run` / `-n`: Preview without making changes

Or use the full line format:
```bash
diary-update --line "EUR 23.08 - groceries - Lidl (milk, yogurt, spaghetti)"
```

### 9. Copy photos to storage location directories

Photos should be organized by **storage location**, not by shopping trip. Only copy photos that show the product itself or its context — **not** barcode scans or expiry date close-ups. Skip photos for items that will be consumed quickly (fresh produce, bread, etc.).

```bash
# Example: nutmeg goes to spices container F-13
cp ~/s/photos.tobixen/newmi/IMG_nutmeg*.jpg ~/solveig-inventory/photos/F-13/

# Example: sauce goes to food2-spreads
cp ~/s/photos.tobixen/newmi/IMG_sauce*.jpg ~/solveig-inventory/photos/food2-spreads/
```

Create the directory if it doesn't exist: `mkdir -p ~/solveig-inventory/photos/LOCATION-ID/`

**Do NOT** create shopping-date directories like `lidl-2026-01-24/`.
**Do NOT** copy barcode/expiry-date photos — those are only used for EAN lookup during processing.

### 10. Commit changes

Commit to solveig-inventory (diary is committed separately via update-diary --commit):
```bash
cd ~/solveig-inventory
git add inventory.md photo-registry.md
git commit -m "Add Lidl shopping YYYY-MM-DD to inventory"
```

## Scripts location

Scripts are in `~/solveig-inventory/scripts/`:
- `match_lidl_receipt.py` - Match receipt items to EANs
- `format_inventory_entry.py` - Format items for inventory.md

## Example conversation

User: "I did some Lidl shopping, receipt is in lidl_receipts.json, photos taken. Milk and yogurt go to fridge, rest to food1."
