# Inventory Systems Comparison

A comparison of self-hosted inventory management systems with this project.

## Systems Most Relevant for Home Use

| System | Focus | Tech Stack | Database | License |
|--------|-------|------------|----------|---------|
| **This system** | General home/boat inventory | Python, JavaScript | Markdown → JSON | - |
| [Homebox](https://hay-kot.github.io/homebox/) | Home organization | Go | SQLite | AGPL-3.0 |
| [Grocy](https://grocy.info/) | Groceries & household | PHP | SQLite | MIT |
| [InvenTree](https://inventree.org/) | Parts/components | Python/Django | PostgreSQL/MySQL | MIT |
| [Shelf](https://www.shelf.nu/) | Asset tracking | Node.js | - | AGPL-3.0 |

Other systems exist for more specialized use cases:
- **Snipe-IT** - IT asset management
- **Part-DB** - Electronic components
- **Cannery** - Firearm/ammunition tracking
- **Spoolman** - 3D printer filament

See [awesome-selfhosted](https://awesome-selfhosted.net/tags/inventory-management.html) for a complete list.

## Feature Comparison

| Feature | This System | Homebox | Grocy | InvenTree |
|---------|-------------|---------|-------|-----------|
| **Primary use case** | General storage | Home items | Food/groceries | Electronic parts |
| **Expiry tracking** | Yes (bb: field) | No | Yes (core feature) | No |
| **Recipe suggestions** | Yes (Claude skill) | No | Yes (built-in) | No |
| **Photo support** | Yes | Yes | Yes | Yes |
| **QR/barcode labels** | No | Yes | Yes | Yes |
| **Hierarchical tags** | Yes | Labels only | Categories | Categories |
| **Search aliases** | Yes (multilingual) | No | No | No |
| **AI maintenance** | Yes (Claude) | No | No | No |
| **Offline capable** | Yes (static files) | Partial | Partial | No |
| **Mobile app** | Web only | Web PWA | Android/iOS | Mobile apps |
| **Multi-user** | No | Yes | Yes | Yes |
| **Shopping list** | Yes (script) | No | Yes (automatic) | No |
| **Human-editable data** | Yes (Markdown) | No | No | No |

## Analysis by System

### Homebox - Closest to general home use

Homebox is "the inventory and organization system built for the Home User." Written in Go, it's lightweight (<50MB memory) and uses SQLite.

**Pros:**
- Simple, focused on home use
- Low resource requirements
- Docker deployment
- Warranties/manuals tracking
- QR code label generation

**Cons:**
- No food expiry tracking
- No AI assistance
- SQLite database (not human-editable)
- No multilingual search

**Best for:** General home items, IoT devices, warranty tracking

### Grocy - Best for food/groceries

Grocy is "ERP beyond your fridge" - a comprehensive household management solution focused on consumables.

**Pros:**
- Expiry date tracking (core feature)
- Shopping list generation
- Meal planning and recipes
- Barcode scanning via camera
- "Due Score" prioritizes recipes using expiring items

**Cons:**
- Focused primarily on consumables
- Overkill for non-food items
- No AI assistance
- PHP-based (heavier than static files)

**Best for:** Kitchen/pantry management, meal planning, grocery shopping

### InvenTree - Best for parts/components

InvenTree provides "intuitive parts management and stock control" with a focus on manufacturing and electronics.

**Pros:**
- Bill of Materials (BOM) management
- Supplier tracking and pricing
- Extensive plugin ecosystem
- Large community (6000+ GitHub stars)
- Mobile apps available

**Cons:**
- Designed for manufacturing/electronics use cases
- Complex for simple home inventory
- Requires PostgreSQL/MySQL
- No food/expiry tracking

**Best for:** Electronics hobbyists, small manufacturing, parts inventory

## What Makes This System Unique

1. **Markdown as source of truth** - Human-readable, editable in any text editor, version-controlled with git. When all you need is to search and edit, a text file in an editor works great.

2. **AI-assisted maintenance** - Claude can process photos, add tags, translate foreign labels (Greek, Portuguese, etc.), categorize items, and suggest recipes based on expiring food.

3. **Multilingual search** - The aliases.json file handles Norwegian/English/Greek synonyms. A search for "saw" finds "sag" (Norwegian), "voltmeter" finds multimeters.

4. **Fully offline capable** - Static HTML/JS/JSON files work without any server or API. Critical for use on a boat that's sometimes completely offline.

5. **Food expiry + recipes** - Combines general inventory with food expiry tracking and AI-generated recipe suggestions that prioritize using expired items.

## What This System Lacks vs Others

1. **QR/barcode generation** - Homebox, Grocy, and InvenTree all generate printable labels with QR codes for physical items.

2. **Mobile apps** - The web UI works on mobile but isn't a Progressive Web App (PWA) with offline caching.

3. **Multi-user authentication** - Other systems have user accounts, permissions, and family sharing built-in.

4. **Barcode scanning** - Grocy can scan product barcodes to auto-populate item information from databases.

5. **Automatic shopping list** - Grocy generates shopping lists automatically when stock drops; this system requires running a script manually.

6. **Chore/task tracking** - Grocy includes household task management beyond just inventory.

## Shopping List Comparison: This System vs Grocy

This system includes a `shopping-list.py` script that compares a desired provisions list (`food-list.md`) against the actual inventory. Here's how it compares to Grocy's shopping list:

| Feature | This system (shopping-list.py) | Grocy |
|---------|-------------------------------|-------|
| **Approach** | Compare desired list vs inventory | Track stock levels with thresholds |
| **Desired items** | Manual food-list.md with targets | Per-product "minimum stock" setting |
| **Stock tracking** | Parses inventory.md tags/qty | Real-time database updates |
| **Expiry awareness** | Excludes expired items from count | Core feature, also affects "use first" |
| **Recipe integration** | Separate (suggest-recipe skill) | Built-in: "add missing to shopping list" |
| **Barcode scanning** | No | Yes (browser camera) |
| **Store organization** | No | Groups by aisle/section |
| **Output** | Terminal printout | Interactive UI, mobile app |
| **Automation** | Run manually | Automatic when stock drops |

**This system's advantages:**
- **Explicit provisioning targets** in food-list.md - define what you *want* on board, not just minimums
- **Hierarchical tag matching** - `food/cereal` matches `food/cereal/oats`
- **Markdown-based** - editable anywhere, version controlled
- **Offline** - works without server

**Grocy's advantages:**
- **Automatic triggers** - shopping list updates when stock drops below minimum
- **Recipe integration** - one click to add missing ingredients
- **Barcode scanning** - quick product lookup and addition
- **Store layout** - optimize your shopping route
- **Mobile app** - check/update list in store

**Verdict:** This system's approach is better for **provisioning a boat** before a voyage (explicit "what should be on board" list). Grocy is better for **ongoing household replenishment** (automatic "we're low on milk" notifications).

## Recommendations

For a use case involving boat + apartment, food + general items, offline capability, and AI-assisted maintenance:

1. **Keep this system** for general inventory - the markdown approach combined with Claude maintenance is genuinely unique and well-suited for the use case.

2. **Consider Grocy alongside** for dedicated food tracking if barcode scanning and automatic shopping lists become important.

3. **Potential additions to this system:**
   - QR code generation for container labels
   - PWA support for better mobile/offline experience
   - Barcode lookup integration (optional, when online)

## References

- [awesome-selfhosted Inventory Management](https://awesome-selfhosted.net/tags/inventory-management.html)
- [Homebox Documentation](https://hay-kot.github.io/homebox/)
- [Grocy Website](https://grocy.info/)
- [InvenTree Website](https://inventree.org/)
- [Snipe-IT](https://snipeitapp.com/)

---

*Last updated: 2026-01-07*
