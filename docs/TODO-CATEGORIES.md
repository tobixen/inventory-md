# Category/Vocabulary TODO

Known issues and improvement areas for the SKOS vocabulary and category hierarchy system.  We focus first on getting a good, working category system for ~/solveig-inventory, afterwards ~/furuset-inventory should be dealt with.

## Wikidata source is not visible under "Category by Source"

Recently WIkidata was added as an independent category source - but in solveig-inventory it's still not visible under the "category by source" root.

## More/better information about a category

Each category by now have a truncated description, one parent, multiple children (and the list gets truncated if there are too many of them), and one source.  I would like to be able to access an info box for a category showing all parents, all children, full description, and a list of sources.

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

## Low Translation Coverage (18% overall)

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
  Opt-in via `enabled_sources=["off", "agrovoc", "dbpedia", "wikidata"]`.
- Added a final language fallback pass that applies `DEFAULT_LANGUAGE_FALLBACKS`
  to every concept's labels after all translation phases complete. This fills
  gaps like "nb" from "sv" (or "da", "nn") when no source has Norwegian.
- **Auto-resolve URIs** via `_resolve_missing_uris()`: after the hierarchy loop
  and before translation phases, concepts without URIs are batch-queried against
  DBpedia and Wikidata by prefLabel. This enables translations for previously
  unreachable local vocab concepts.

**Remaining approach**:
- Manually add URIs to `vocabulary.yaml` for concepts where auto-resolve
  returns a wrong match (sanity check rejects mismatched prefLabels)
- Enable Wikidata in `enabled_sources` for better coverage of non-food concepts

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

## Package Vocabulary Has No Distinct Source/Namespace

**Status**: Open
**Impact**: Cannot distinguish package-provided concepts from user-defined local concepts

The package vocabulary (`src/inventory_md/data/vocabulary.yaml`) loads with
`source="local"`, same as user-provided `local-vocabulary.yaml` files. There's no way
to tell whether a concept like `clothing` was defined by the package or by the user.

This matters for:
- Conflict resolution (user definitions should override package defaults)
- Debugging (which file did this concept come from?)
- Future tooling (e.g., "show me only my custom vocabulary")

**Fix approach**:
- Introduce a `source="package"` (or `"inventory-md"`) for concepts loaded from
  the package data directory
- User local vocabulary keeps `source="local"` and takes priority over package
- Alternatively, use a namespace prefix like `pkg:` for concept IDs, though this
  would be a bigger change
