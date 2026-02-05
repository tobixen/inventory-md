# SKOS-Based Category System

## Human-written notes

Most of the content below is AI-generated.  I will look through and perhaps rewrite some of it at some point in the future ... when/if I get time.

### SKOS

I generally think "don't reinvent the wheel" is a good idea - as well as "follow the standards", even when the standards are too complex or designed by people seeing the world with very different eyes than my own.

According to Wikipedia, "Simple Knowledge Organization System (SKOS) is a W3C recommendation designed for representation of thesauri, classification schemes, taxonomies, subject-heading systems, or any other type of structured controlled vocabulary" - so it sounded just perfect.  The AI warned me that it would be too complex, I was probably wrong to ignore that warning.

### Categories vs tags vs ...

SKOS is currently used for categories - while everything that does not fit into a category system should be put into tags.  Consider two worn out red cotton T-shirt owned by dad.  T-shirt is a category, while ownership, size, condition, quantity, color etc are other "dimensions".  For quantity etc the inventory-system supports qty, mass, volume ... but whatever is not directly supported should go into tags.

### Public databases

Perhaps I started in the wrong end here - because usage of SKOS in itself is sort of just establishing the database schema - what is more important here is actually to get access a global public category database.   Two SKOS-based databases was found - AGROVOC is a public SKOS database for food products and agricultural purposes, and DBpedia is a Wikipedia-based database.  We're also accessing some few databases to look up EANs - one of them is the OpenFoodFacts database, it has it's own category system (not SKOS-based), so it was decided to use the OFF category system as a third source.

TODO: how does other inventory-systems solve this?  Does the other EAN-sources we're using having any kind of caegorization system?

### Scope

The scope of inventory-md is to be a general domestic inventory database, used both for food products, clothes, kitchen equipment, electronics, household items, hobby items, tools, sports equipment, more specialized equipment, and in general just everything.  I'm not only using it in a house, I'm using it on my yacht too.

AGROVOC has an agricultural focus.  This does not only limit its scope, but it also puts some color to the vocabulary.  For instance, in a domestic setting the category "bedding" may include various douvets, pillows, matresses and bedclothes, but according to AGROVOC "beddings" are products optimized for absorbing animal pee.

DBpedia has a more general focus, but for different reasons it's not very well-suited for inventory-md as it's currently (2026-02) designed.

OFF has a food/kitchen focus.

### Hiearchical categories

The idea of using "hierarchical categories" came before I started investigating SKOS.  Perhaps I started in the wrong end here also - perhaps I first should have investigated what we can get out from SKOS and public databases and then later decided on how to build the navigation system (TODO: does it make sense to redo this completely perhaps?).  Particularly DBpedia is quite weak on putting things into a hierarchical system.

For the hierarhical navigation to work out, we need relatively few root nodes (10 is probably a good number, 100 is too much), and every root node should have relatively few children (5-10 is probably a good number, 100 is way too much).  I see no problem with having multiple paths to the same category - but it may be a bit silly when some of the paths are just irrelevant for the item in the category.

As for now we've ended up with a "global vocabulary" stitching together the different sources and bringing down the number of root nodes in the category system.  The vocabulary serves as a **linking layer** - mapping concepts from external databases (OFF, AGROVOC, DBpedia) into a clean hierarchy optimized for domestic inventory use.

### Vocabulary Loading (as of 2026-02)

The global vocabulary is now **shipped with the package** and loaded from multiple locations with merge precedence:

1. **Package default** (`inventory_md/data/vocabulary.yaml`) - lowest priority
2. **System config** (`/etc/inventory-md/vocabulary.yaml`)
3. **User config** (`~/.config/inventory-md/vocabulary.yaml`)
4. **Instance-specific** (`./vocabulary.yaml` or `./local-vocabulary.yaml`) - highest priority

Later files override earlier ones, allowing users to customize or extend the default vocabulary without modifying the package.

### Language Fallback Chains

For translations, the system now supports language fallback chains. When a label isn't found in the preferred language, it tries related languages before falling back to English:

- **Scandinavian**: `nb` → `no` → `da` → `nn` → `sv` → `en`
- **Germanic**: `de` → `de-AT` → `de-CH` → `nl` → `en`
- **Romance**: `es` → `pt` → `it` → `fr` → `en`

This leverages mutual intelligibility between related languages (e.g., a Norwegian user can read Danish labels).

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

- **Global vocabulary** - shipped with package, loaded from multiple locations with merge precedence
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
| `src/inventory_md/vocabulary.py` | Category tree building, path normalization, multi-location loading |
| `src/inventory_md/skos.py` | AGROVOC/DBpedia SPARQL client, Oxigraph |
| `src/inventory_md/off.py` | Open Food Facts taxonomy client |
| `src/inventory_md/parser.py` | Parse `category:` syntax from markdown |
| `src/inventory_md/cli.py` | CLI commands for parse, skos, vocabulary |
| `src/inventory_md/config.py` | Configuration with skos.enabled, language_fallbacks |
| `src/inventory_md/data/vocabulary.yaml` | Package default vocabulary (shipped) |
| `~/.config/inventory-md/vocabulary.yaml` | User vocabulary overrides |
| `./vocabulary.yaml` or `./local-vocabulary.yaml` | Instance-specific vocabulary |

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

4. **Global Vocabulary** - Merged from multiple locations
   - Package default + system + user + instance-specific
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

The vocabulary is loaded from multiple locations, merged with precedence:

1. **Package default** (`inventory_md/data/vocabulary.yaml`) - shipped with inventory-md
2. **System config** (`/etc/inventory-md/vocabulary.yaml`) - for system-wide customization
3. **User config** (`~/.config/inventory-md/vocabulary.yaml`) - for user preferences
4. **Instance-specific** (`./vocabulary.yaml` or `./local-vocabulary.yaml`) - for this inventory

Each file provides:
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
