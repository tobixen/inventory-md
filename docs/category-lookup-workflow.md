# Category Lookup Workflow

This document describes how category labels in `inventory.md` are resolved to
canonical hierarchy paths and enriched with translations, and which tingbok API
endpoints are involved at each stage.

## Actors

| Component | Role |
|---|---|
| `inventory-md` | CLI that parses inventory.md and calls tingbok |
| `tingbok` | HTTP service that wraps AGROVOC, DBpedia, Wikidata, OFF, UPCitemdb, … |
| `vocabulary.yaml` | Master vocabulary shipped with tingbok (the "linking layer") |

## Stage overview

```
inventory.md
    │
    ▼
1. Parse items   ── extract category: labels, tag: labels, EAN: barcodes
    │
    ▼
2. Load global vocabulary ── GET /api/vocabulary
    │
    ▼
3. Load local-vocabulary.yaml (highest priority, overrides global)
    │
    ▼
4. Build vocabulary from inventory ── merge all known concepts
    │
    ├─ 5a. Orphaned labels (not yet a path) ── GET /api/skos/hierarchy per source
    │
    └─ 5b. EAN barcodes ── GET /api/ean/{ean}
                           │
                           └── category label from product ── GET /api/skos/hierarchy
    │
    ▼
6. Save vocabulary.json ── used by search.html category browser
```

## Stage 1 — Parse items

`inventory_md.parser` extracts all `key:value` metadata from each item line.

```
* category:food/spices/cumin EAN:1234567890128 Cumin seeds
        ↑                        ↑
   category:          ean: metadata key (any case)
```

The `category:` value may be:
- A full path like `food/spices/cumin` (already resolved, stored as-is).
- A bare label like `cumin` (orphaned — needs resolution in stage 5a).

## Stage 2 — Load global vocabulary

```python
vocabulary.fetch_vocabulary_from_tingbok(tingbok_url)
    → GET {tingbok_url}/api/vocabulary
```

Returns all concepts from `vocabulary.yaml` enriched with labels, synonyms, and
descriptions fetched from AGROVOC / DBpedia / Wikidata / OFF in the background.
These concepts form the "linking layer" — root nodes and structural categories
that anchor the hierarchy.

`GET /api/vocabulary/{concept_id}` returns a single concept from the vocabulary
and 404 for unknown IDs.  **This means non-vocabulary concepts cannot currently
be fetched in the same format.**  See [Gap](#gap) below.

## Stage 3 — Load local vocabulary

The file `local-vocabulary.yaml` (or `local-vocabulary.json`) in the inventory
directory is loaded and merged on top of the global vocabulary, giving
instance-specific overrides the highest priority.

## Stage 4 — Build vocabulary from inventory

`vocabulary.build_vocabulary_from_inventory` walks all items, collects every
`category:` value, and creates `Concept` objects for each.  Items with full
paths (`food/spices/cumin`) populate the hierarchy directly.  Items with bare
labels (`cumin`) produce orphaned concepts (`source="inventory"`) awaiting stage 5a.

## Stage 5a — Resolve orphaned labels

```python
vocabulary.resolve_categories_via_tingbok(orphaned_labels, tingbok_url)
```

For each orphaned label (e.g. `"cumin"`):

```
GET /api/skos/hierarchy?label=cumin&source=agrovoc
GET /api/skos/hierarchy?label=cumin&source=dbpedia  (if agrovoc misses)
GET /api/skos/hierarchy?label=cumin&source=wikidata  (if dbpedia misses)
```

The first source that returns `found=true` wins.  The response includes:

```json
{
  "label": "cumin",
  "paths": ["food/spices/cumin"],
  "found": true,
  "source": "agrovoc",
  "uri_map": {"food/spices/cumin": "http://aims.fao.org/aos/agrovoc/c_12851"}
}
```

All path segments are added to the vocabulary (e.g. `food`, `food/spices`,
`food/spices/cumin`).

## Stage 5b — EAN barcode lookup

```python
vocabulary.lookup_ean_via_tingbok(ean, tingbok_url)
    → GET {tingbok_url}/api/ean/{ean}
```

tingbok queries Open Food Facts → UPCitemdb (for products) or Open Library →
nb.no (for ISBNs / books).  The response is a `ProductResponse`:

```json
{
  "ean": "1234567890128",
  "name": "Cumin seeds",
  "brand": "Acme",
  "categories": ["spices", "cumin seeds"],
  "source": "openfoodfacts",
  "type": "product"
}
```

The most specific category (`"cumin seeds"`) is added to the orphaned-label
list and resolved via stage 5a.

## Stage 6 — Save vocabulary.json

The merged vocabulary (with hierarchy paths and `categoryMappings`) is written
to `vocabulary.json` for the `search.html` category browser.

---

## Gap

`GET /api/vocabulary/{concept_id}` only works for concepts **already in
`vocabulary.yaml`**.  Concepts resolved dynamically from SKOS sources (e.g.
`food/spices/cumin`) cannot be fetched in `VocabularyConcept` format after the
parse run.

### Proposed: `GET /api/lookup/{label}`

A unified endpoint that returns `VocabularyConcept` format **regardless of
whether the concept is in `vocabulary.yaml`**:

1. If `label` matches a concept ID in `vocabulary.yaml` → same as
   `GET /api/vocabulary/{label}`.
2. If `label` matches a `prefLabel` or `altLabel` in `vocabulary.yaml` → return
   that concept.
3. Otherwise → query all SKOS sources (agrovoc, dbpedia, wikidata), merge labels,
   altLabels, descriptions (longest wins) and source URIs, and derive the canonical
   concept ID from the hierarchy path (e.g. `food/spices/cumin`).
4. Return 404 only if all sources miss.

Response documents from this endpoint are cacheable in their own directory,
separate from the raw SKOS concept/label cache files, making them easy to
inspect.
