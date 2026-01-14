# Inventory Analysis Scripts

Standalone Python scripts for analyzing inventory data. These scripts work directly with `inventory.json` files and have no dependencies beyond Python 3.10+.

## Scripts

### analyze_inventory.py

Comprehensive analysis of an inventory file, printing statistics about containers, items, images, tags, and hierarchy.

```bash
# Analyze inventory in current directory
python scripts/analyze_inventory.py

# Analyze specific inventory
python scripts/analyze_inventory.py ~/furuset-inventory/inventory.json
```

**Output includes:**
- Container counts (total, empty, with/without images)
- Item statistics (total, tagged, untagged)
- Top 15 tags by frequency
- Hierarchy analysis (parent/child relationships)
- Data quality summary

### check_quality.py

Focused data quality checker that identifies issues requiring attention.

```bash
# Check inventory in current directory
python scripts/check_quality.py

# Check specific inventory
python scripts/check_quality.py ~/furuset-inventory/inventory.json

# Verbose output
python scripts/check_quality.py -v inventory.json
```

**Checks performed:**
- Duplicate container IDs (ERROR)
- Missing parent references (ERROR)
- Items tagged TODO (WARNING)
- Untagged items (INFO)
- Empty containers (INFO)
- Missing descriptions (INFO)
- Containers without images (INFO)

**Exit codes:**
- `0` - No errors found
- `1` - Errors found
- `2` - File not found or other error

### export_tags.py

Export tag statistics in various formats for reporting or further analysis.

```bash
# Text output (default)
python scripts/export_tags.py inventory.json

# CSV output (for spreadsheets)
python scripts/export_tags.py inventory.json --format csv > tags.csv

# JSON output (for processing)
python scripts/export_tags.py inventory.json --format json > tags.json
```

**Available formats:**
- `text` - Human-readable table
- `csv` - Comma-separated values
- `json` - Structured JSON

## Usage Examples

### Quick Health Check

```bash
cd ~/furuset-inventory
python ~/inventory-md/scripts/check_quality.py
```

### Generate Full Report

```bash
cd ~/furuset-inventory
python ~/inventory-md/scripts/analyze_inventory.py > report.txt
```

### Compare Two Inventories

```bash
# Generate stats for both
python scripts/analyze_inventory.py ~/furuset-inventory/inventory.json > furuset-stats.txt
python scripts/analyze_inventory.py ~/solveig-inventory/inventory.json > solveig-stats.txt

# Compare
diff furuset-stats.txt solveig-stats.txt
```

### Export Tags for Review

```bash
python scripts/export_tags.py inventory.json --format csv | sort -t',' -k2 -nr > tags-sorted.csv
```

## Integration with inventory-md

These scripts complement the main `inventory-md` CLI:

1. Run `inventory-md parse` to update JSON from markdown
2. Run analysis scripts to review the data
3. Use the insights to improve the inventory

## Adding to PATH

For convenience, add the scripts directory to your PATH:

```bash
# Add to ~/.bashrc or ~/.zshrc
export PATH="$PATH:$HOME/inventory-md/scripts"

# Then use directly
analyze_inventory.py ~/furuset-inventory/inventory.json
check_quality.py
```
