# Category/Vocabulary TODO

Known issues and improvement areas for the SKOS vocabulary and category hierarchy system.

## 1. DBpedia Concepts Have No Translations (200 concepts)

**Status**: Fixed (2026-02-06)
**Impact**: 200 DBpedia-sourced concepts have zero translations

DBpedia URIs are now persisted to `concept.uri` during hierarchy building (Path B),
and a new DBpedia translation phase fetches labels via `client.get_batch_labels()`
using the existing `_get_dbpedia_labels_batch` in `skos.py`.

**Changes**:
- Store DBpedia URI on leaf concept when paths are found (`vocabulary.py`)
- Add DBpedia translation phase after AGROVOC phase (`vocabulary.py`)
- Includes sanity check (same pattern as OFF/AGROVOC)

## 2. AGROVOC Root Mapping Creates Nonsensical Paths / Orphaned Concepts

**Status**: Open
**Impact**: Junk hierarchy nodes clutter the vocabulary (173 orphans)

The `AGROVOC_ROOT_MAPPING` maps `"products" → "food"`, but AGROVOC's "products"
root has both food and non-food children. This produces nonsensical paths like
`food/non_food_products/clothing/workwear` — "non-food" placed under "food".

These incorrect paths get overridden by local vocabulary (which correctly defines
`clothing` as a root), but the intermediate nodes remain as orphans.

Examples:
- `food/non_food_products/clothing/workwear` (AGROVOC: products/non_food_products/...)
- `activities/monitoring/process_control/remote_control` (AGROVOC)

**Root cause**: `AGROVOC_ROOT_MAPPING` blindly maps all descendants of "products" to
"food", but "products" has non-food children like "non_food_products", "fibres",
"rubber and gums", etc.

**Fix approach**:
- Don't map "products" → "food" when the path contains "non_food_products" or other
  non-food branches; OR add those as separate roots in `AGROVOC_ROOT_MAPPING`
- Then prune any remaining orphan concepts not reachable from `category_mappings`

## 3. Low Translation Coverage (18% overall)

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

## 4. OFF Path-to-Translation Mismatch (fixed for labels, URI issue remains)

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

## 5. `food` Concept Needs DBpedia URI and Manual Labels

**Status**: Open (quick win)
**Impact**: `food` gets wrong or overly-specific translations

Neither AGROVOC nor OFF have a single "food" top-level concept. AGROVOC has
`products`/`plant products`/`animal products`, OFF has 85 specific root categories.
Both get mapped to synthetic `"food"` path roots.

DBpedia has `http://dbpedia.org/resource/Food` with labels in 28+ languages including:
- en: Food, nb: Mat, de: Lebensmittel, fr: Nourriture, sv: Mat, es: Alimento, etc.

**Fix**: Add `uri: "http://dbpedia.org/resource/Food"` to `food` in `vocabulary.yaml`
and ensure the DBpedia translation phase works (issue #1).

As a quick interim fix, add explicit labels to the packaged vocabulary.

## 6. Source Hierarchy Preservation (category_by_source)

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

## 7. Package Vocabulary Has No Distinct Source/Namespace

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
