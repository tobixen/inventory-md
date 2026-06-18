# Process Shopping

Staged, resumable workflow for turning a shopping trip into: a spending **ledger**,
**inventory** entries, **tingbok** product observations, and (optionally) **Open
Food Facts** product data + **Open Prices** prices. (A personal workflow may also
record a diary expense line — that step lives in the personal skill, not here.)

Generic guide — uses `$INVENTORY_DIR`, `$PHOTO_DIR`, `$LEDGER` as placeholders;
your personal skill fills in real paths, shops, and credentials. Item format:
`docs/ADDING-ITEMS.md`. Design rationale: `docs/shopping-workflow-redesign-2026-06-06.md`
and `docs/open-prices-integration.md`.

TODO: perhaps those directories should go into a config file?

## Principles

- **Deterministic work in scripts; judgement in a reviewable file.** Receipt
  parsing, barcode/OCR extraction, EAN-candidate lookup, ledger writes,
  validation — all scripted. Matching an EAN, reading a best-before, choosing a
  storage location — done by user/AI editing the staging file, then committed.
- **Gate the irreversible steps.** tingbok PUT, Open Prices/OFF publishing, and
  git commits happen only after the staging file is reviewed and validated. If a
  product↔EAN mapping is unclear, **ask** — never post wrong data to tingbok/OFF.
- **Resumable.** The staging file carries a `status:` block; an interrupted run
  resumes from it. The ledger import is idempotent; inventory/publish steps
  are guarded by the status flags.
- It's better to read structure from `inventory.json` than grepping in `inventory.md`.  The commands `inventory-md lookup` and `inventory-md container` also does the right thing.

## Non-interactive operation (the allowlist contract)

This workflow is meant to run without per-action approval. Claude Code grants
that by pre-approving a list of command **prefixes** (one rule per script /
`inventory-md` subcommand). Two rules follow from how that matching works:

- **One command per shell call. Never chain with `&&`, `|`, `;`, or `$( )`.** A
  chained command is matched as a single opaque string, matches no prefix rule,
  and forces an approval prompt — even when each part would be allowed alone.
  Run the steps as separate calls (or let `pipeline.py` sequence them for you).
- **Read state through scripts, not ad-hoc shell.** Use `shopping_context.py`,
  `inventory-md container`, `inventory-md lookup`, and the `Read` tool — not
  `grep`/`cat`/`awk`/`find` over the markdown, config, or diary. Those probes
  are exactly what an allowlist can't pre-approve.
- **The staging file is the one human gate.** Everything irreversible
  (inventory write, tingbok PUT, OFF/Open Prices publish, git commit) happens
  *after* the staging file is reviewed. Get the review, then the scripts run
  unattended.

Start a trip with the context command instead of grepping for conventions:
```bash
~/inventory-md/scripts/shopping_context.py "SHOP" --diary DIARY_FILE
```
It prints the shop's cached OSM, recent staging files (a schema example to
copy), and recent diary lines for the shop.

## Capture (at the shop)

- User should photograph the **receipt at the shop** so its EXIF GPS marks the location
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
flags. A barcode photo with no date of its own is paired with the date from the
*immediately following* expiry photo, surfaced as `bb` with a `bb_from` pointer
to the source frame; treat a `bb_from` date as a positional guess to sanity-check.
It never decides a match or invents a date.

Photos needs to be manually inspected for barcodes that don't resolves and best-before dates that cannot be read by the OCR.  Run the scripts first and wait for them — the whole point of `extract_barcodes.py`/`shop_import.py` is to make manual photo inspection unnecessary.

Default assumption: each photo holds **nothing but a barcode and/or an expiry date**, and a product's best-before is either in its barcode photo, in the immediately following photo, or supplied by the user.

## Stage 2 — review (AI, or by user in an editor)

Edit the staging file: for each item pick the right `ean` from `ean_candidates`
(or add one), set `name`, `category`, `bb` (from the photo's `bb` candidate, else
`:EST`), `location`, and a unique `inventory_id`. Attach label `photos`. Clear
`needs_review`. **Set `to_tingbok: true` for items with a confirmed EAN,
`to_tingbok: false` for by-weight produce and items without a barcode.** The
importer scaffolds `to_tingbok: null` as a deliberate reminder — leave no item
at `null` before committing. This is the checkpoint to fix mistakes **before**
anything irreversible. Re-running stage 1 is safe (idempotent ledger; staging is yours).

**Categories — be specific.** Use the most specific leaf category, not a broad
bucket (`tomatoes`, not `vegetables`/`vegetable`; `cheese/kashkaval`, not
`cheese`; `food/eggs`, `fresh-milk`). Broad buckets are useless for the
shopping-list generator and expiry tracking, and `check_quality.py` **fails**
on them (`vegetables`, `fruit`, `nuts`, `meat`, `dairy`, `cheese`, `misc`, …).
A broad/parent category is allowed only when no narrower concept fits — then
exempt that item with the tag `category-broad-ok` (or run with
`--allow-broad-categories`). Get the canonical slug from tingbok:
`GET /api/lookup/{term}` returns the `id` to use. A category new to your
inventory won't be in the local `vocabulary.json` yet — that's expected; ask
tingbok, don't invent one. Watch mistranslated receipt names (Bulgarian
`КАРТОФИ ЛИЛАВИ` "purple potatoes" were actually purple **sweet** potatoes).

**Quantities — count, not weight.** For by-weight produce, `qty` is the piece
**count** (3 peppers), never the kg weight (`qty: 0.543` is wrong). Put the
**total** weight in `mass:` (`543g`) and the per-kg price in `price` with
`price_unit: kg`; the importer writes `qty:3 mass:543g/3 price:EUR:.../kg`
(single piece → bare `mass:543g`). Packaged multi-buys use the total too
(2×1l milk → `volume: 2l` → `volume:2l/2`). **Ask the user for the count**
when it isn't obvious from the receipt.

**tingbok cross-check (gate — the user MUST respond to these before you proceed):**
for every `ean` you assign, compare the tingbok record to what you bought:

- tingbok **has** the EAN and its description **matches** the purchase → fine,
  proceed silently.
- tingbok has the EAN but its description **does not match** (wrong product,
  wrong quantity) → **flag it and stop**; the user MUST confirm or correct the
  EAN before anything irreversible.
- the EAN is **not in tingbok** → **flag it**; the user MUST confirm the EAN.
- a **food** product is not in tingbok → flag it and encourage the user to take
  front/ingredients/nutrition/packaging photos so it can be posted to OFF.

Batch these flags into one round of questions rather than asking item-by-item.

## Stage 3 — commit (script + thin AI, gated)

**Drive it with `pipeline.py` — one command, not a hand-chained pipeline.**
Once the staging file is reviewed, `pipeline.py` runs the ledger → inventory →
tingbok steps in order (reading/advancing the `status:` block, resumable) and
then validates (`parse` + `check_quality`):
```bash
~/inventory-md/scripts/pipeline.py $INVENTORY_DIR/staging/shopping-YYYY-MM-DD.yaml           # dry run — plan + previews
~/inventory-md/scripts/pipeline.py $INVENTORY_DIR/staging/shopping-YYYY-MM-DD.yaml --commit  # run pending stages + validate
```
A `status:` value of `done` skips a stage; `skipped` skips it permanently (e.g.
`tingbok_push: skipped` for non-food hardware). On a stage failure it stops and
leaves the status unchanged, so re-running resumes there. `--from STAGE`
force-restarts at a stage. The remaining steps (photos, diary, publishing,
commit) stay manual — see below. The numbered steps that follow are *what the
driver runs*; run them individually only to debug.

1. **Validate** — every item complete; every item has a unique `ID`; food items
   have a `bb` (or `:EST`); no duplicate IDs. (Folded into the inventory write
   and the final quality gate.)
2. **Ledger** — append/enrich `$LEDGER` (one row per line item):
   ```bash
   ~/inventory-md/scripts/ledger.py import-staging $INVENTORY_DIR/staging/shopping-YYYY-MM-DD.yaml --ledger $LEDGER
   ```
   Append-or-enrich: a raw row from a receipt importer is later filled in place
   with `ean`/`category`/`inventory_id` by the reviewed staging import (matched on
   `date, shop, receipt_name, qty, unit_price, total`; nulls never overwrite).
3. **Inventory** — write every reviewed row straight from the staging file; do
   **not** hand-edit `inventory.md`:
   ```bash
   ~/inventory-md/scripts/inventory_import.py $INVENTORY_DIR/staging/shopping-YYYY-MM-DD.yaml            # dry run — preview the plan
   ~/inventory-md/scripts/inventory_import.py $INVENTORY_DIR/staging/shopping-YYYY-MM-DD.yaml --commit
   ```
   It reads each item's `location` (→ container), `category`, `inventory_id`,
   `ean`, `bb` (`:EST` honoured), `qty`/`unit` (weighed lines → `mass`/`volume`)
   and `price`, formats the line, inserts it in the right section, and runs the
   QA checks as part of the write: duplicate `ID:`, food-without-`bb:` (hard
   error; `--no-bb-check` to override for fresh produce), and category resolution
   (`--strict` to fail on unresolved). `add_to_inventory: false` rows are skipped;
   rows whose `inventory_id` already exists are reported as `exists` and skipped,
   so re-running is safe. Missing `location` defaults to `floating`. So the review
   step (Stage 2) must fill `location`, `category`, `bb` and a unique
   `inventory_id` per row — there is nothing left to edit by hand here.
   This is `inventory-md add` applied per row; see `docs/ADDING-ITEMS.md` for the
   field reference and the single-item CLI.
4. **Photos** (manual) — copy only **label** photos to `photos/LOCATION-ID/`; skip
   barcode/expiry close-ups; skip fast-consumed items. Never `git add` photos.
5. **tingbok** — push price + receipt-name observations for reviewed EANs (a
   merge PUT; prices/receipt_names appended, re-running is safe). Use the script,
   never a raw `curl`:
   ```bash
   ~/inventory-md/scripts/tingbok_push.py $INVENTORY_DIR/staging/shopping-YYYY-MM-DD.yaml            # dry run
   ~/inventory-md/scripts/tingbok_push.py $INVENTORY_DIR/staging/shopping-YYYY-MM-DD.yaml --commit
   ```
   It pushes only items with `to_tingbok: true` and an `ean`; per-item
   `tingbok_name`/`tingbok_categories`/`tingbok_quantity` override a poor or
   missing tingbok name.
6. **Quality gate** — regenerate and check (flags food without best-before,
   duplicate IDs, unresolvable categories). Two separate commands, not chained:
   ```bash
   inventory-md parse inventory.md
   ~/inventory-md/scripts/check_quality.py inventory.json
   ```
7. **Commit** (manual) `inventory.md` (+ staging file, + photo-registry.md if used).
   The ledger is committed in its own repo. (Personal workflows may add a diary
   expense line as part of this stage — see the personal skill.)

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
| `shopping_context.py` | read-only trip context: shop OSM, recent staging, diary lines |
| `extract_barcodes.py --best-before` | barcodes + best-before OCR per photo |
| `bb_dates.py` | OCR-text → best-before date candidates (library) |
| `shop_import.py` | receipt + photos → staging YAML |
| `pipeline.py` | drive Stage-3 commit (ledger→inventory→tingbok→validate) from `status:` |
| `ledger.py` | purchases.jsonl: import / query / consumed |
| `inventory_import.py` | write reviewed staging rows into `inventory.md` |
| `tingbok_push.py` | push reviewed price/receipt-name observations to tingbok |
| `check_quality.py` | validation gate (food-bb, dup IDs, categories) |
| `off_upload.py` | create missing OFF products |
| `openprices_publish.py` / `op_auth.py` | publish prices / mint token |

`tingbok` (`GET/PUT /api/ean/{ean}`, `GET /api/ean/search?receipt_name=`) is the
EAN/category/price aggregator. There is **no `ean_cache.json`** — use tingbok.
