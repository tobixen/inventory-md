# SKOS-Based Category System

## Overview

The category system provides hierarchical classification for inventory items using SKOS (Simple Knowledge Organization System) vocabularies. Items can be classified using semantic categories that enable "find all food items" or "show all tools" searches.

## Current Status

### Implemented

- **Parser support** - `category:path/to/concept` syntax in inventory.md
- **Vocabulary module** - `src/inventory_md/vocabulary.py` for building category trees
- **SKOS module** - `src/inventory_md/skos.py` for AGROVOC/DBpedia lookups
- **Oxigraph integration** - Local AGROVOC database for fast queries (~7M triples)
- **CLI commands**:
  - `inventory-md parse --skos` - Enrich categories with SKOS lookups
  - `inventory-md skos expand <term>` - Expand terms to hierarchy paths
  - `inventory-md skos lookup <term>` - Look up single concept details
  - `inventory-md vocabulary list/lookup/tree` - Manage local vocabulary
- **Configuration** - `skos.enabled`, `skos.hierarchy_mode`, `skos.languages` in config file
- **CLI hierarchy mode** - `inventory-md parse --hierarchy` expands labels to full SKOS paths
- **Category mappings** - `vocabulary.json` includes `categoryMappings` for search expansion
- **search.html category browser** - Collapsible tree UI with expand/collapse, counts, search
- **Conditional category UI** - Category browser hidden when vocabulary.json missing or empty
- **SKOS path expansion in UI** - Category badges and filters use expanded SKOS paths
- **Plural normalization** - "books" → "book", "potatoes" → "potato"
- **Source priority** - DBpedia for non-food terms, AGROVOC for food terms

### Not Yet Implemented

- [ ] **Local vocabulary import** - `local-vocabulary.yaml` with custom categories
- [ ] **Aliases deprecation** - Migrate aliases.json to vocabulary altLabels

## Two Category Modes

### 1. Path Mode (Current Default)

User defines explicit category paths in inventory.md:

```markdown
* category:food/vegetables/potato ID:P1 Potatoes from garden
* category:tool/garden/shovel ID:T1 Garden shovel
```

Categories are stored as-is. The hierarchy is inferred from path separators.
SKOS enriches with prefLabel/altLabels but doesn't change paths.

**Use when**: You want full control over your category structure.

### 2. SKOS Hierarchy Mode (Planned)

User writes simple labels, system expands to full AGROVOC hierarchy:

```markdown
* category:potato ID:P1 Potatoes from garden
```

System expands to: `food/plant_products/vegetables/root_vegetables/potato`

All food items end up under a unified "food" root, enabling "show all food" queries.

**Use when**: You want automatic organization based on AGROVOC's agricultural vocabulary.

## Usage

### Basic Category Syntax

```markdown
* category:food/vegetables ID:VEG1 Mixed vegetables
* category:book tag:condition:good ID:B1 Cookbook
* category:tool/power/drill tag:brand:makita ID:T1 Makita drill
```

- `category:` - Product classification (what is this)
- `tag:` - Attributes (what state is it in)

### Configuration

Create `inventory-md.yaml` in your inventory directory:

```yaml
lang: en

skos:
  enabled: true          # Enable SKOS lookups in parse --auto
  languages: ["en", "nb"]  # Languages for category labels
```

### CLI Commands

```bash
# Parse with SKOS enrichment
inventory-md parse inventory.md --skos

# Auto-detect files and use config
inventory-md parse --auto

# Expand a term to SKOS hierarchy
inventory-md skos expand potato
# → food/plant_products/vegetables/root_vegetables/potato

# Look up concept details
inventory-md skos lookup hammer

# Show category tree
inventory-md vocabulary tree
```

## Implementation Details

### Files

| File | Purpose |
|------|---------|
| `src/inventory_md/vocabulary.py` | Local vocabulary, category tree building |
| `src/inventory_md/skos.py` | AGROVOC/DBpedia SPARQL client, Oxigraph |
| `src/inventory_md/parser.py` | Parse `category:` syntax from markdown |
| `src/inventory_md/cli.py` | CLI commands for parse, skos, vocabulary |
| `src/inventory_md/config.py` | Configuration with skos.enabled option |

### Generated Files

| File | Purpose |
|------|---------|
| `inventory.json` | Parsed inventory with categories in metadata |
| `vocabulary.json` | Category tree for search.html UI |

### SKOS Data Sources

1. **AGROVOC** (FAO agricultural vocabulary)
   - Local Oxigraph database: `~/.cache/inventory-md/skos/agrovoc.nt.gz`
   - ~7M triples, loads in ~35s, then queries are fast
   - Good for food, agriculture, plants, animals
   - Has Norwegian (nb) labels

2. **DBpedia** (Wikipedia structured data)
   - Remote SPARQL endpoint
   - Good for general concepts: tools, electronics, books
   - No Norwegian labels

### Priority Logic

```python
# In vocabulary._enrich_with_skos():
is_food_term = label.lower() in _FOOD_TERMS
primary_source = "agrovoc" if is_food_term else "dbpedia"
```

Food terms (potato, carrot, etc.) → AGROVOC first
Other terms (hammer, book, etc.) → DBpedia first

## Remaining Work

### Phase 1: Local Vocabulary (Low Priority)

Support `local-vocabulary.yaml` for site-specific categories:

```yaml
concepts:
  christmas-decorations:
    prefLabel: "Christmas decorations"
    altLabel: ["jul", "xmas", "julepynt"]
    broader: "seasonal/winter"

  boat-equipment/safety:
    prefLabel: "Safety equipment"
    altLabel: ["life vests", "flares"]
```

Migrate from `aliases.json`:
```json
{"potato": ["potet", "kartoffel"]}
```
to:
```yaml
concepts:
  potato:
    altLabel: ["potet", "kartoffel"]
```

## Testing

```bash
# Run vocabulary tests
pytest tests/test_vocabulary.py -v

# Test SKOS expansion
inventory-md skos expand potato carrot hammer

# Test full parse with SKOS
inventory-md parse inventory.md --skos

# View generated vocabulary
cat vocabulary.json | jq '.roots'
```

## Known Issues

1. **AGROVOC agricultural bias** - Terms like "bedding" return "litter for animals" instead of household bedding. Mitigated by preferring DBpedia for non-food terms.

2. **DBpedia lacks Norwegian** - Only AGROVOC has Norwegian labels. DBpedia concepts show English only.

3. **Loading time** - First SKOS query loads Oxigraph (~35s). Subsequent queries are fast.

4. **Path explosion** - AGROVOC can return many paths for one concept. Currently limited to first path found.
