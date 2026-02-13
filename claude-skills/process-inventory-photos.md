# Process Inventory Photos

Process photos of inventory locations (boxes, shelves, cupboards, storage areas) and update the inventory system.

## Trigger
Use when the user asks to process inventory photos, e.g.:
- "process photos from ~/s/photos.tobixen/newmi/IMG_2026*"
- "there are new inventory photos"
- "process the new photos"

## Workflow

### 1. Find and count photos
```bash
ls ~/s/photos.tobixen/newmi/PATTERN* | wc -l
ls ~/s/photos.tobixen/newmi/PATTERN*
```

or, if no pattern is given:

```bash
find ~/s/photos.tobixen/ -type f -mmin -60
```

ALL photos have to be processed.

### 2. Extract barcodes FIRST
Before analyzing photos visually, extract any barcodes to get product info:
```bash
~/inventory-system/scripts/extract_barcodes.py ~/s/photos.tobixen/newmi/PATTERN*.jpg
```

This will:
- Extract any EAN/UPC barcodes visible in the photos
- Look up product info in Open Food Facts
- Output product names, brands, and quantities

**Use this output while analyzing photos** - you'll already know what many products are.

### 2b. Manual barcode/article lookups
For items not in Open Food Facts, try manual lookups:

**BILTEMA articles** (Art. XX-XXXXX format):
- Try: `https://www.biltema.no/search?q=XXXXX` (note: search pages may not render well)
- Record article number in inventory as `biltema:XX-XXXXX`

**Clas Ohlson articles** (XX.XXXX-X format):
- Try: `https://www.clasohlson.com/no/search?q=XXXXXXX`

**EAN codes**: Always include in inventory as `EAN:XXXXXXXXXXXXX`

**Always record from photos:**
- EAN/UPC barcodes
- Article/product numbers (Art., Prod.nr, Item No.)
- Model numbers
- Serial numbers (for valuable items)
- Best-before dates (bb:YYYY-MM-DD)
- Batch/lot numbers (for recalls)

### 3. View photos to identify boxes and items
- Look for labels, or ask the user about container/location.  The labels are often on the format A-03, TB-42, etc
- When some pictures are missing label, quite often the label will be the same as on the previous box
- Identify items with details: brand, model, specifications, part numbers
- Use the barcode extraction output from step 2 for product identification
- Text should be saved both in the original language and the inventory language (English for Solveig, Norwegian for Furuset).
- Note items that are unclear with TODO tag

### 3b. Ask about unclear items using structured questions
After viewing all photos, collect unclear items and ask the user using the AskUserQuestion tool with multiple-choice options. Group related questions together (up to 4 questions per call). This is more efficient than asking one question at a time.

Example questions:
- "Is the black square item in photo X a solar panel?" with options like "Yes, folding solar panel" / "No, something else"
- "Are photos X and Y showing the same bag or different bags?" with options like "Same bag" / "Two different bags"
- "What brand are these bike panniers?" with options like "Decathlon" / "Unknown brand" / "Not panniers"

This structured approach helps identify items faster and avoids back-and-forth.

### 4. Create/update photo-registry.md
Map each photo to visible items:
```markdown
| Photo | Items Visible |
|-------|--------------|
| IMG_xxx.jpg | Item description, another item |
```

### 5. Copy photos to correct directories
```bash
mkdir -p photos/{BOX-ID}
cp SOURCE_PHOTOS photos/{BOX-ID}/
```

### 6. Update inventory.md
Add items with categories, IDs, quantities, and measurements:
```markdown
* category:concept ID:category-shortname qty:N mass:Xg Item description (brand, model)
```

**Categories vs Tags:**
- `category:` - Product classification (what is it). Use SKOS hierarchy expansion.
- `tag:` - Attributes (what state/condition). Simple labels.

**Category syntax:**
- Simple label: `category:potatoes` - expanded to SKOS hierarchy (e.g., food/vegetables/potatoes)
- Full path: `category:food/vegetables/potatoes` - kept as-is
- Multiple: `category:oatmeal,breakfast` - comma-separated

**Category sources** (priority order):
1. **OFF (Open Food Facts)** - Best for food categories (~14K nodes with translations)
2. **AGROVOC** - Agricultural vocabulary (good for produce, farming terms)
3. **DBpedia** - General knowledge (tools, equipment, non-food items)

**Examples:**
- `category:soy sauce` → food/condiments/sauces/soy_sauces (from OFF)
- `category:potatoes` → food/vegetables/potatoes (from OFF or AGROVOC)
- `category:hammer` → tool (from DBpedia)
- `category:bedding` → bedding (from DBpedia) - for pillows, sleeping bags

**Tags** for attributes:
- `tag:condition:new`, `tag:condition:used`
- `tag:TODO` - needs review
- `tag:brand:makita`

Common top-level categories: food, tools, electronics, safety, boat, chemicals, consumables, documents
Cross-cutting tags: electric, battery, manual, consumable, spare

**Quantity and measurements:**
- `qty:N` - number of identical items (e.g., `qty:3` for 3 packs)
- `mass:Xg` or `mass:Xkg` - weight per unit (e.g., `mass:500g`, `mass:1kg`)
- `volume:Xl` or `volume:Xml` - volume per unit (e.g., `volume:1l`, `volume:400ml`)

### 7. Commit changes
```bash
git add inventory.md photo-registry.md
git commit -m "Add BOX-ID items from photo session DATE"
```

## Barcode Lookup

If you can see an EAN/barcode in a photo that wasn't automatically extracted, look it up manually:
```bash
~/inventory-system/scripts/extract_barcodes.py --lookup 5701234567890
```

This queries Open Food Facts and returns the product name, brand, and quantity.

**In inventory.md**, include EAN when available:
```markdown
* tag:food/condiment ID:ketchup-heinz EAN:5000157024671 bb:2027-03 Heinz Tomato Ketchup (570g)
```

## Photo Registry Format

The `photo-registry.md` file maps photos to items using markdown tables:

```markdown
# Photo-Item Registry

## Session: 2026-01-03

### TB-03 (Box description)

| Photo | Item IDs |
|-------|----------|
| IMG_20260103_224919.jpg | ID:drill-bosch |
| IMG_20260103_225014.jpg | ID:gloves-nyroca, ID:goggles-tb03 |
| IMG_20260103_225018.jpg | (overview) |
| IMG_20260103_225031.jpg | ID:tea-caykur (best-before label: 2028-10-04) |
```

**Structure:**
- Session headers with dates (`## Session: YYYY-MM-DD`)
- Container/location headers (`### CONTAINER-ID`)
- Tables with `| Photo | Item IDs |` columns

**Item IDs format:** `ID:category-shortname` (e.g., `ID:drill-bosch`, `ID:wrench-force17`)

**Special entries:**
- `(overview)` - Overview photo of entire container
- `(box label)` - Photo of the container label
- `(blurry)` - Unusable photo
- `(not in inventory)` - Item visible but not tracked
- `(best-before: DATE)` - Notes about visible labels

## Photo Registry JSON Generation

When running `inventory-md parse`, the system automatically:
1. Parses `photo-registry.md` if it exists
2. Generates `photo-registry.json` with:
   - `photos`: Map of filename → {items, container, session, notes}
   - `items`: Reverse index of item ID → [filenames]
   - `containers`: Map of container → [filenames]

This JSON enables the search.html web interface to:
- Show a 📷 icon next to items that have photos
- Display item-specific photos when clicking the icon
- Filter gallery view to show only photos of matching items

## Notes
- Photos are NOT stored in git (listed in .gitignore)
- Use sync-photos.sh to rsync photos to server
- Items needing clarification get tag:TODO

## Language per instance
- **solveig-inventory**: English tags and descriptions
- **furusetalle9-inventory**: Norwegian tags and descriptions

### Norwegian tags (furusetalle9-inventory)

**Hierarchical tags** (category/subcategory):
- `tag:barn/leker` - children's toys
- `tag:barn/kunst` - children's art
- `tag:klær/vinter` - winter clothes
- `tag:klær/friluft` - outdoor clothes
- `tag:elektronikk/belysning` - electronic lighting
- `tag:sport/sykkel` - bicycle/cycling
- `tag:kjøkken/servise` - kitchen tableware
- `tag:hjem/oppbevaring` - home storage

**Cross-cutting tags** (comma-separated):
- `tag:klær,barn` - children's clothes (clothes + cross-cutting "barn")
- `tag:sko,barn` - children's shoes
- `tag:verktøy,elektronikk` - electronic tools
- `tag:diverse,TODO` - miscellaneous needing review

**Common Norwegian categories:**
barn (children), klær (clothes), sko (shoes), elektronikk (electronics), verktøy (tools), kjøkken (kitchen), bad (bathroom), helse (health), sport, friluft (outdoor), hage (garden), bil (car), hjem (home), belysning (lighting), dokumenter (documents), bok (books), jul (christmas), leker (toys), tekstil (textile), hobby, oppbevaring (storage), diverse (misc), veske (bags)

**Cross-cutting modifiers:**
barn (children's), elektronikk (electronic), TODO, pappas (dad's), mammas (mom's), personlig (personal)

Reference: See `inventory-system/tag-mapping.json` for full Norwegian-English mappings.

## Item IDs for cross-referencing

Use unique IDs to link items between inventory.md and photo-registry.md.

**IMPORTANT:** When you assign an ID in photo-registry.md, you MUST also add that same ID to the corresponding item in inventory.md. The ID must exist in BOTH files for cross-referencing to work. Failing to do this will break photo-to-item linking.

**ID format:** `ID:category-shortname` or `ID:category-shortname-number`

Examples: `ID:drill-einhell1`, `ID:wrench-force17`, `ID:gloves-nyroca1`

Make sure the IDs are unique, add some postfix like `-02` if necessary

**Workflow for assigning IDs:**
1. Choose a descriptive ID for the item (e.g., `ID:bagasjevekt-travel-scale`)
2. Add the ID to the item line in **inventory.md** (after tag:, before description)
3. Use the same ID in **photo-registry.md** to reference the item in photos

**In inventory.md:**
```markdown
* tag:tools,electric ID:drill-einhell1 Einhell TC-ID 650 E impact drill (650W, 230V, 13mm chuck)
* tag:tools ID:wrench-force17 Force combination wrench 17mm
* tag:food/cereal/oats ID:oatflakes-fine bb:2026-10 qty:8 mass:500g Fine Oat Flakes
* tag:food/bread/rusks ID:rusks-tastino bb:2026-08 qty:3 mass:360g Tastino Wheat & Rye rusks
```

**In photo-registry.md:**
```markdown
| IMG_20260103_233627.jpg | ID:drill-einhell1 |
| IMG_20260103_225647.jpg | ID:wrench-force17, ID:wrench-force18 |
```

Benefits:
- Short, unique references instead of repeating long descriptions
- Easy to grep/search across files
- Descriptions can be updated without breaking registry links
- Multiple items per photo: comma-separated IDs

## Storage locations
Not limited to boxes - can be:
- Temporary boxes (TA-01, TB-02, etc.)
- Shelves (e.g., "Garage shelf 3")
- Cupboards, drawers, boat compartments
- Any named storage area

If no label is visible, ask the user for the location name.

## Best-before dates (bb:)

Food products and other perishables should include a best-before date tag.

**Format:** `bb:YYYY-MM` or `bb:YYYY-MM-DD` or `bb:YYYY-MM-DDTHH:MM`

Examples:
- `bb:2026-10` - October 2026
- `bb:2026-01-15` - January 15, 2026
- `bb:2026-01-04T15:44` - with time (rare)

**In inventory.md:**
```markdown
* tag:food ID:pasta-barilla bb:2026-10 Barilla spaghetti (500g)
* tag:food ID:tuna-canned bb:2027-03 Canned tuna in oil (3-pack)
```

This enables:
- Sorting items by expiration date
- Alerts for soon-to-expire products
- Inventory rotation planning
