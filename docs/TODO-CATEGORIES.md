# Category/Vocabulary TODO

Known issues and improvement areas for the SKOS vocabulary and category hierarchy system.

## Quick introduction

There are four components involved here:

* ~/tingbok - supposed to be the authorative source of categorization information, running as a service from tingbok.plann.no, fetching information from various sources.  Currently the user needs to deploy code changes.
* ~/inventory-md - the "inventory system", basically a CLI.
* ~/solveig-inventory - an inventory.  Data is in inventory.md, when running `inventory-md parse --auto` it will extract the data into inventory.json and build vocabulary.json.  Most category-problems observed by the user can be found by digging into ~/solveig-inventory/vocabulary.json
* ~/furuset-inventory - another inventory instance.

We're trying to keep the same version numbers on tingbok and plann.  The project is still in a 0.x development phase, and I'm probably the only user, so we don't need to care about backward compatibility if it makes sense to change APIs and making breaking changes,

## Core ideas

* The category system is hierarchical.  food/spices/cumin could be a node.
* The tingbok has a vocabulary.yaml describing the root nodes and parts of the "inventory system" category tree.  This file should be slim, it shouldn't contain information available from other sources.  It's also not complete, it's just a starting point.
* Every category should have at least one path, but may have several paths.  food/vegetables/potato snd food/staples/potato is the same category, but with two paths.
* Tingbok should query multiple sources to find the relevant paths, translations, alternative lables and a good description of every category.

## Split/combine source concepts?

Some sources lump together things (spices + herbs, underwear and socks), while others keep it separated.  Sometimes such a combination is just for the category tree (in GPT, "Underwear and socks" have subcategories socks and underwear).  Sometimes we want the Tingbok vocabulary category to combine multiple source URIs from the same source.  Specifically, I want "long johns" (Q2472769) and "longs" (Q56303142 in wikidata) to be combined into one category in Tingbok.  The other cases can probably be handled in the vocabulary as it is - if two different Tingbok vocabulary categories references the same source URI, we probably want to create a parent category referencing the source.  If we want to create an "underwear and socks" node in the hierarchy, we can define that in vocabulary, exclude other sources than GPT, and let socks and underwear be children of it.

## ~~Clothing~~ **Fixed**

~~Clothing is listed with only an "inventory" source in solveig, despite having children.  It also lacks translations.~~

**Root cause**: `enrich_categories_via_lookup` creates inventory-sourced stub nodes for every path segment of an enriched concept (e.g. a `clothing` stub when enriching `clothing/outdoor_clothing`).  These stubs were then merged back into the main vocab via `vocab.update(resolved)`, silently overwriting the tingbok-sourced `clothing` concept.

**Fixed**: after `vocab.update(resolved)` in `parse_command`, global-vocab (tingbok) concepts that were overwritten by inventory-sourced stubs are restored.  Also added `nb: "Klær"` label to the vocabulary entry.

**Note**: the fix only takes effect after re-running `inventory-md parse --auto` against a tingbok server that returns 200 for `/api/vocabulary` (the server must have completed its background label-fetch before the parse runs).

## Nuts

Two separate "nut" problems:

1. **Food nuts hierarchy was flat**: `peanuts` and `cashews` had `food/snacks` as their broader instead of being children of `nuts`.  The `nuts` concept had ID `nuts` instead of `food/nuts`, causing an orphan `food/nuts` stub to appear in vocabulary.json whenever coconut/coconut-milk enrichment returned a path like `food/nuts/coconuts`.

   **Fixed**: renamed concept `nuts` → `food/nuts`, moved peanuts/cashews/coconut under it, added `coconut` to vocabulary, updated `food/snacks.narrower`.

2. **Hardware nuts miscategorised**: inventory.md uses `category:nut` (singular) for hex nuts, wing nuts, lock nuts — these were showing up as an unmatched `nut` stub with no parents.

   **Fixed**: added `hardware/nut` concept under `fasteners`, and added `"nut"/"nuts"` to fasteners' altLabel so the bare `category:nut` label enriches to the right place.

## Furuset

Under ~/furusetalle9-inventory/inventory.md I have a Norwegian inventory.  It has categories like "klær/vinter", "jul/belysning", etc - it could be redone into "klær/vinterklær" (I already changed that one), "jul/julebelysning", etc, but I like it as it was.  Perhaps it should be possible to enter aliases for categories in the vocabulary.yaml file?

## ~~inventory-md: caching~~ **Fixed**

~~The inventory-md should cache ean and category lookups from tingbok, with a one-week TTL.  The vocabulary should not be cached.~~
**Done**: client-side cache under `~/.cache/inventory-md/tingbok/` with 7-day TTL for both EAN lookups and `/api/lookup` results.

## ~~inventory-md: category-by-source missing~~ **Fixed**

~~It disappeared after the latest rounds of update~~
**Fixed**: `build_category_tree` now dynamically generates `category_by_source` and `category_by_source/{source}` virtual nodes from each concept's `source_uris` dict — no hardcoded source names.  `buildCategoryCounts()` in search.html aggregates item counts upward so source nodes appear in the category browser.

## User interface

~~When clicking on dbpedia, wikidata or agrovoc one gets to the source URI, and that's fine.  However, off and gpt does not have any URL.  For GPT I'd like to show the full category line in a mouseover.  For OFF, some OFF data should be shown in a mouseover.~~
**Fixed**: OFF and GPT badges now show a `title` tooltip — "OpenFoodFacts: potatoes" or "Google Product Taxonomy #455".  GPT also gets its own colour (blue).  `gpt:` and `off:` URIs no longer produce broken hyperlinks.

~~When clicking on the information sign and an information box pops up and one chooses one of the broader or narrower from the information box, the new category should be displayed in the information box.  Today the information box disappears.~~
**Fixed**: clicking broader/narrower in the detail modal now calls `navigateCategoryInModal()` which updates both the modal content and the selected category in the tree, keeping the modal open.

## Tingbok hard-coded vocabulary vs other concepts

* ~~Document in details the workflow when some category present in `inventory.md` is looked up.~~
  **Done**: see `docs/category-lookup-workflow.md`.

* ~~Consider a new URL like `https://tingbok.plann.no/api/lookup/{concept}` that returns
  `VocabularyConcept` format regardless of whether the concept is in `vocabulary.yaml`.~~
  **Implemented**: `GET /api/lookup/{label}` in tingbok.  Checks vocabulary by ID and
  prefLabel/altLabel first; if not found, queries **all** SKOS sources (AGROVOC, DBpedia,
  Wikidata) in parallel and merges labels, altLabels, descriptions (longest wins) and
  source URIs.  Returns `VocabularyConcept` with hierarchy-derived `id`.
  See `docs/category-lookup-workflow.md` for the full design rationale.

URLs like `https://tingbok.plann.no/api/vocabulary/food` remain the canonical URL for concepts
present in `vocabulary.yaml`.  `GET /api/lookup/{label}` extends this to all concepts.

**Remaining**:
* The caching for `/api/lookup` results is currently done by the underlying SKOS service
  (per concept/label files in `~/.cache/tingbok/skos/`).  Separating lookup results into
  their own cache directory for easier inspection was requested but not yet done.
* Translation warnings ("bedding" = animal litter vs. household bedding) should be
  generated at lookup time and written to a separate YAML/JSON file on the server.

## EAN-support from the parse script

* ~~Whenever an inventory line with EAN:xxx is discovered during parsing, tingbok should be queried about the EAN, and the category should be set or verified depending on the feedback from tingbok.~~
  **Implemented**: `parse --auto` now queries `GET /api/ean/{ean}` for each item with an `EAN:` tag.
  Tingbok's EAN service dispatches by code type: ISBNs (978/979 prefix) → Open Library → nb.no;
  other EAN/UPC → Open Food Facts → UPCitemdb.  Results are cached 60 days.
  The most specific English category is fed into `resolve_categories_via_tingbok` so
  EAN-derived categories appear in the vocabulary hierarchy.  Product name and inferred
  category are printed during the parse run.
  **Remaining**: auto-write `category:xxx` back into the inventory markdown file.

## EAN update support

Currently price and other information on receipts is correlated with photos of bar-codes, this is at the moment a Claude-based effort (see inventory-md/claude-skills).  Now that the database should stay at Tingbok, we need an interface for updating Tingbok.  The skill should be updated to reflect this (is it "cheapest" to do those updates via REST or MCP?).

## Multiple-sources (important!)

There are still some remaining work here and quite some regressions after the latest rounds of work on tingbok and inventory-md.  Possibly the tingbok API needs to be changed a bit to reflect that tingbok is now supposed to do the full work of looking up categories?

I think that instead of fetching https://tingbok.plann.no/api/vocabulary it should fetch categories by a canonical "tingbok URL", starting with the virtual _root category.

I think there is no such thing as a canonical "tingbok URL" now.  This needs to be fixed.

Some of the categories in the current tingbok vocabulary.yaml has an uri field with a value, this infomation may safely be overwritten by the canonical tingbok URL

The source URIs should probably always be given with https rather than http, since https is the standard nowadays.

~~Recently a prune-vocabulary command was introduced to tingbok to remove redundant labels from vocabulary.yaml, but it does not remove `altLabel` - this should be fixed.~~
**Fixed**: `prune-vocabulary` now also removes redundant `altLabel` entries (individual values removed selectively per language).

Some notes I made while investigating the solveig inventory:

* https://tingbok.plann.no/api/skos/lookup?label=clothing should probably not default to only showing agrovoc it should probably do a lookup in all sources. (this may be moot, do we need the lookup api call at all?)
* ~~(in solveig-inventory / tingbok vocabulary) "clothing" is missing quite some altlabels, including "costume".~~
  **Fixed**: `GET /api/vocabulary` now merges `altLabel` from DBpedia (skos:altLabel), Wikidata (aliases), AGROVOC (altLabel), and OFF (synonyms).
* ~~(in solveig-inventory) the cumin category was previously (v0.7.0) recognized as a subcategory of spice - now it's not.~~
  **Fixed**: `parse --auto` now calls `resolve_categories_via_tingbok()` for orphaned labels, querying `/api/skos/hierarchy` across AGROVOC/DBpedia/Wikidata.
* (in solveig-inventory) buillion is a subcategory of spice - needs verification after the above fix.
* "Categories by source" in the inventory UI — should be dynamically generated from tingbok data rather than hardcoded in inventory-md.

## ~~Tingbok cache gracetime~~ **Fixed**

**Done**: TTL check removed from `_load_from_cache` — stale data is always served immediately (no cold misses).  Freshness maintained by a background `cache_refresh_loop` task inside the FastAPI process:
- Finds the oldest cache entry (`_find_oldest_cache_entry`)
- Sleeps `max(0, (max_age - age) / divisor)` seconds
- Refreshes via `_refresh_entry`, preserving `_last_accessed` so the access clock is not reset
- Loops forever

Configurable: `TINGBOK_CACHE_MAX_AGE_DAYS` (default 60), `TINGBOK_CACHE_REFRESH_DIVISOR` (default 100).
`tingbok prune-cache` deletes entries not accessed within the retention window (`--max-age DAYS`, default 60).

## Google Product Taxonomy (GPT) as a future source

~~GPT is fully implemented in tingbok~~: `gpt.py` service, `gpt:{id}` URI scheme,
`download-taxonomy --gpt` CLI, wired into `populate-uris` and startup label fetching.
54 `gpt:` URIs already in vocabulary.yaml.

**Remaining:**

0) How does the GPT compare to the tingbok vocabulary?  Are there tingbok concepts
   without any `gpt:` URI that should have one?  Perhaps remap some categories.
   (This requires manual review against the GPT hierarchy.)

1) "Categories by source" in the inventory UI is missing GPT — but this is part of
   the broader "categories by source should be dynamically generated from tingbok"
   work, covered under "Remove redundant logic from inventory-md" below.

## Move "memory" information into docs

There is a file ~/.claude/projects/-home-tobias-inventory-system/memory - useful information should exists in the docs (tingbok and inventory-md) rather than in the memory file.  It's needed to look through and check if the old file maps well with the current realities.  The list below contains my comments after looking through the file.  My opinions below may involve changes in the code, both tingbok and inventory-md - small changes can be done immediately, big changes should be added to this TODO-CATEGORIES-document.

* "source priority" - I think we should treat the sources more or less equally, rather than having them as a prioritized list.
* There is no "package vocabulary" anymore, it's the Tingbok vocabulary
* There is nothing special about Wikidata - it's just one out of several sources
* "Plant-based foods and beverages" is not the same as "food", it is a sub-category of food.
* Probably all source-specific logic (`off.py`, SPARQL-logic, etc) should be removed from inventory-md and kept only in tingbok
* Lots of work has been done on multi-source tracking in the tingbok project, so the entire section is probably outdated.
* Tingbok should have some built-in rate-limiting handling.  Niquests comes with some built-in logic for this ... check Retry in niquests.packages.urllib3.util

## ~~Remove redundant logic from inventory-md~~ **Done** (2026-03-06)

(but quite some regressions are observed after this was done)

`skos.py`, `off.py`, and ~2300 lines of hierarchy/translation logic removed from
inventory-md.  The `inventory-md skos` CLI command and `--skos`/`--hierarchy` parse
flags are gone.  Remaining source references in `vocabulary.py` are limited to
`_uri_to_source()` (URI-to-source-name mapping) and the language fallback logic
(pure functions, no network calls).

The fallback to the old direct-source approach is replaced with:

## Create a new optional tingbok fallback

tingbok could be an optional dependency of inventory-md.  If the tingbok library exists and tingbok.plann.no doesn't respond, use the tingbok libraries directly.

We then need to rethink what dependencies should be optional and not, like, mcp is clearly not needed for this purpose

## Still some categories missing translations

This is probably not much relevant more, needs manual verification.

For categories that exist in the local vocabulary but have no matches in the other category sources (like root node "Health & Safety"), there must be translations locally in the package vocabulary.

~~household/books seems to be missing Norwegian translation and have a Danish translation.~~
**Fixed**: Multi-source tracking (`source_uris`) now finds supplementary DBpedia/Wikidata
URIs for concepts that only matched via OFF/AGROVOC, so translation phases can query all
available sources. Books now gets Norwegian from Wikidata even when originally matched via
DBpedia.
