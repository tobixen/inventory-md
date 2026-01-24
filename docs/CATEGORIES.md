# SKOS-Based Category System Plan

## Overview

Replace/augment the current flat tag system with a SKOS-based hierarchical category system for better product classification. This includes:

1. **Category search** - Search SKOS concepts (not free text)
2. **Hierarchical category browser** - Drill-down tree UI
3. **SKOS integration** - Use AGROVOC/DBpedia + local vocabulary
4. **Keep tags for attributes** - condition, packaging, etc.

## Current State

### Existing Tag System
- Items use `tag:xxx,yyy` syntax in inventory.md
- Tags stored as flat list in `item.metadata.tags`
- search.html has basic tag filter buttons (flat, no hierarchy)
- Solveig inventory already uses hierarchical paths: `tag:tool/hex`, `tag:food/vegetable`

### Existing SKOS Module
- `src/inventory_md/skos.py` - queries AGROVOC/DBpedia SPARQL endpoints
- Caches results in `~/.cache/inventory-md/skos/`
- `SKOSClient.expand_tag("potato")` → `["root_vegetables/potato", "tubers/potato"]`

### Solveig Hierarchical UI (from git history)
- CSS for `.tag-category`, `.tag-dropdown`, `.tag-dropdown-item`
- JavaScript builds `tagHierarchy` Map from tags with `/` separator
- Dropdown menus show category → subcategories

## Design Decisions

1. **Syntax**: Require explicit `category:` prefix (not auto-detected from `/`)
2. **UI**: Tree browser (expandable hierarchy like file explorer)
3. **Aliases**: Deprecate `aliases.json` in favor of SKOS `altLabels` in local-vocabulary.yaml

## Proposed Architecture

### 1. Dual Classification System

```markdown
* category:food/vegetables/potatoes tag:packaging:glass,condition:new Potatoes from garden
```

- **`category:`** - SKOS-based product classification ("what is this") - REQUIRED prefix
- **`tag:`** - Attributes/properties ("what state is it in")

### 2. Data Sources (Priority Order)

1. **Local vocabulary** (`local-vocabulary.yaml`) - site-specific categories
2. **SKOS cache** (`~/.cache/inventory-md/skos/`) - cached AGROVOC/DBpedia lookups
3. **Remote SPARQL** - on-demand queries (with caching)

### 3. Local Vocabulary Format

```yaml
# local-vocabulary.yaml (in inventory directory)
concepts:
  christmas-decorations:
    prefLabel: "Christmas decorations"
    altLabel: ["jul", "xmas", "julepynt"]
    broader: "seasonal/winter"

  boat-equipment:
    prefLabel: "Boat equipment"
    narrower:
      - "boat-equipment/safety"
      - "boat-equipment/navigation"
      - "boat-equipment/maintenance"

  boat-equipment/safety:
    prefLabel: "Safety equipment"
    altLabel: ["life vests", "flares", "pyro"]
```

### 4. Search Modes

| Mode | Input | Matches | Example |
|------|-------|---------|---------|
| Free text | "potato" | Any text containing "potato" | "The Great Potato Cookbook" |
| Category | category:potato | Items categorized as potatoes | Actual potatoes |
| Tag | tag:condition:new | Items with attribute | New items only |

## UI Design

### Category Browser (Hierarchical Tree) - PRIMARY UI

```
┌─────────────────────────────────────┐
│ 📁 Categories              [Clear] │
├─────────────────────────────────────┤
│ ▼ Food (45)                         │
│   ▼ Vegetables (12)                 │
│     ● Potatoes (3)  ← selected      │
│     ○ Carrots (2)                   │
│   ▶ Canned goods (8)                │
│ ▶ Tools (32)                        │
│ ▶ Electronics (18)                  │
└─────────────────────────────────────┘
```

- Click ▶/▼ to expand/collapse
- Click category name to filter (includes all children)
- Radio button (○/●) for leaf selection
- Counts show items in each category (including children)
- Collapsible on mobile to save space

### Category Search Field

```
┌─────────────────────────────────────┐
│ 🏷️ Search categories: [potato    ] │
│   ┌─────────────────────────────┐   │
│   │ 🥔 Potatoes (food/veg...)   │   │
│   │ 🍟 Potato chips (food/sn..) │   │
│   │ 📖 Potato (disambiguation)  │   │
│   └─────────────────────────────┘   │
└─────────────────────────────────────┘
```

- Autocomplete from SKOS prefLabel + altLabel
- Shows hierarchy path
- Separate from free-text search

### Tag Filters (Attributes)

```
┌─────────────────────────────────────┐
│ Condition: [All ▼] Packaging: [All ▼] │
│   ○ new          ○ glass              │
│   ○ used         ○ plastic            │
│   ○ worn         ○ tin                │
│   ○ defect       ○ cardboard          │
└─────────────────────────────────────┘
```

- Dropdown/checkbox filters for common attributes
- Auto-generated from tag namespaces (tag:condition:xxx)

## Implementation Plan

### Phase 1: Parser & Data Model

**Files to modify:**
- `src/inventory_md/parser.py`

**Changes:**
1. Parse `category:path/to/concept` syntax (separate from `tag:`)
2. Store categories in `item.metadata.categories` as list
3. Support both explicit paths and simple labels (expand via SKOS)

```python
# New metadata structure
item = {
    'metadata': {
        'categories': ['food/vegetables/potatoes'],  # SKOS-based
        'tags': ['packaging:glass', 'condition:new'],  # Attributes
    }
}
```

### Phase 2: Local Vocabulary Support

**New file:**
- `src/inventory_md/vocabulary.py`

**Functions:**
```python
def load_local_vocabulary(path: Path) -> dict
def merge_vocabularies(local: dict, skos_cache: dict) -> dict
def lookup_concept(label: str, vocabulary: dict) -> Concept | None
def get_broader_concepts(concept: Concept) -> list[Concept]
def get_narrower_concepts(concept: Concept) -> list[Concept]
def build_category_tree(vocabulary: dict) -> CategoryTree
```

**CLI command:**
```bash
inventory-md vocabulary list              # Show all concepts
inventory-md vocabulary lookup "potato"   # Find concept by label
inventory-md vocabulary add "my-concept"  # Add to local vocabulary
```

### Phase 3: Enhanced search.html

**Changes to template:**
1. Add category browser (collapsible tree)
2. Add category search with autocomplete
3. Add attribute tag filters (dropdowns)
4. Keep free-text search separate
5. Restore hierarchical dropdown from solveig git history

**New JavaScript functions:**
```javascript
// Category tree
function buildCategoryTree(inventoryData, vocabulary)
function renderCategoryBrowser(tree)
function toggleCategoryNode(categoryId)
function selectCategory(categoryPath)

// Category search
function searchCategories(query)
function renderCategoryAutocomplete(results)

// Attribute filters
function buildAttributeFilters(inventoryData)
function renderAttributeDropdowns(attributes)
```

**New data files loaded by search.html:**
- `vocabulary.json` - merged local + cached SKOS concepts

### Phase 4: Parse Command Integration

**Changes to `cli.py` parse command:**
1. Load local-vocabulary.yaml if present
2. Expand category labels to paths via SKOS (with caching)
3. Generate `vocabulary.json` alongside `inventory.json`

```bash
inventory-md parse inventory.md
# Outputs:
#   inventory.json      - inventory data with categories
#   vocabulary.json     - category tree for UI
#   photo-registry.json - (existing)
```

## File Structure

```
inventory-directory/
├── inventory.md
├── inventory.json
├── vocabulary.json          # Generated category tree
├── local-vocabulary.yaml    # User-defined categories
├── search.html
└── ...

~/.cache/inventory-md/skos/  # SKOS lookup cache
├── concept_agrovoc_en_potato_abc123.json
├── concept_dbpedia_en_screwdriver_def456.json
└── ...
```

## Files to Create/Modify

### New Files
- `src/inventory_md/vocabulary.py` - Local vocabulary management
- `tests/test_vocabulary.py` - Tests
- `docs/skos-categories.md` - Documentation (copy of this plan, cleaned up)

**First step**: Copy this plan to `/home/tobias/inventory-system/docs/skos-categories.md`

### Modified Files
- `src/inventory_md/parser.py` - Parse `category:` syntax
- `src/inventory_md/cli.py` - Add vocabulary commands, generate vocabulary.json
- `src/inventory_md/config.py` - Add vocabulary config defaults
- `src/inventory_md/templates/search.html` - Category browser UI
- `src/inventory_md/skos.py` - Minor enhancements for vocabulary integration

## Migration Path

### Backward Compatibility
- Existing `tag:food/vegetable` syntax continues to work (displayed as-is)
- Tags without namespace remain as attribute tags
- No breaking changes to inventory.md format

### Gradual Migration
1. Start using `category:` for new items
2. Optionally convert existing hierarchical tags to `category:` syntax
3. Create local-vocabulary.yaml for site-specific concepts
4. Migrate aliases.json entries to local-vocabulary.yaml altLabels

### Aliases.json Deprecation
- Move search synonyms to `local-vocabulary.yaml` as `altLabels`
- search.html will load vocabulary.json for synonym expansion
- Old aliases.json still loaded for backward compatibility (with deprecation warning)

## Verification

1. **Parser test:**
   ```bash
   echo "* category:food/vegetables ID:test Test item" > /tmp/test.md
   inventory-md parse /tmp/test.md --validate
   ```

2. **Category browser:**
   - Open search.html
   - Category tree should show hierarchy
   - Clicking category filters results

3. **Category search:**
   - Type "potato" in category search
   - Autocomplete shows matching concepts
   - Selecting filters to that category

4. **SKOS expansion:**
   ```bash
   inventory-md skos expand potato
   # Should return hierarchical paths
   ```

5. **Local vocabulary:**
   ```bash
   inventory-md vocabulary list
   inventory-md vocabulary lookup "christmas"
   ```

## Future Extensions (Not in Scope)

- Visual vocabulary editor (web UI)
- Import/export SKOS RDF files
- Multi-language support for labels
- Faceted search combining categories + attributes
