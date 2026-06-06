# Shopping / inventory workflow redesign

*Date: 2026-06-06. This is a personal-workflow design note (Tobias' Lidl/boat
setup), but the structural ideas — staged pipeline, append-only purchase ledger,
deterministic-vs-judgment split, validation gates — are relevant to the
`inventory-md` project generally, so it lives here in `docs/`.*

> **Status:** design accepted. Decisions taken (2026-06-06):
> adopt **both** the staged pipeline **and** the `purchases.jsonl` ledger.
> First deliverable: **`shop-import` → staging file**. Phone: **folder capture
> only** (no app, no offline lookup for now). Offline EAN lookup deferred.

---

## Original prompt (verbatim)

> I do have some routines described in ~/.claude/skills/process* - in addition to
> the routines described in those files, for the lidl shopping I also have to log
> in to lidl in the browser, and do `cd ~/regnskap ; python
> ~/shopping-analyzer/get_data.py update --browser chromium --country bg`. There
> are some problems with the current approach:
>
> * The Claude agent frequently does mistakes, sometimes the same mistakes - like
>   mixing up EAN codes, sending the wrong data to tingbok, forgetting things like
>   adding the ID-field to the markdown file, copying photos of the milk barcode
>   and expiry date to the inventory, guessing an expiry date when a perfectly good
>   photo of the expiry date exists, and other mistakes.
> * I'm often procrastinating the whole process because it's too much work. I even
>   type in full paths to the skill files and photo directory in the claude code
>   window, I should not have to do that.
> * There is some data loss in the process - I would like to have at least a
>   theoretical possibility to go back and find the answer to questions like "how
>   much did I actually spend on beer in August?" and "What was the purchase price
>   of all the food I actually consumed in August?"
>
> Please consider ways to streamline the process. Some thoughts:
>
> * Can more of the process be scripted?
> * Does it make sense to split up the process better? Smaller skills that should
>   be done in order, less need for context, perhaps saving the data found in the
>   previous step in a temporary or permanent file, also allowing me (when/if I
>   have time) to look into the files and correct mistakes on an early stage, also
>   allowing the process to be started immediately after the shopping (even if I'm
>   busy) without having to go through the whole process at once.
> * Does it make sense to save some of the raw data from the receipts i.e. in a
>   json-file under ~/regnskap ? Currently shopping from Decathlon and Lidl ends up
>   there, in the format provided by them, but in addition I'm photographing
>   receipts from other shops, and I would like to have one file with all the
>   relevant data from all shops, including EANs when applicable, and inventory-id
>   for things that was added to the inventory.
> * Perhaps some mobile app allowing me to start the process from the cellphone? I
>   don't want photos of barcodes and expiry dates to end up in my gallery and
>   backups - perhaps allowing the photos to be taken from an app would be better.
>   I want to be able to work locally while being offline. I'm currently using
>   syncthing and my syncthing-git plugin allowing git-controlled directories to be
>   synced, so that's probably the best way of transferring data from the phone to
>   the laptop. It should probably do lookups for EANs through tingbok. If the EAN
>   doesn't look up or if the EAN is not correct, it will be needed to take a photo
>   of the product and not only the barcode. I can ensure the ean-db.json from
>   tingbok is synced to the phone, allowing fallback lookups to be done from an
>   offline phone.
> * Perhaps there are better ways?
>
> (Maybe the whole idea of micro-managing the inventory is wrong. Maybe the idea
> of having the inventory in markdown-format is wrong. Maybe the idea of adding and
> keeping generated data in the markdown diary is wrong. But I do like the
> possibility to search, add and edit the inventory in my editor, etc).

---

## Diagnosis: why the mistakes happen

The recurring mistakes (EAN mixups, bad tingbok PUTs, missing `ID` field, copying
barcode/expiry photos, guessing an expiry that's already in a photo) are not
random. They share one root cause: **a single agent turn does OCR + fuzzy
matching + judgment + editing a 171 KB markdown file + an irreversible API PUT +
git, all at once, with no checkpoint and no validation gate.** Every step is an
LLM judgment call, and nothing *fails loudly* before the irreversible actions
(tingbok PUT, commit).

So the fix is structural, not "prompt better":

1. **Move deterministic work into scripts** (receipt parsing, barcode extraction,
   EAN lookup, exact-name matching, photo classification, inventory-line
   generation, schema validation).
2. **Insert a human-correctable staging file** between discovery and commit.
3. **Gate the irreversible steps behind validation** that fails loudly.

This also fixes procrastination (you can stop after any stage and resume later)
and data loss (the staging file feeds a permanent ledger).

## Honest pushback (recorded for posterity)

- **A custom mobile app is the wrong first move.** Most of the want is free: a
  FOSS camera app saving to a chosen folder + `.nomedia` (keeps it out of
  gallery/backups) + syncthing. The only thing worth *building* would be an
  offline EAN-lookup page — and that's blocked anyway: `tingbok.plann.no` has no
  `ean-db.json` dump endpoint yet (404). **Decision: folder capture only; offline
  lookup deferred.**
- **Markdown inventory is not the problem — keep it.** Greppable, diffable,
  editable. The mistakes come from the process around it, not the format.
- **The diary smell is real.** Generated, itemized data should live in a
  structured ledger; the diary keeps only the human-meaningful summary line.
- **"Is micromanaging wrong?"** The cost of micromanaging is the friction causing
  procrastination. Lower the friction (scripting), don't abandon the practice.
  The ledger captures spending even for items not added to `inventory.md`.

## The ledger: `~/regnskap/purchases.jsonl` (append-only)

Solves the data-loss problem and feeds everything else. One line per receipt
line-item:

```json
{"date":"2026-06-04","shop":"Lidl Varna","receipt_name":"ПРЯСНО МЛЯКО 3%",
 "ean":"4056489080510","name":"Pilos Fresh Milk 3% 1l","category":"food/dairy",
 "qty":1,"unit_price":1.43,"currency":"EUR","total":1.43,"inventory_id":null}
```

- Append-only → no data loss. Lidl/Decathlon importers append; photographed
  receipts get parsed into this schema and appended.
- `inventory_id` is the **join key**.
  - *"How much on beer in August?"* → filter the ledger.
  - *"Purchase price of food consumed in August?"* → `inventory.md` is
    git-backed, so a script can diff git history to find when an item with a
    given `inventory_id` was removed, join back to the ledger by `inventory_id`,
    and sum prices — **zero extra logging**. Caveat: removal-commit date ≈
    consumption date; bulk reorganizations blur it. Approximate but free.

> **Implemented** in `scripts/ledger.py` (stage 2): importers for raw Lidl,
> Decathlon (carries EAN), and reviewed staging files; `query` (category/date/
> shop) and `consumed` (git-history join — verified: 239 removed IDs detected
> across 215 revisions in ~1.3 s).
>
> **Append-or-enrich, not strict append-only** (per the owner's call): rows are
> matched on the stable receipt fields (`date, shop, receipt_name, qty,
> unit_price, total`); a re-import is a no-op, but importing the *reviewed*
> staging file fills the enrichable fields (`ean, name, category, inventory_id`)
> on the existing raw row in place — never duplicating, and nulls never overwrite
> an existing value. So raw imports give spend totals by date/shop immediately,
> and category + consumption queries resolve for each line once it's been reviewed
> through the staging flow.

## The pipeline: ordered, resumable stages

Each stage has a clear input/output file. Run stage 1 right after shopping; fix
mistakes in your editor whenever; finish later.

1. **`capture`** (phone, ~no code): camera app → synced folder.
2. **`shop-import`** (deterministic script, *no LLM judgment*) — **FIRST
   DELIVERABLE**: pull latest Lidl/Decathlon receipt (or LLM-OCR a photo receipt
   into the schema), run `extract_barcodes.py`, auto-match receipt lines ↔ EANs
   by **exact** tingbok `receipt_name`, look up each EAN, **classify each photo as
   label / barcode-only / expiry-only**, emit
   `staging/shopping-YYYY-MM-DD.yaml` with one row per line-item and a
   `needs_review` flag. *This is the correction checkpoint — fix EAN mixups here
   in the editor before anything irreversible.*
3. **`shop-review`** (small-context LLM): only `needs_review` rows (fuzzy matches,
   missing EAN/bb, ambiguous photos). Structured questions, writes back.
4. **`shop-commit`** (script + thin LLM): validate staging (every row complete;
   every photographed item has an `ID`; bb present or `:EST`; no dup IDs) → fail
   loudly → append to `purchases.jsonl` → script-insert inventory lines (ID never
   forgotten) → copy *only* label photos → PUT tingbok → run `check_quality.py`
   gate → `diary-update` → commit.

Stages 2 and 4 are mostly deterministic. The LLM only does vision (already
scripted) and the narrow review → collapses the error surface.

### Each named mistake → its guardrail

| Mistake | Guardrail |
|---|---|
| EAN mixups | exact-name matching in script; staging shows EAN+name+price together; low-confidence flagged |
| Bad tingbok PUT | PUT only in commit step, only reviewed rows, after validation, with a dry-run diff |
| Forgot ID field | script *generates* the inventory line incl. ID; validator rejects photographed items without ID |
| Copied barcode/expiry photos | classify photos automatically; only labels are copy-eligible |
| Guessed expiry when photo exists | staging row carries photo-derived bb; LLM forbidden to invent bb if set; else `:EST` required + flagged |

### Friction (path-typing)

The skills already hardcode photo dirs and receipt locations — you shouldn't be
typing paths. A single `/shop` skill should auto-detect newest receipt +
`find -mmin` photos + shop. A `make shop` / `make shop-commit` wrapper opens the
staging file in `$EDITOR` between stages.

## Photo storage (decided)

- Inventory photos move to a **separate directory** from the camera-capture
  folder (good hygiene regardless).
- **Delete photos from the laptop as soon as they are fully processed** (already
  rsynced to server via `sync-photos.sh`; not in git).
- Camera-app setup needed on **Redmi** and **Pixel/GrapheneOS**, both via
  **F-Droid** (e.g. Open Camera with a custom save dir + `.nomedia`). TODO.

## Drift / bugs found while reading (clean up)

- `match_lidl_receipt.py` and both skill docs still rely on `ean_cache.json`,
  which is deprecated in favour of tingbok. The matcher should query tingbok (or
  a synced dump).
- No `/api/ean-db.json` dump endpoint on tingbok (404) — needed before any
  offline phone lookup.
- Typo in `process-lidl-shopping.md` line 25: "breif" → "brief".

## Build order

1. `shop-import` → `staging/shopping-YYYY-MM-DD.yaml` (**first**).
2. `purchases.jsonl` schema + Lidl/Decathlon importers + git-history
   consumption-cost query.
3. `shop-review` + `shop-commit` stages + validation gate.
4. `/shop` wrapper skill + Makefile targets; fix the drift/bugs above.
5. Phone folder-capture setup (Redmi + Pixel via F-Droid).
