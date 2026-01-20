# QR Label Printing Feature Plan

## Overview

Add QR code label generation to inventory-md for printing labels on standard A4 label sheets or label printers. Label sheet formats are user-configurable in the config file using metric dimensions (millimeters).

## Requirements

**ID Format:** Two letters + one digit
- First letter: user-defined **series** (A-Z) - user decides meaning (e.g., A=small items, B=boxes, C=containers)
- Second letter + digit: sequential (A0-A9, B0-B9, ..., Z9 = 260 IDs per series)
- Examples: `AA0`, `AA1`, ..., `AA9`, `AB0`, ..., `AZ9`, `BA0`, `BA1`, ...

**Series concept:** User defines what each series letter means:
- Series A = "small items" or "transparent boxes" or "February batch"
- Series B = "large items" or "cardboard boxes" or "March batch"
- etc. - completely user-defined

**Label Styles:**
1. **compact** - QR code only (for small labels)
2. **standard** - QR + large ID + small date (default)
3. **duplicate** - Two identical QR codes + ID + date (for wide labels, can cut/tear)

**Output Formats:**
- PDF sheets (configurable label formats, e.g., 48.5×25.4mm, 40 labels per A4 sheet)
- PNG images (for custom printing)
- Future: Direct label printer support (Brother QL, Dymo)

## Dependencies

Add to `pyproject.toml`:
```toml
labels = [
    "qrcode[pil]>=7.4",  # QR code generation with Pillow support
    "reportlab>=4.0",     # PDF generation for label sheets
]
```

## Files to Create/Modify

### New Files

1. **`src/inventory_md/labels.py`** - Core label generation module
   ```python
   # Key functions:
   def validate_label_id(label_id: str) -> bool
   def next_id(current: str) -> str
   def generate_id_sequence(series: str = None, start: str = None, count: int = 1) -> list[str]
   def generate_qr(url: str, box_size: int = 10) -> Image
   def generate_label(label_id: str, base_url: str, style: str = "standard", date: str = None) -> Image
   def create_label_sheet(label_ids: list[str], base_url: str, sheet_format: str = "avery5260", style: str = "standard") -> bytes  # PDF

   # Sheet formats registry (dimensions in mm)
   SHEET_FORMATS = {
       "48x25-40": {  # 48.5×25.4mm, 40 labels/sheet (4 cols × 10 rows)
           "cols": 4, "rows": 10,
           "label_width_mm": 48.5, "label_height_mm": 25.4,
           "page_width_mm": 210, "page_height_mm": 297,  # A4
           "margin_top_mm": 13, "margin_left_mm": 4,
       },
       "70x36-24": {  # 70×36mm, 24 labels/sheet (3 cols × 8 rows)
           "cols": 3, "rows": 8,
           "label_width_mm": 70, "label_height_mm": 36,
           ...
       },
   }
   ```

2. **`tests/test_labels.py`** - Unit tests

### Modified Files

1. **`src/inventory_md/cli.py`** - Add `labels` command
2. **`src/inventory_md/config.py`** - Extend labels config defaults
3. **`pyproject.toml`** - Add `[labels]` optional dependency

## CLI Interface

```bash
# Generate a sheet of sequential labels for series A
inventory-md labels generate --series A --count 30 -o labels.pdf
# Generates: AA0, AA1, ..., AA9, AB0, ..., AC9 (30 labels)

# Start from a specific ID
inventory-md labels generate --start AB5 --count 10 -o labels.pdf
# Generates: AB5, AB6, ..., AC4

# Generate labels for specific IDs
inventory-md labels generate --ids AA0,AA1,BA3,CA5 -o labels.pdf

# Compact style (QR only, no text)
inventory-md labels generate --series A --count 30 --style compact -o labels.pdf

# Duplicate QR style (same QR printed twice on wide labels)
inventory-md labels generate --series A --count 30 --duplicate-qr -o labels.pdf

# Generate PNG images instead of PDF
inventory-md labels generate --series B --count 10 --format png -o labels/

# Show available label sheet formats
inventory-md labels formats

# Preview what IDs will be generated (dry run)
inventory-md labels preview --series C --count 6
# Output: CA0 CA1 CA2 CA3 CA4 CA5
```

## Config Integration

Extend `config.py` DEFAULTS:
```python
"labels": {
    "sheet_format": "48x25-40",  # Default: 48.5×25.4mm, 40 labels/A4
    "base_url": "https://inventory.example.com/search.html",
    "style": "standard",  # or "compact"
    "show_date": True,
    "duplicate_qr": False,  # Print multiple QR codes on wide labels
}
```

Config file example:
```yaml
labels:
  base_url: https://my-inventory.local/search.html
  sheet_format: 48x25-40
  style: standard
  show_date: true
  # Custom sheet format (overrides built-in)
  custom_formats:
    my-labels:
      cols: 4
      rows: 10
      label_width_mm: 48.5
      label_height_mm: 25.4
      page_width_mm: 210
      page_height_mm: 297
      margin_top_mm: 13
      margin_left_mm: 4
```

## ID Sequence Logic

```python
def validate_label_id(label_id: str) -> bool:
    """Check if ID matches format: [A-Z][A-Z][0-9]"""
    return len(label_id) == 3 and label_id[0:2].isalpha() and label_id[2].isdigit()

def next_id(current: str) -> str:
    """AA9 -> AB0, AZ9 -> raises (series exhausted, 260 IDs max per series)"""
    series, letter, digit = current[0], current[1], int(current[2])
    if digit < 9:
        return f"{series}{letter}{digit + 1}"
    elif letter < 'Z':
        return f"{series}{chr(ord(letter) + 1)}0"
    else:
        raise ValueError(f"Series {series} exhausted after {current} (max 260 IDs per series)")

def generate_id_sequence(series: str = None, start: str = None, count: int = 1) -> list[str]:
    """Generate count IDs.

    Args:
        series: Single letter A-Z. If provided without start, begins at {series}A0
        start: Starting ID (e.g., "AB5"). Overrides series.
        count: Number of IDs to generate

    Returns:
        List of IDs: ["AA0", "AA1", ...]
    """
    if start:
        current = start.upper()
    elif series:
        current = f"{series.upper()}A0"
    else:
        raise ValueError("Must provide either series or start")

    result = [current]
    for _ in range(count - 1):
        current = next_id(current)
        result.append(current)
    return result
```

## Label Layout

**Standard style** - ID is large/prominent for easy visual scanning, date is small:
```
+---------------------------+
|  [QR]    AA0              |  <- large ID text
|          2026-01-20       |  <- small date text
+---------------------------+
```

**Compact style** - QR code only:
```
+---------------------------+
|         [QR]              |
+---------------------------+
```

**Duplicate QR style** - For wide/rectangular labels, print same QR twice. User can:
- Cut with scissors and apply front/back of item
- Apply whole label to save time (redundant QR codes)
- Tear off one side if only one QR needed
```
+---------------------------+
| [QR]  AA0   [QR]          |  <- same QR code duplicated
|       2026-01-20          |
+---------------------------+
```

Example dimensions (48.5×25.4mm format):
- Label: 48.5mm × 25.4mm
- 4 columns × 10 rows = 40 labels per A4 sheet
- Margins configurable per format

## Implementation Steps

1. **Save plan to docs/**:
   - Copy this plan to `docs/qr-labels-plan.md` for reference

2. **Update `pyproject.toml`**:
   - Add `[labels]` optional dependency group (qrcode, reportlab)

3. **Create `labels.py` module** with:
   - ID validation and sequence generation (`validate_label_id`, `next_id`, `generate_id_sequence`)
   - QR code generation using `qrcode` library
   - Label image generation using Pillow (standard, compact, duplicate styles)
   - PDF sheet generation using `reportlab`
   - Sheet format registry with metric dimensions (mm), user-configurable via config

4. **Update config.py**:
   - Extend `labels` defaults with `base_url`, `sheet_format`, `style`, `show_date`

5. **Add CLI command** in `cli.py`:
   - `labels generate` - main generation command (--series, --start, --ids, --count, --style, -o)
   - `labels formats` - list available sheet formats
   - `labels preview` - show IDs without generating (dry run)

6. **Add tests** (`tests/test_labels.py`):
   - ID validation and sequence generation
   - QR code generation
   - Label image generation (all styles: standard, compact, duplicate)
   - PDF output (basic validation)
   - Custom sheet format configuration

## File Paths

- `/home/tobias/inventory-system/src/inventory_md/labels.py` (new)
- `/home/tobias/inventory-system/src/inventory_md/cli.py` (modify)
- `/home/tobias/inventory-system/src/inventory_md/config.py` (modify)
- `/home/tobias/inventory-system/pyproject.toml` (modify)
- `/home/tobias/inventory-system/tests/test_labels.py` (new)

## QR URL Format (Static File Compatible)

The QR codes encode URLs for the static `search.html` page using hash fragments:
```
https://inventory.example.com/search.html#AA0
```

This works with static file serving (no API server needed). The search.html JavaScript will:
1. Check `location.hash` on page load
2. If hash contains an ID, auto-search and highlight it

**Note:** A small JS addition to search.html may be needed to handle the hash-based navigation.

## Verification

1. Install dependencies: `pip install -e ".[labels]"`
2. Generate test labels: `inventory-md labels generate --series A --count 5 -o test.pdf`
3. Open `test.pdf` - should show 5 labels with QR codes (AA0-AA4)
4. Test with base_url config:
   ```bash
   echo '{"labels": {"base_url": "https://test.example.com/search.html"}}' > inventory-md.json
   inventory-md labels generate --ids AA0 -o test.pdf
   ```
5. Scan QR code - should contain `https://test.example.com/search.html#AA0`
6. Test compact style: `inventory-md labels generate --series B --count 3 --style compact -o compact.pdf`
7. Run tests: `pytest tests/test_labels.py -v`

## Future Extensions (not in scope)

- Direct label printer support (Brother QL-700, Dymo)
- Batch printing from inventory (generate labels for all containers)
- Web UI for label generation
- Custom label templates
