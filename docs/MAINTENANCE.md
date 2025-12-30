# Inventory Maintenance Guide

Regular maintenance helps keep your inventory searchable, organized, and useful. This guide outlines recommended tasks and their frequency.

## Quick Reference

| Task | Frequency | Command/Action |
|------|-----------|----------------|
| Run quality check | Weekly | `python scripts/check_quality.py` |
| Full analysis | Monthly | `python scripts/analyze_inventory.py` |
| Process TODO items | As needed | Review items tagged `TODO` |
| Add missing tags | Monthly | See [Tagging Guidelines](#tagging-guidelines) |
| Update aliases | Quarterly | Edit `aliases.json` |
| Backup photos | Monthly | Ensure photos are backed up |

---

## Analysis Scripts

The `scripts/` directory contains tools for analyzing inventory data quality.

### Quality Check (Weekly)

```bash
cd ~/your-inventory
python ~/inventory-system/scripts/check_quality.py
```

This identifies:
- **ERRORS**: Duplicate IDs, missing parent references (fix immediately)
- **WARNINGS**: Items tagged `TODO` (review and resolve)
- **INFO**: Untagged items, empty containers, missing descriptions

Example output:
```
WARNINGS:
  [WARN]  TODO item in A15: Noe skinngreier
  [WARN]  TODO item in C22: Nøkler (eller i en annen boks?)

INFO:
  [INFO]  Untagged items: 202 items have no tags
  [INFO]  Empty containers: 13
  [INFO]  Missing descriptions: 175 containers
```

### Full Analysis (Monthly)

```bash
python ~/inventory-system/scripts/analyze_inventory.py
```

Provides comprehensive statistics:
- Container and item counts
- Tag coverage percentage
- Top tags by frequency
- Hierarchy analysis
- Image coverage

Use this to track progress over time. Consider saving reports:
```bash
python ~/inventory-system/scripts/analyze_inventory.py > reports/$(date +%Y-%m).txt
```

### Tag Export

```bash
# View all tags sorted by frequency
python ~/inventory-system/scripts/export_tags.py

# Export to CSV for spreadsheet analysis
python ~/inventory-system/scripts/export_tags.py --format csv > tags.csv
```

---

## Tagging Guidelines

Tags make items searchable. Aim for **80%+ tag coverage**.

### Adding Tags

In `inventory.md`, add tags to items using the `tag:` prefix:

```markdown
## ID:A1 Box with tools

* tag:verktøy Hammer
* tag:verktøy,elektronikk Drill with battery
* tag:klær,barn Winter jacket, size 140
```

### Common Tag Categories

| Category | Norwegian | English | Use for |
|----------|-----------|---------|---------|
| Children | barn | children | Kids' items, toys |
| Toys | leker | toys | Games, toys, play items |
| Clothes | klær | clothes | Clothing, textiles |
| Tools | verktøy | tools | Hand/power tools |
| Electronics | elektronikk | electronics | Devices, cables, chargers |
| Kitchen | kjøkken | kitchen | Cookware, utensils |
| Books | bok | book | Books, magazines |
| Documents | dokumenter | documents | Papers, manuals |
| Sports | sport | sports | Sports equipment |
| Outdoor | friluft | outdoor | Camping, hiking gear |
| Christmas | jul | christmas | Holiday decorations |
| Easter | påske | easter | Easter items |

### Multi-tagging

Items can have multiple tags:
```markdown
* tag:barn,klær,vinterklær Winter coat for kids
* tag:elektronikk,belysning LED lamp with USB charger
```

### Finding Untagged Items

```bash
# List containers with untagged items
python -c "
import json
with open('inventory.json') as f:
    data = json.load(f)
for c in data['containers']:
    untagged = [i for i in c.get('items', [])
                if not i.get('metadata', {}).get('tags')]
    if untagged:
        print(f\"{c['id']}: {len(untagged)} untagged\")
"
```

---

## Managing TODO Items

Items tagged `TODO` need review - they're typically:
- Unidentified items
- Items needing categorization
- Duplicates to verify
- Items to relocate

### Reviewing TODOs

1. Run quality check to list all TODOs:
   ```bash
   python scripts/check_quality.py 2>&1 | grep "TODO item"
   ```

2. For each TODO item, either:
   - **Identify it**: Remove `TODO` tag, add proper tags
   - **Relocate it**: Move to correct container
   - **Dispose of it**: Remove from inventory if discarded
   - **Keep as TODO**: If still uncertain, leave for next review

### Example TODO Resolution

Before:
```markdown
* tag:TODO Noe skinngreier
```

After investigation:
```markdown
* tag:klær,personlig Skinnhansker og skinnbelte
```

---

## Updating aliases.json

The `aliases.json` file maps search terms to related terms, enabling bilingual search (Norwegian/English) and synonym matching.

### Structure

```json
{
  "english_term": ["norwegian_term", "synonym"],
  "norwegian_term": ["english_term", "synonym"]
}
```

### When to Update

- When adding new tag categories
- When users report search terms not finding expected results
- Quarterly review

### Adding New Aliases

1. Identify the term and its translations/synonyms
2. Add bidirectional mappings:

```json
{
  "flashlight": ["lommelykt", "torch"],
  "lommelykt": ["flashlight", "torch"],
  "torch": ["flashlight", "lommelykt"]
}
```

### Common Alias Patterns

```json
{
  // Singular/plural
  "book": ["bok", "bøker"],
  "books": ["bok", "bøker"],

  // Norwegian/English
  "tools": ["verktøy"],
  "verktøy": ["tools"],

  // Synonyms
  "bike": ["sykkel", "bicycle"],
  "bicycle": ["sykkel", "bike"]
}
```

---

## Container Descriptions

Descriptions help users understand what's in a container without reading every item.

### Adding Descriptions

In `inventory.md`, add text between the heading and items:

```markdown
## ID:A5 Box with holiday items

Easter and Christmas decorations, mostly ornaments and lights.

* tag:påske Easter eggs
* tag:jul Christmas ornaments
```

### Good Descriptions Include

- General category of contents
- Size range (for clothes)
- Condition notes
- Location hints

### Examples

```markdown
## ID:D04 - vacuum bag

Vacuum-packed winter clothes for children, sizes 8-10 years.

* tag:klær,barn Winter jacket
```

```markdown
## ID:E01 - tools and screws

Basic tools for daily use. Kept in hallway for easy access.

* tag:verktøy Hammer
* tag:verktøy Screwdriver set
```

---

## Photo Maintenance

### Checking Photo Coverage

```bash
# Containers without photos
python ~/inventory-system/scripts/analyze_inventory.py | grep "Without images"

# List specific containers missing photos
python -c "
import json
with open('inventory.json') as f:
    data = json.load(f)
for c in data['containers']:
    if not c.get('images'):
        print(c['id'])
"
```

### Regenerating Thumbnails

If photos are added manually (not through the web interface):

```bash
inventory-system parse inventory.md
```

This will:
- Discover new photos in `photos/` directories
- Generate thumbnails in `resized/`
- Update `inventory.json`
- Create photo listings

### Photo Organization

Photos are stored in `photos/{container_id}/`:
```
photos/
├── A1/
│   ├── IMG_001.jpg
│   └── IMG_002.jpg
├── A2/
│   └── photo.jpg
```

---

## Backup Recommendations

### What to Back Up

| Directory/File | Priority | Notes |
|----------------|----------|-------|
| `inventory.md` | Critical | Source of truth |
| `photos/` | Critical | Original photos (large) |
| `aliases.json` | High | Search configuration |
| `inventory.json` | Low | Can be regenerated |
| `resized/` | Low | Can be regenerated |

### Backup Commands

```bash
# Full backup
tar -czf backup-$(date +%Y%m%d).tar.gz inventory.md photos/ aliases.json

# Quick backup (no photos)
tar -czf backup-quick-$(date +%Y%m%d).tar.gz inventory.md aliases.json
```

---

## Troubleshooting

### "Duplicate container ID" Error

Two containers have the same ID. Search for duplicates:
```bash
grep -n "^## ID:" inventory.md | sort -t: -k3 | uniq -d -f2
```

### Items Not Appearing in Search

1. Check if item is tagged
2. Check `aliases.json` for missing search terms
3. Regenerate JSON: `inventory-system parse inventory.md`

### Photos Not Showing

1. Check photo exists in `photos/{container_id}/`
2. Check file extension (must be .jpg, .jpeg, .png, or .gif)
3. Regenerate: `inventory-system parse inventory.md`

---

## Maintenance Checklist

### Weekly
- [ ] Run `check_quality.py`
- [ ] Address any ERRORS immediately
- [ ] Review new TODO items

### Monthly
- [ ] Run `analyze_inventory.py`
- [ ] Add tags to untagged items (target: 10-20 items)
- [ ] Add descriptions to containers without them
- [ ] Review and resolve TODO items
- [ ] Verify backups are current

### Quarterly
- [ ] Review and update `aliases.json`
- [ ] Check photo coverage for important containers
- [ ] Archive old reports
- [ ] Review empty containers (consolidate or remove)
