# Process Shopping

Staged, resumable workflow for turning a shopping trip into: a spending **ledger**,
**inventory** entries, a **diary** expense line, **tingbok** product observations,
and (optionally) **Open Food Facts** product data + **Open Prices** prices.

Generic guide — uses `$INVENTORY_DIR`, `$PHOTO_DIR`, `$LEDGER` as placeholders;
your personal skill fills in real paths, shops, and credentials. Item format:
`docs/ADDING-ITEMS.md`. Design rationale: `docs/shopping-workflow-redesign-2026-06-06.md`
and `docs/open-prices-integration.md`.

## Principles

- **Deterministic work in scripts; judgement in a reviewable file.** Receipt
  parsing, barcode/OCR extraction, EAN-candidate lookup, ledger writes,
  validation — all scripted. Matching an EAN, reading a best-before, choosing a
  storage location — done by you/AI editing the staging file, then committed.
- **Gate the irreversible steps.** tingbok PUT, Open Prices/OFF publishing, and
  git commits happen only after the staging file is reviewed and validated. If a
  product↔EAN mapping is unclear, **ask** — never post wrong data to tingbok/OFF.
- **Resumable.** The staging file carries a `status:` block; an interrupted run
  resumes from it. The ledger import is idempotent; diary/inventory/publish steps
  are guarded by the status flags.

## Capture (at the shop)

- Photograph the **receipt at the shop** so its EXIF GPS marks the location
  (used for Open Prices). Photograph product labels **upright and legible** — the
  best-before date is read by OCR, which honours EXIF orientation but can't read
  faint/sideways print.
- For products that exists in OFF, there should be one photo with the barcode and the next should be with the expiry date.  If both fits into the same photo, only one photo is taken.  For photos of products not existing in off, there should be photos of the front, ingrediences, nutrition information and package recycling information.

## Stage 1 — import (deterministic)

```bash
# Barcodes + best-before OCR on every photo (barcode shots included):
~/inventory-md/scripts/extract_barcodes.py --best-before $PHOTO_DIR/IMG_*.jpg --json > barcodes.json

# Receipt + photos -> human-correctable staging file (EAN candidates via tingbok
# reverse receipt-name search; photos classified barcode/expiry/label):
~/inventory-md/scripts/shop_import.py --receipt RECEIPT.json --barcodes-json barcodes.json \
    --out $INVENTORY_DIR/staging/shopping-YYYY-MM-DD.yaml
```

**One staging file per shop visit** (canonical flat single-shop schema —
`session, shop, currency, items[]`; no multi-shop `shops:` wrapper). If a day
has more than one visit, suffix the file with the shop, e.g.
`shopping-YYYY-MM-DD-lidl.yaml`; the importer rejects a multi-shop file.

Receipt source: a JSON file from a receipt parser, or OCR/read a photographed
receipt into the same shape (`date, shop, total, items[name,price,quantity]`).
The importer emits one row per line item with `ean_candidates`, a classified
`loose_photos` list (each may carry a `bb` from the OCR pass), and `needs_review`
flags. It never decides a match or invents a date.

## Stage 2 — review (you / AI, in an editor)

Edit the staging file: for each item pick the right `ean` from `ean_candidates`
(or add one), set `name`, `category`, `bb` (from the photo's `bb` candidate, else
`:EST`), `location`, and a unique `inventory_id`. Attach label `photos`. Clear
`needs_review`. **Set `to_tingbok: true` for items with a confirmed EAN,
`to_tingbok: false` for by-weight produce and items without a barcode.** The
importer scaffolds `to_tingbok: null` as a deliberate reminder — leave no item
at `null` before committing. This is the checkpoint to fix mistakes **before**
anything irreversible. Re-running stage 1 is safe (idempotent ledger; staging is yours).

## Stage 3 — commit (script + thin AI, gated)

1. **Validate** — every item complete; every item has a unique `ID`; food items
   have a `bb` (or `:EST`); no duplicate IDs.
2. **Ledger** — append/enrich `$LEDGER` (one row per line item):
   ```bash
   ~/inventory-md/scripts/ledger.py import-staging $INVENTORY_DIR/staging/shopping-YYYY-MM-DD.yaml --ledger $LEDGER
   ```
   Append-or-enrich: a raw row from a receipt importer is later filled in place
   with `ean`/`category`/`inventory_id` by the reviewed staging import (matched on
   `date, shop, receipt_name, qty, unit_price, total`; nulls never overwrite).
3. **Inventory** — add lines to the right container in `inventory.md`:
   ```
   * category:CONCEPT ID:ITEM-ID EAN:CODE bb:YYYY-MM[:EST] qty:N mass:Xg volume:Xl price:CUR:X/pcs NAME
   ```
   See `docs/ADDING-ITEMS.md`. **Every** item needs an `ID:`; food items need a
   `bb:` (estimate with `:EST` if unknown). To inspect a container — its existing
   items, the `category`/`ID` conventions in use, where to insert — query the
   parsed `inventory.json`, do **not** grep/awk the markdown (section boundaries
   are not regex-friendly and you'll miss items):
   ```bash
   inventory-md parse inventory.md   # refresh inventory.json
   jq -r '.. | objects | select(.id?=="food4" and .items?) | .items[].raw_text' inventory.json
   ```
   Then anchor the `Edit` on the last existing item line in that container.
4. **Photos** — copy only **label** photos to `photos/LOCATION-ID/`; skip
   barcode/expiry close-ups; skip fast-consumed items. Never `git add` photos.
5. **tingbok** — PUT observations for reviewed EANs (merges; prices/receipt_names
   appended):
   ```bash
   curl -s -X PUT https://tingbok.plann.no/api/ean/EAN -H 'Content-Type: application/json' -d '{
     "name":"...","categories":["food/dairy"],"quantity":"1l",
     "prices":[{"date":"YYYY-MM-DD","shop":"Shop","price":1.02,"currency":"EUR","unit":"pcs"}],
     "receipt_names":[{"name":"AS PRINTED","shop":"Shop","first_seen":"YYYY-MM-DD","last_seen":"YYYY-MM-DD"}]}'
   ```
6. **Quality gate** — regenerate and check (flags food without best-before,
   duplicate IDs, unresolvable categories):
   ```bash
   inventory-md parse inventory.md && ~/inventory-md/scripts/check_quality.py inventory.json
   ```
7. **Diary** — one expense line per shop (separate git repo):
   ```bash
   diary-update -d YYYY-MM-DD -a AMOUNT -c EUR -t food --description "Shop (items…)"
   ```
8. **Commit** `inventory.md` (+ staging file, + photo-registry.md if used). Diary
   and ledger are committed in their own repos.

## Stage 4 — contribute upstream (optional, gated)

**Missing OFF products** (EANs that don't resolve in OFF) — create them from a
curated YAML with front/ingredients/nutrition/packaging photos:
```bash
~/inventory-md/scripts/off_upload.py --products off-products.yaml          # dry run
~/inventory-md/scripts/off_upload.py --products off-products.yaml --commit  # writes to OFF
```

**Open Prices** — publish receipt prices (auth once via `op_auth.py`):
```bash
~/inventory-md/scripts/openprices_publish.py --shop "Shop" --date YYYY-MM-DD \
    --proof RECEIPT.jpg --osm WAY:NNN [--discount EAN=GROSS:SALE] [--commit]
# barcodeless items as CATEGORY prices:
    --no-products --category-price "en:baguettes=0.17,was=0.45,type=SALE"
```
Shop location is a **confirmed** OSM object (cached per shop), never auto-geocoded
— receipt photos are often taken away from the shop. PRODUCT prices must not set
`price_per`. Both OFF and Open Prices are **public** — treat as irreversible-ish
(Open Prices rows are deletable; you own them).

## Queries

```bash
~/inventory-md/scripts/ledger.py query --category food --since YYYY-MM-DD --until YYYY-MM-DD
~/inventory-md/scripts/ledger.py consumed --inventory inventory.md --since … --until …
```
`consumed` joins ledger rows to items removed from `inventory.md` (git history) to
cost what was actually used in a period — only resolves for rows enriched (ean/
category/inventory_id) through the reviewed staging flow.

## Tools

| Script (`~/inventory-md/scripts/`) | Role |
|---|---|
| `extract_barcodes.py --best-before` | barcodes + best-before OCR per photo |
| `bb_dates.py` | OCR-text → best-before date candidates (library) |
| `shop_import.py` | receipt + photos → staging YAML |
| `ledger.py` | purchases.jsonl: import / query / consumed |
| `check_quality.py` | validation gate (food-bb, dup IDs, categories) |
| `off_upload.py` | create missing OFF products |
| `openprices_publish.py` / `op_auth.py` | publish prices / mint token |

`tingbok` (`GET/PUT /api/ean/{ean}`, `GET /api/ean/search?receipt_name=`) is the
EAN/category/price aggregator. There is **no `ean_cache.json`** — use tingbok.
