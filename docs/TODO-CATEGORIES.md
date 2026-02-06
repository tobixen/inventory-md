# Category/Vocabulary TODO

Known issues and improvement areas for the SKOS vocabulary and category hierarchy system.  We focus first on getting a good, working category system for ~/solveig-inventory, afterwards ~/furuset-inventory should be dealt with.

## ~~Unwanted external root categories~~

**Status**: Fixed (2026-02-06)
**Impact**: External sources (DBpedia, AGROVOC) leaked unwanted roots like
`environmental_design`, `goods_(economics)`, `industrial_equipment`, `subjects`

A virtual root concept (`_root`) in `vocabulary.yaml` now explicitly defines which
concepts are top-level roots and their display order. External rootless concepts are
excluded (whitelist behavior). Falls back to the previous inferred-root behavior when
`_root` is absent.

## Consider merging some root categories

Hobby, transport, sports and outdoors could be one root. Construction and most of
Consumables should go under Hardware. Documents, Office supplies and Domestic stuff
could go into one root. The `_root.narrower` list controls which concepts appear as
roots, so merging just requires adding `broader` to demoted roots and updating
`_root.narrower`.

## ~~Too many "local" categories~~

**Status**: Fixed (2026-02-06)
**Impact**: Local concepts with `broader` produced duplicate flat and path-prefixed
concepts (e.g., both `ac-cable` and `electronics/ac-cable`), resulting in 138
orphaned flat concepts

When a local vocabulary concept like `ac-cable` has `broader: ['electronics']`, the
builder now transfers metadata from the flat concept to the path-prefixed concept and
removes the flat duplicate. The path-prefixed form is kept because the UI uses
`category.startsWith(selected + '/')` for filtering.

## DBpedia Concepts Have No Translations (200 concepts)

**Status**: Fixed (2026-02-06)
**Impact**: 200 DBpedia-sourced concepts have zero translations

DBpedia URIs are now persisted to `concept.uri` during hierarchy building (Path B),
and a new DBpedia translation phase fetches labels via `client.get_batch_labels()`
using the existing `_get_dbpedia_labels_batch` in `skos.py`.

**Changes**:
- Store DBpedia URI on leaf concept when paths are found (`vocabulary.py`)
- Add DBpedia translation phase after AGROVOC phase (`vocabulary.py`)
- Includes sanity check (same pattern as OFF/AGROVOC)

## ~~Orphaned OFF/AGROVOC Intermediate Concepts~~ (likely stale)

**Status**: Probably resolved / stale
**Original impact**: 173 junk hierarchy nodes clutter the vocabulary

This was observed during earlier iterations of the vocabulary builder. The concern was
that AGROVOC paths like `food/non_food_products/clothing/workwear` would create orphan
intermediate nodes when `local_broader_path` later overrides them.

However, tracing the current code flow shows this doesn't happen: when
`local_broader_path` is set, `_add_paths_to_concepts` is only called with the local
path (e.g., `clothing/workwear`). The AGROVOC paths in `all_paths` are only used for
URI extraction, never for concept creation.

The `food/non_food_products` path was itself a root mapping bug: AGROVOC's hierarchy is
`products/non_food_products/clothing`, and `AGROVOC_ROOT_MAPPING` maps `"products"` →
`"food"`. With `category_by_source`, the raw AGROVOC path is correctly preserved as
`category_by_source/agrovoc/products/non_food_products/clothing/workwear`.

**Action**: Verify with a real run whether any orphan concepts still exist. If so,
investigate which code path creates them. If not, close this issue.

## Low Translation Coverage (18% overall)

**Status**: Open
**Impact**: 663 non-food local concepts have no translations

Most local concepts lack URIs, so the translation phase can't look them up.
Only concepts with AGROVOC/OFF/DBpedia URIs (or matches in `all_uri_maps`) get
translations.

**Fix approach**:
- Add DBpedia URIs to more local vocabulary entries (like was done for `tools`,
  `bedding`, `peanuts`, etc.)
- Consider batch-querying DBpedia by prefLabel for concepts without URIs
- Fix DBpedia translation phase (issue #1) to make added URIs actually work

## OFF Path-to-Translation Mismatch (fixed for labels, URI issue remains)

**Status**: Partially fixed (2026-02-06)
**Impact**: Intermediate path concepts can get wrong translations from OFF

OFF has ~85 root categories (`plant-based foods and beverages`, `meats`, `seafood`,
`dairies`, etc.). `OFF_ROOT_MAPPING` in `off.py` correctly maps these to `"food"` for
path construction. However, the OFF node ID stored in `off_node_ids["food"]` still
points to the specific root node (e.g., `en:plant-based-foods-and-beverages`), giving
wrong translation labels.

The sanity check (comparing English label to prefLabel) now catches obvious mismatches,
but the root cause is that OFF's translation for `"food"` comes from whichever specific
root category was processed first.

**Fix approach**:
- Don't store OFF node IDs for mapped root concepts (they're synthetic "food" nodes,
  not real OFF concepts)
- Use DBpedia URI for `food` translations instead (see below)

## ~~`food` Concept Needs DBpedia URI and Manual Labels~~

**Status**: Fixed (2026-02-06)
**Impact**: `food` gets wrong or overly-specific translations

The `food` concept in `vocabulary.yaml` now has `uri: "http://dbpedia.org/resource/Food"`
and explicit labels in 12 languages (en, nb, de, fr, es, it, nl, sv, pl, ru, uk, fi, bg).

## Source Hierarchy Preservation (category_by_source)

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
