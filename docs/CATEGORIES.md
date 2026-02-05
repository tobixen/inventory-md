# SKOS-Based Category System

## Human-written notes

Most of the content below is AI-generated.  I will look through and perhaps rewrite some of it at some point in the future ... when/if I get time.

I generally think "don't reinvent the wheel" is a good idea - as well as "follow the standards", even when the standards are too complex or designed by people seeing the world with very different eyes than my own.

According to Wikipedia, "Simple Knowledge Organization System (SKOS) is a W3C recommendation designed for representation of thesauri, classification schemes, taxonomies, subject-heading systems, or any other type of structured controlled vocabulary" - so it sounded just perfect.  The AI warned me that it would be too complex, I was probably wrong to ignore that warning - and the public database itself seems to be non-existent.  Two databases was found - AGROVOC is a public SKOS database for food products and agricultural purposes.  The idea was to at least use them for food products.  The agricultural focus can be a bit strong sometimes.  I had a category "bedding" for various douvets, pillows, matresses and bedclothes, but according to AGROVOC the primary purpose of "bedding" is to absorbing animal pee.

DBpedia seems like a more complete and general-purpose database, but for my idea of "hierarchical navigation" it has proven more or less useless (perhaps it's not DBpedia that is the problem, maybe it's my idea of "hierarcihcal navigation" that is useless?).

We're fetching EAN-based information from the openfoodfacts database - and they already have a categorization system - but it's mostly for food products, and even that one didn't work out perfectly in the hierarchical categorization system.

We've ended up with a local vocabulary stiching together the different sources and bringing down the number of root nodes in the category system.  I'm not too happy with it, but let's try it out for a while before rethinking this.

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

- **Global vocabulary** - `~/.config/inventory-md/vocabulary.yaml` with custom categories
- **Open Food Facts** - OFF taxonomy client for food categorization
- **Path normalization** - Collapse duplicate path components (e.g., `food/foods` → `food`)
- **Root category control** - Local vocabulary mappings reduce orphan root categories

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
| `src/inventory_md/vocabulary.py` | Category tree building, path normalization |
| `src/inventory_md/skos.py` | AGROVOC/DBpedia SPARQL client, Oxigraph |
| `src/inventory_md/off.py` | Open Food Facts taxonomy client |
| `src/inventory_md/parser.py` | Parse `category:` syntax from markdown |
| `src/inventory_md/cli.py` | CLI commands for parse, skos, vocabulary |
| `src/inventory_md/config.py` | Configuration with skos.enabled option |
| `~/.config/inventory-md/vocabulary.yaml` | Global vocabulary (user-defined) |

### Generated Files

| File | Purpose |
|------|---------|
| `inventory.json` | Parsed inventory with categories in metadata |
| `vocabulary.json` | Category tree for search.html UI |

### Data Sources

1. **Open Food Facts (OFF)** - Primary source for food items
   - Local taxonomy via `openfoodfacts` Python package
   - ~14K category nodes with localized names
   - Paths normalized to avoid duplicates (e.g., `food/foods` → `food`)
   - Has translations for many languages

2. **AGROVOC** (FAO agricultural vocabulary)
   - Local Oxigraph database: `~/.cache/inventory-md/skos/agrovoc.nt.gz`
   - ~7M triples, loads in ~35s, then queries are fast
   - Good for food, agriculture, plants, animals
   - Has Norwegian (nb) labels

3. **DBpedia** (Wikipedia structured data)
   - Remote SPARQL endpoint
   - Uses both `gold:hypernym` (is-a) and `dct:subject` (category) relations
   - Good for general concepts: tools, electronics, books
   - No Norwegian labels

4. **Global Vocabulary** - User-defined mappings
   - `~/.config/inventory-md/vocabulary.yaml`
   - Takes precedence over external sources
   - Maps orphan categories to proper parents

### Priority Logic

In hierarchy mode (`--hierarchy`), sources are checked in this order:

1. **Global vocabulary** - If label matches a local concept (by ID or altLabel)
2. **Open Food Facts** - For food-related terms
3. **AGROVOC** - For agricultural/food terms not found in OFF
4. **DBpedia** - Fallback for general concepts

Local vocabulary always takes precedence, allowing users to override external mappings.

## Global Vocabulary

The global vocabulary file at `~/.config/inventory-md/vocabulary.yaml` provides:
- Custom category definitions with prefLabel, altLabel, broader, narrower
- Mappings from orphan categories to parent categories (reducing root nodes)
- Override for external sources (OFF, AGROVOC, DBpedia)

Example:
```yaml
concepts:
  food:
    prefLabel: "Food"
    altLabel: ["groceries", "provisions"]
    narrower:
      - food/beverages
      - food/dairy
      - food/grains

  american_fashion:
    prefLabel: "American fashion"
    broader: clothing/fashion

  instant-foods:
    prefLabel: "Instant foods"
    broader: food/preserved
```

Local vocabulary entries take precedence over external source lookups.

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
