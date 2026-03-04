# Category/Vocabulary TODO

Known issues and improvement areas for the SKOS vocabulary and category hierarchy system.  We focus first on getting a good, working category system for ~/solveig-inventory, afterwards ~/furuset-inventory should be dealt with.

## Multiple-sources (important!)

Some of the logic has sort of been moved from inventory-md to a separate tingbok project - the source for tingbok is under ~/tingbok

The tingbok vocabulary.json should contain the URL to all applicable data sources.  Currently there is an `uri` field but it's only used in some few of the categories, and it only allows a single URL, not a list of URLs.  It needs to be changed a bit so the URL for every matching source can be stored in the vocabulary.  off probably doesn't have the uri-concept, but we can make mock URIs ... like `off://category:{categoryname}`.  If the list is empty, then tingbok should autogenerate a list, if the list contains items i.e. for bedding, with agrovoc missing, then it should assume that there is no need to look up bedding in agrovoc.

The git-controlled tingbok `vocabulary.json` should not contain any redundant altlabels etc.  If translations exists upstream, then that's sufficient.  (but translation information may exist in local caches and should be delivered to the end-clients).

Currently it seems that lots of translations are missing in the category system.  The logic should be to fetch *all* translations from *all* sources.  The fallback logic (use nn or da or no if no nb is found, etc) should only apply if NONE of the sources have nb language.  (exceptions may apply - like no is sort of the same as nb and may be considered as a primary altlabel source and not just fallback).

Categories should be displayed not only with one source in the UI, but with the full list of sources (and the info box should either contain information from all the sources, or it should be possible to choose source and then see the info)

The very most of the categories should be accessible by several paths, both from the virtual `_root`-node and through the "Category by Source" node. (I think this is sort of working already)

Sometimes a category is completely wrong (like the animal seal vs a rubber seal).  I noticed the wikidata has a https://www.wikidata.org/wiki/Property:P1889 "different from", perhaps something like this may be used to distinguish rubber seals from live seals and human-bed-related items from animal-pee-absorbing matters?

## ~~Wikidata source is not visible under "Category by Source"~~

**Status**: Resolved (2026-02-09)

Wikidata was opt-in (not in default `enabled_sources`) to avoid doubling SPARQL
query load. Changed to enabled by default — the extra queries are worth the better
ontological hierarchy and multilingual coverage. Vocabulary regeneration needed to
populate `category_by_source/wikidata/` entries.

## ~~More/better information about a category~~

**Status**: Resolved (2026-02-09)

The inline info panel (compact, truncated) now has an "ℹ️" button that opens a
full-detail modal dialog showing: all parents, ALL children (sorted, no limit),
full description (no truncation), all source badges with clickable URIs, alt labels,
and language-aware Wikipedia link. Also fixed `build_category_tree()` not copying
`source_uris`, so they now appear in `vocabulary.json`.

## ~~Unwanted external root categories~~

**Status**: Fixed (2026-02-06)
**Impact**: External sources (DBpedia, AGROVOC) leaked unwanted roots like
`environmental_design`, `goods_(economics)`, `industrial_equipment`, `subjects`

A virtual root concept (`_root`) in `vocabulary.yaml` now explicitly defines which
concepts are top-level roots and their display order. External rootless concepts are
excluded (whitelist behavior). Falls back to the previous inferred-root behavior when
`_root` is absent.

## ~~Consider merging some root categories~~

**Status**: Resolved (2026-02-09)

Merged 18 root categories down to 10 meaningful roots:
- **recreation** (new) absorbs outdoor, sports, transport
- **hardware** absorbs construction, consumables
- **household** absorbs office, books, documents
- **medical** renamed to "Health & Safety", absorbs safety-equipment
- **hobby** deleted (redundant with transport)

Remaining roots: food, tools, electronics, household, clothing, hardware,
recreation, medical, games, misc (+ category_by_source).

## ~~Too many "local" categories~~

**Status**: Fixed (2026-02-06)
**Impact**: Local concepts with `broader` produced duplicate flat and path-prefixed
concepts (e.g., both `ac-cable` and `electronics/ac-cable`), resulting in 138
orphaned flat concepts

When a local vocabulary concept like `ac-cable` has `broader: ['electronics']`, the
builder now transfers metadata from the flat concept to the path-prefixed concept and
removes the flat duplicate. The path-prefixed form is kept because the UI uses
`category.startsWith(selected + '/')` for filtering.

## ~~DBpedia Concepts Have No Translations (200 concepts)~~

**Status**: Fixed (2026-02-06)
**Impact**: 200 DBpedia-sourced concepts have zero translations

DBpedia URIs are now persisted to `concept.uri` during hierarchy building (Path B),
and a new DBpedia translation phase fetches labels via `client.get_batch_labels()`
using the existing `_get_dbpedia_labels_batch` in `skos.py`.

**Changes**:
- Store DBpedia URI on leaf concept when paths are found (`vocabulary.py`)
- Add DBpedia translation phase after AGROVOC phase (`vocabulary.py`)
- Includes sanity check (same pattern as OFF/AGROVOC)

## ~~Orphaned OFF/AGROVOC Intermediate Concepts~~

**Status**: Resolved (2026-02-09)
**Original impact**: 173 junk hierarchy nodes clutter the vocabulary

This was observed during earlier iterations of the vocabulary builder. The concern was
that AGROVOC paths like `food/non_food_products/clothing/workwear` would create orphan
intermediate nodes when `local_broader_path` later overrides them.

Code analysis confirms this doesn't happen: when `local_broader_path` is set,
`_add_paths_to_concepts` is only called with the local path (e.g.,
`clothing/workwear`). The AGROVOC paths in `all_paths` are only used for URI
extraction, never for concept creation. Raw source paths are correctly preserved
under `category_by_source/agrovoc/`.

## ~~Low Translation Coverage (18% overall)~~

**Status**: Largely addressed (2026-02-09)
**Impact**: 663 non-food local concepts have no translations

Most local concepts lack URIs, so the translation phase can't look them up.
Only concepts with AGROVOC/OFF/DBpedia URIs (or matches in `all_uri_maps`) get
translations.

**Improvements**:
- Promoted Wikidata to a full, independent category source (not just translation).
  Wikidata now has its own concept lookup, hierarchy building via P31/P279, and
  `category_by_source/wikidata/` entries — following the same pattern as DBpedia.
  Wikidata has cleaner ontological hierarchy than DBpedia (structured P279 subclass
  chains vs. messy Wikipedia categories) and excellent multilingual label coverage.
  Now enabled by default in `enabled_sources`.
- Added a final language fallback pass that applies `DEFAULT_LANGUAGE_FALLBACKS`
  to every concept's labels after all translation phases complete. This fills
  gaps like "nb" from "sv" (or "da", "nn") when no source has Norwegian.
- **Auto-resolve URIs** via `_resolve_missing_uris()`: after the hierarchy loop
  and before translation phases, concepts without URIs are batch-queried against
  DBpedia and Wikidata by prefLabel. This enables translations for previously
  unreachable local vocab concepts.

**Remaining**: Manually add URIs to `vocabulary.yaml` for concepts where
auto-resolve returns a wrong match (sanity check rejects mismatched prefLabels).

## ~~OFF Path-to-Translation Mismatch~~

**Status**: Fixed (2026-02-08)
**Impact**: Intermediate path concepts could get wrong translations from OFF

OFF has ~85 root categories (`plant-based foods and beverages`, `meats`, `seafood`,
`dairies`, etc.). `OFF_ROOT_MAPPING` in `off.py` correctly maps these to `"food"` for
path construction. The AGROVOC `_build_paths_to_root` now skips mapped root URIs
(same pattern as `off.py`), and the translation phases iterate candidate URIs from both
`all_uri_maps` and `concept.uri`, filtering by source type. The DBpedia phase no longer
skips concepts that already have partial translations, allowing it to fill gaps.

## ~~`food` Concept Needs DBpedia URI and Manual Labels~~

**Status**: Fixed (2026-02-06)
**Impact**: `food` gets wrong or overly-specific translations

The `food` concept in `vocabulary.yaml` now has `uri: "http://dbpedia.org/resource/Food"`
and explicit labels in 12 languages (en, nb, de, fr, es, it, nl, sv, pl, ru, uk, fi, bg).

## ~~Look into warnings when generating the solveig-inventory vocabulary~~

**Status**: Resolved (2026-02-09)

Three fixes eliminated all 14 AGROVOC mismatch warnings:
- Skip AGROVOC lookup entirely when local concept already has a non-AGROVOC URI
  (covers 9 warnings: bedding, disc, gps, peanuts, snacks, tool, tools, tubing, washer)
- Accept singular/plural variants in mismatch check (dairy/dairies)
- Added DBpedia URIs to 4 concepts (mushrooms, lumber, marine_propulsion, medicine)

## ~~Source Hierarchy Preservation (category_by_source)~~

**Status**: Implemented (2026-02-06)
**Impact**: OFF/AGROVOC/DBpedia original hierarchies are now preserved

When paths are mapped to synthetic roots (e.g., OFF's "Plant-based foods and beverages"
mapped to "food"), the original pre-mapping paths are now stored under
`category_by_source/<source>/<raw_path>`.

**Examples**:
- `category_by_source/off/plant_based_foods_and_beverages/vegetables/potatoes`
- `category_by_source/agrovoc/products/plant_products/potatoes`
- `category_by_source/dbpedia/american_inventions/widget`

**Changes**:
- `off.py`: `build_paths_to_root` now returns raw paths (3-tuple)
- `vocabulary.py`: `_build_paths_to_root` and `build_skos_hierarchy_paths` return raw paths
- `vocabulary.py`: Raw paths stored under `category_by_source/` during vocabulary building

## ~~Package Vocabulary Has No Distinct Source/Namespace~~

**Status**: Resolved (2026-02-09)
**Impact**: Cannot distinguish package-provided concepts from user-defined local concepts

The package vocabulary (`src/inventory_md/data/vocabulary.yaml`) loads with
`source="local"`, same as user-provided `local-vocabulary.yaml` files. There's no way
to tell whether a concept like `clothing` was defined by the package or by the user.

This matters for:
- Conflict resolution (user definitions should override package defaults)
- Debugging (which file did this concept come from?)
- Future tooling (e.g., "show me only my custom vocabulary")

**Resolution**: Added `default_source` parameter to `load_local_vocabulary()`.
`load_global_vocabulary()` detects the package data directory and passes
`default_source="package"`. Source checks in the vocabulary builder now treat
`"package"` like `"local"` for hierarchy protection. Removed several places that
force-reset `_target.source` to `"local"` — the original source is now preserved
through enrichment and dedup passes.


## Still some categories missing translations

For categories that exist in the local vocabulary but have no matches in the other category sources (like root node "Health & Safety"), there must be translations locally in the package vocabulary.

~~household/books seems to be missing Norwegian translation and have a Danish translation.~~
**Fixed**: Multi-source tracking (`source_uris`) now finds supplementary DBpedia/Wikidata
URIs for concepts that only matched via OFF/AGROVOC, so translation phases can query all
available sources. Books now gets Norwegian from Wikidata even when originally matched via
DBpedia.

## ~~Weird progress status in `inventory-md parse`~~

**Status**: Resolved (2026-02-09)

The AGROVOC Oxigraph loading (~30s) happened silently during the first lookup,
making it look like `[1/475] Alcoholic beverages` was taking forever. After the
expansion loop finished at `[472/475]`, multiple silent phases ran (URI resolution,
source_uris population, additional URI lookup, and 4 translation phases) with no
user feedback.

**Resolution**: Added a `progress` callback parameter to
`build_vocabulary_with_skos_hierarchy()`. The library no longer calls `print()`
directly (fixing ruff T201 violations). Instead, the CLI passes a callback that
prints progress messages. Phases reported: `init` (Oxigraph loading), `expand`
(category loop), `warning` (AGROVOC mismatches), `resolve` (URI resolution),
`translate` (per-source translation + language fallbacks). The Oxigraph store is
now eagerly loaded with a visible status message before the expansion loop starts.
