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
2. Load global vocabulary ── GET /api/vocabulary  (shared HTTP/2 session)
    │
    ▼
3. Load local-vocabulary.yaml (highest priority, overrides global)
    │
    ▼
4. Build vocabulary from inventory ── merge all known concepts
    │
    ├─ 5a. EAN barcodes ── GET /api/ean/{ean}
    │                      │
    │                      └── category label from product ──┐
    │                                                        │
    └─ 5b. Enrich all inventory categories not in global    ─┘
           vocab ── GET /api/lookup/{label} (all sources merged)
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
- A full path like `food/spices/cumin` — each path segment (`food`, `food/spices`,
  `food/spices/cumin`) becomes a concept that may need enrichment from tingbok (translations,
  altLabels, description, source URIs, alternative paths).
- A bare label like `cumin` — needs resolution to a canonical path via stage 5b.

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
and 404 for unknown IDs.  For concepts not in `vocabulary.yaml`, use
`GET /api/lookup/{label}` instead — see [below](#get-apilookuplabel-implemented).

## Stage 3 — Load local vocabulary

The file `local-vocabulary.yaml` (or `local-vocabulary.json`) in the inventory
directory is loaded and merged on top of the global vocabulary, giving
instance-specific overrides the highest priority.

## Stage 4 — Build vocabulary from inventory

`vocabulary.build_vocabulary_from_inventory` walks all items, collects every
`category:` value, and creates `Concept` objects for each.  Both full paths and
bare labels produce concepts with `source="inventory"` awaiting enrichment in
stage 5.

## Stage 5a — EAN barcode lookup

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

The most specific category (`"cumin seeds"`) is queued for enrichment in stage 5b.

## Stage 5b — Enrich all inventory categories

```python
vocabulary.enrich_categories_via_lookup(labels, tingbok_url, session=session)
    → GET {tingbok_url}/api/lookup/{label}  (for each label)
```

Every concept with `source="inventory"` that is **not** already in the global
vocabulary is enriched via `GET /api/lookup/{label}`.  This covers both:

- **Full paths** like `food/spices/cumin` — gains translations, altLabels,
  description, source URIs, and alternative hierarchy paths.
- **Bare labels** like `cumin` (or EAN-derived labels like `"cumin seeds"`) —
  resolved to a canonical path and fully enriched.

All HTTP calls share a single `niquests.Session(multiplexed=True)` so that
multiple requests to the same tingbok host are sent over one HTTP/2 connection.

The response is a `VocabularyConcept` (same format as `GET /api/vocabulary/{id}`),
with all SKOS sources already merged by tingbok.  All path segments are added to
the vocabulary.  For bare labels that resolved to a different concept ID, a
`categoryMappings` entry is recorded so the search UI can expand the label to
its canonical path.

## Stage 6 — Save vocabulary.json

The merged vocabulary (with hierarchy paths and `categoryMappings`) is written
to `vocabulary.json` for the `search.html` category browser.

---

## `GET /api/lookup/{label}` (implemented)

A unified endpoint that returns `VocabularyConcept` format **regardless of
whether the concept is in `vocabulary.yaml`**:

1. If `label` matches a concept ID in `vocabulary.yaml` → same as
   `GET /api/vocabulary/{label}`.
2. If `label` matches a `prefLabel` or `altLabel` in `vocabulary.yaml` → return
   that concept.
3. Otherwise → query **all** SKOS sources (agrovoc, dbpedia, wikidata) **in
   parallel** via `asyncio.gather`, merge labels (first-per-language), altLabels
   (union), descriptions (longest wins) and source URIs (union), and derive the
   canonical concept ID from the hierarchy path (e.g. `food/spices/cumin`).
4. Return 404 only if all sources miss.

inventory-md uses `niquests.Session(multiplexed=True)` for all requests to
tingbok, enabling HTTP/2 connection reuse across multiple `/api/lookup` calls.

Caching is currently handled by the underlying SKOS service (per-concept/label
files in `~/.cache/tingbok/skos/`).  Separating lookup results into their own
cache directory for easier inspection is a future improvement.
