# Shopping pipeline — issues found while processing Lidl 2026-06-07

Notes captured during a real run (`staging/shopping-2026-06-07.yaml`) for later
fixing. Ordered roughly by impact.

## Scripts

1. **Staging schema mismatch (silent data loss).**
   `shop_import.py` emits a *flat single-shop* schema (top-level
   `session` / `shop` / `items:`). But the previously committed
   `shopping-2026-06-06.yaml` and the personal skill example use a `shops:`
   list wrapper (multi-shop). `ledger.py import-staging` only understands the
   flat schema and, given the `shops:` layout, imports **0 rows with no
   warning** ("0 added (of 0 rows)"). Fixes:
   - Pick one canonical schema (flat vs. `shops:`-list) and make every consumer
     agree.
   - If `import-staging` finds 0 items, or sees an unexpected top-level `shops:`
     key, it should **warn/exit non-zero**, not succeed silently.
   - Update the personal skill's example to the canonical schema.

2. **`extract_barcodes.py` misses easily-readable barcodes and invents others.**
   Of the photographed barcodes it missed several a human read at a glance
   (cooking cream 20531072, cheese 20709440, potato puree 20163822, Balkansko
   3800135310060, fusili 4056489177548) and produced **spurious EAN13s from
   reflections/curved cans** (deo photo → 9333672970335 + 0053200005672, both
   bogus). Consider: deskew/rotation, perspective-undistort for cans, multiple
   decoders (zbar + zxing), and a confidence/agreement filter.

3. **Best-before OCR is weak on the hard cases.** Dot-matrix dates on shiny can
   bottoms, mirrored prints, and curved jars were almost all unread
   (`ocr_date_candidates: []`). One barcode digit-run ("2016 3822" on the potato
   puree) was misread as a *date* `2016-06-06`. Need: don't treat near-barcode
   numerics as dates; better contrast handling for laser/dot-matrix on metal.

4. **No auto-join of photo barcodes → receipt items.** `shop_import.py` already
   classifies each photo and resolves the barcode to a product via tingbok GET
   (the genuinely useful signal), but still leaves `ean: null` on every receipt
   line. The reverse *receipt-name* search it does use is low value (e.g.
   ОВЕСЕНИ ЯДКИ ФИНИ → "Chili meat sticks" @0.51). Flip the priority: match the
   tingbok-resolved photo products to receipt lines (by resolved name/category,
   qty, price, order) and pre-fill `ean`, leaving only ambiguous lines for review.

5. **`shop_import.py` not executable.** Direct `~/inventory-md/scripts/shop_import.py`
   → "Permission denied"; had to call via `python scripts/...`.
   `extract_barcodes.py` runs fine directly. Fix the exec bit / shebang
   consistently across scripts.

## Data model

6. **One location per item — can't split a qty across locations.** 14 beer cans
   were split fridge/food1 (e.g. 4× 3%: 3 fridge + 1 food1). The staging
   `location:` field is a single string; I used an ad-hoc `pantry-fridge+food1`
   + a `notes:` line, and split into two lines by hand in `inventory.md`.
   Consider `locations: [{location, qty}, ...]`.

7. **`price` unit ambiguity for by-weight items.** Cabbage 1.768 kg @ 0.59/kg:
   `price` is per-kg but `staging_to_rows` does `total = price*qty` (only correct
   because `line_total` is supplied). Document that `price` is the unit price in
   the receipt's `unit`, and prefer trusting `line_total` for weighed goods.

## tingbok (service — repo `~/tingbok`)

T1. **`PUT /api/ean/{ean}` rejects observation-only updates.** Adding just a
   price + receipt_name returns `422 "At least one of 'categories' or 'name'
   must be provided"`. Recording a *price* shouldn't require re-supplying
   name/categories. Either relax the rule for price/receipt-name-only bodies, or
   document it. Workaround in `scripts/tingbok_push.py`: GET first and echo the
   current name back so the merge doesn't wipe it — but that's a wasteful extra
   round-trip the API forces on every caller.

T2. **`inventory-md parse` pushes low-quality observations.** It upserts
   name/categories/prices from inventory.md to tingbok, but:
   - prices are stored with **`date: null, shop: null`** (inventory has no shop
     or date) — near-useless price rows;
   - the product **name is overwritten with the inventory free-text NAME**,
     leaking inventory-only notes into tingbok (this run polluted
     3800135310060 with `"… (3 of 6; rest in fridge)"`; had to hand-fix
     `ean-db.json`). inventory-sourced names should be lower-priority than a
     curated name, or skipped; inventory-sourced prices should be marked or
     omitted.

## Inventory / instructions

8. **No freezer container.** Frozen goods (shrimp) have nowhere to live; they
   get placed in `pantry-fridge` with a note. Consider a freezer/coldest-spot
   sub-location. (On this boat "frozen" thaws fast — bb estimated at +3 days.)

9. **Container lookup.** Confirmed good practice (now in the generic guide):
   inspect containers via parsed `inventory.json` + `jq`, not by grepping the
   markdown. Worth a one-liner helper script (`container-items <id>`).
