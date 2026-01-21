# Process Lidl Shopping

Process a Lidl shopping receipt and update the boat inventory.

## When to use

Use this skill when the user mentions:
- Lidl shopping/receipt
- Processing a shopping receipt
- Adding groceries to inventory

## Workflow

### 1. Read the receipt

The Lidl receipt is stored at `~/shopping-analyzer/lidl_receipts.json`. Read the most recent entry (last item in the array).

Receipt fields:
- `purchase_date`: Date in format "YYYY.MM.DD"
- `total_price_no_saving`: Total amount in local currency. EUR for Bulgaria
- `store`: Store location
- `items`: Array of purchased items with `name`, `price`, `quantity`

### 2. Extract barcodes and best-before dates from photos

Run the barcode extraction script on recent photos:
```bash
~/inventory-system/scripts/extract_barcodes.py ~/s/photos.tobixen/newmi/IMG_*.jpg
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
* tag:food/CATEGORY ID:ITEM-ID EAN:EANCODE bb:YYYY-MM qty:N mass:Xg volume:Xl price:EUR:XXX/YYY PRODUCT NAME
```

Volume is typically used for liquids and mass for solid stuff.  They are rarely combined.

YYY is typically "pcs" or "kg"

Qty is typically not known and should not be specified for vegetables, fruits, etc.  The Lidl shopping receipt says "stk", but in the description it says "per kg", so then the unit is actually kilograms.

If Qty is given on a line, then mass is considered to be "per piece".  So 2 packages @ 500 gram (total mass 1kg) should be specified as `mass:500g qty:2`.

If the user is counting things and informing that he bought 4 onions and it says 521 grams on the receipt, then `qty:4 mass:521/4`

Tags by category:
- Dairy: `tag:food/dairy/milk`, `tag:food/dairy/cheese`
- Vegetables: `tag:food/vegetable/potato`, `tag:food/vegetable/onion`
- Chocolate: `tag:food/snacks/chocolate`
- Seafood: `tag:food/seafood`
- Bread: `tag:food/bread`
- Fruit: `tag:food/fruit/banana`

Best-before - check photos or estimate:
- Fresh milk: ~10 days from purchase
- Potatoes (cool/dark): ~3 months
- Chocolate: ~6-8 months
- Frozen seafood: check package, usually 1-3 months in fridge
- Fresh bread: 3-5 days
- Bananas: 5-7 days

If estimated, the best before should be postfixed with `:EST`.  `bb:2026-12-13:EST`

### 7. Update EAN cache

Add new products to `~/solveig-inventory/ean_cache.json` with `lidl_receipt_name` field:
```json
{
  "EAN_CODE": {
    "ean": "EAN_CODE",
    "name": "Product name",
    "brand": "Brand",
    "quantity": "amount",
    "categories": "Category",
    "lidl_receipt_name": "BULGARIAN RECEIPT NAME",
    "source": "manual"
  }
}
```

### 8. Update diary with expenses

Use the `~/bin/update-diary` script to add the expense:

```bash
~/bin/update-diary --amount 23.08 --description "Lidl (milk, yogurt, spaghetti, bread, rum, meat)"
```

Options:
- `--amount` / `-a`: Amount spent
- `--currency` / `-c`: Currency (default: EUR)
- `--type` / `-t`: Expense type (default: groceries)
- `--description`: Brief description of what was bought
- `--date` / `-d`: Date if not today (YYYY-MM-DD)
- `--commit`: Auto-commit the diary change
- `--dry-run` / `-n`: Preview without making changes

Or use the full line format:
```bash
~/bin/update-diary --line "EUR 23.08 - groceries - Lidl (milk, yogurt, spaghetti)"
```

### 9. Commit changes

Commit to solveig-inventory (diary is committed separately via update-diary --commit):
```bash
cd ~/solveig-inventory
git add inventory.md ean_cache.json
git commit -m "Add Lidl shopping YYYY-MM-DD to inventory"
```

## Scripts location

Scripts are in `~/solveig-inventory/scripts/`:
- `match_lidl_receipt.py` - Match receipt items to EANs
- `format_inventory_entry.py` - Format items for inventory.md

## Example conversation

User: "I did some Lidl shopping, receipt is in lidl_receipts.json, photos taken. Milk and yogurt go to fridge, rest to food1."
