"""
QR label generation for inventory items.

Generates QR code labels for printing on standard A4 label sheets.
Label sheet formats are user-configurable using metric dimensions (mm).
"""
from __future__ import annotations

import io
import re
from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL import Image as PILImage

# Sheet format registry - dimensions in millimeters
# Format name pattern: {width}x{height}-{count} for easy identification
SHEET_FORMATS: dict[str, dict] = {
    "48x25-40": {
        "description": "48.5x25.4mm, 40 labels per A4 (4 cols x 10 rows)",
        "cols": 4,
        "rows": 10,
        "label_width_mm": 48.5,
        "label_height_mm": 25.4,
        "page_width_mm": 210,
        "page_height_mm": 297,
        "margin_top_mm": 13,
        "margin_left_mm": 4,
        "h_gap_mm": 0,
        "v_gap_mm": 0,
    },
    "70x36-24": {
        "description": "70x36mm, 24 labels per A4 (3 cols x 8 rows)",
        "cols": 3,
        "rows": 8,
        "label_width_mm": 70,
        "label_height_mm": 36,
        "page_width_mm": 210,
        "page_height_mm": 297,
        "margin_top_mm": 4.5,
        "margin_left_mm": 0,
        "h_gap_mm": 0,
        "v_gap_mm": 0,
    },
    "70x37-21": {
        "description": "70x37mm, 21 labels per A4 (3 cols x 7 rows)",
        "cols": 3,
        "rows": 7,
        "label_width_mm": 70,
        "label_height_mm": 37,
        "page_width_mm": 210,
        "page_height_mm": 297,
        "margin_top_mm": 15,
        "margin_left_mm": 0,
        "h_gap_mm": 0,
        "v_gap_mm": 0,
    },
    "63x38-21": {
        "description": "63.5x38.1mm, 21 labels per A4 (3 cols x 7 rows)",
        "cols": 3,
        "rows": 7,
        "label_width_mm": 63.5,
        "label_height_mm": 38.1,
        "page_width_mm": 210,
        "page_height_mm": 297,
        "margin_top_mm": 15.1,
        "margin_left_mm": 7.2,
        "h_gap_mm": 2.5,
        "v_gap_mm": 0,
    },
    "38x21-65": {
        "description": "38.1x21.2mm, 65 labels per A4 (5 cols x 13 rows)",
        "cols": 5,
        "rows": 13,
        "label_width_mm": 38.1,
        "label_height_mm": 21.2,
        "page_width_mm": 210,
        "page_height_mm": 297,
        "margin_top_mm": 10.7,
        "margin_left_mm": 4.7,
        "h_gap_mm": 2.5,
        "v_gap_mm": 0,
    },
}


def validate_label_id(label_id: str) -> bool:
    """Check if ID matches format: [A-Z][A-Z][0-9].

    Args:
        label_id: The label ID to validate.

    Returns:
        True if valid, False otherwise.

    Examples:
        >>> validate_label_id("AA0")
        True
        >>> validate_label_id("ZZ9")
        True
        >>> validate_label_id("A0")
        False
        >>> validate_label_id("AAA")
        False
    """
    if not isinstance(label_id, str):
        return False
    return bool(re.match(r"^[A-Z]{2}[0-9]$", label_id.upper()))


def next_id(current: str) -> str:
    """Get the next ID in sequence.

    Args:
        current: Current ID (e.g., "AA0").

    Returns:
        Next ID in sequence.

    Raises:
        ValueError: If series is exhausted (after XZ9, where X is any series letter).

    Examples:
        >>> next_id("AA0")
        'AA1'
        >>> next_id("AA9")
        'AB0'
        >>> next_id("AZ9")
        Traceback (most recent call last):
            ...
        ValueError: Series A exhausted after AZ9 (max 260 IDs per series)
    """
    current = current.upper()
    if not validate_label_id(current):
        raise ValueError(f"Invalid label ID: {current}")

    series = current[0]
    letter = current[1]
    digit = int(current[2])

    if digit < 9:
        return f"{series}{letter}{digit + 1}"
    elif letter < "Z":
        return f"{series}{chr(ord(letter) + 1)}0"
    else:
        raise ValueError(f"Series {series} exhausted after {current} (max 260 IDs per series)")


def generate_id_sequence(
    series: str | None = None,
    start: str | None = None,
    count: int = 1,
) -> list[str]:
    """Generate a sequence of label IDs.

    Args:
        series: Single letter A-Z. If provided without start, begins at {series}A0.
        start: Starting ID (e.g., "AB5"). Overrides series.
        count: Number of IDs to generate.

    Returns:
        List of IDs, e.g., ["AA0", "AA1", "AA2"].

    Raises:
        ValueError: If neither series nor start is provided, or if count exceeds available IDs.

    Examples:
        >>> generate_id_sequence(series="A", count=3)
        ['AA0', 'AA1', 'AA2']
        >>> generate_id_sequence(start="AB5", count=3)
        ['AB5', 'AB6', 'AB7']
    """
    if start:
        current = start.upper()
        if not validate_label_id(current):
            raise ValueError(f"Invalid start ID: {start}")
    elif series:
        if len(series) != 1 or not series.isalpha():
            raise ValueError(f"Series must be a single letter A-Z, got: {series}")
        current = f"{series.upper()}A0"
    else:
        raise ValueError("Must provide either series or start")

    if count < 1:
        raise ValueError("Count must be at least 1")

    result = [current]
    for _ in range(count - 1):
        current = next_id(current)
        result.append(current)
    return result


def generate_qr(url: str, box_size: int = 10, border: int = 1) -> "PILImage.Image":
    """Generate a QR code image for the given URL.

    Args:
        url: The URL to encode in the QR code.
        box_size: Size of each box in pixels.
        border: Border size in boxes.

    Returns:
        PIL Image of the QR code.
    """
    import qrcode

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(url)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white")


def generate_label(
    label_id: str,
    base_url: str,
    style: str = "standard",
    label_date: str | None = None,
    width_mm: float = 48.5,
    height_mm: float = 25.4,
    dpi: int = 300,
) -> "PILImage.Image":
    """Generate a single label image.

    Args:
        label_id: The label ID (e.g., "AA0").
        base_url: Base URL for the QR code (e.g., "https://inventory.example.com/search.html").
        style: Label style - "standard", "compact", or "duplicate".
        label_date: Date string to show (default: today's date if style is standard/duplicate).
        width_mm: Label width in millimeters.
        height_mm: Label height in millimeters.
        dpi: Resolution in dots per inch.

    Returns:
        PIL Image of the label.
    """
    from PIL import Image, ImageDraw, ImageFont

    # Convert mm to pixels
    width_px = int(width_mm * dpi / 25.4)
    height_px = int(height_mm * dpi / 25.4)

    # Create white background
    img = Image.new("RGB", (width_px, height_px), "white")
    draw = ImageDraw.Draw(img)

    # Build URL with hash fragment
    url = f"{base_url}#{label_id}"

    # Calculate QR code size - leave margin
    margin = int(min(width_px, height_px) * 0.05)
    qr_max_size = height_px - 2 * margin

    if style == "compact":
        # QR code only, centered
        qr_size = min(qr_max_size, width_px - 2 * margin)
        qr_box_size = max(1, qr_size // 25)  # Approximate for version 1 QR
        qr_img = generate_qr(url, box_size=qr_box_size, border=1)
        qr_img = qr_img.resize((qr_size, qr_size), Image.Resampling.LANCZOS)

        # Center the QR code
        x = (width_px - qr_size) // 2
        y = (height_px - qr_size) // 2
        img.paste(qr_img, (x, y))

    elif style == "duplicate":
        # Two QR codes + ID + date
        # Layout: [QR] [ID/Date] [QR]
        section_width = width_px // 3
        qr_size = min(qr_max_size, section_width - 2 * margin)
        qr_box_size = max(1, qr_size // 25)
        qr_img = generate_qr(url, box_size=qr_box_size, border=1)
        qr_img = qr_img.resize((qr_size, qr_size), Image.Resampling.LANCZOS)

        # Left QR code
        x1 = (section_width - qr_size) // 2
        y = (height_px - qr_size) // 2
        img.paste(qr_img, (x1, y))

        # Right QR code
        x2 = 2 * section_width + (section_width - qr_size) // 2
        img.paste(qr_img, (x2, y))

        # Center text area
        _draw_label_text(
            draw,
            label_id,
            label_date,
            section_width,
            section_width,
            0,
            height_px,
            dpi,
        )

    else:  # standard
        # QR code on left, ID and date on right
        qr_size = min(qr_max_size, width_px // 2 - 2 * margin)
        qr_box_size = max(1, qr_size // 25)
        qr_img = generate_qr(url, box_size=qr_box_size, border=1)
        qr_img = qr_img.resize((qr_size, qr_size), Image.Resampling.LANCZOS)

        # Position QR on left
        qr_x = margin
        qr_y = (height_px - qr_size) // 2
        img.paste(qr_img, (qr_x, qr_y))

        # Draw text on right side
        text_x = qr_x + qr_size + margin
        text_width = width_px - text_x - margin
        _draw_label_text(draw, label_id, label_date, text_x, text_width, 0, height_px, dpi)

    return img


def _draw_label_text(
    draw: "ImageDraw.Draw",
    label_id: str,
    label_date: str | None,
    x: int,
    width: int,
    y: int,
    height: int,
    dpi: int,
) -> None:
    """Draw ID and date text on label."""
    from PIL import ImageFont

    # Default date to today
    if label_date is None:
        label_date = date.today().isoformat()

    # Try to use a nice font, fall back to default
    try:
        # Calculate font sizes based on DPI
        id_font_size = int(dpi * 0.15)  # ~45pt at 300dpi
        date_font_size = int(dpi * 0.07)  # ~21pt at 300dpi

        # Try common system fonts
        font_names = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
            "/usr/share/fonts/TTF/DejaVuSansMono-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
            "/System/Library/Fonts/Menlo.ttc",
            "C:\\Windows\\Fonts\\consola.ttf",
        ]
        id_font = None
        for font_path in font_names:
            try:
                id_font = ImageFont.truetype(font_path, id_font_size)
                date_font = ImageFont.truetype(font_path, date_font_size)
                break
            except OSError:
                continue

        if id_font is None:
            id_font = ImageFont.load_default()
            date_font = ImageFont.load_default()
    except Exception:
        id_font = ImageFont.load_default()
        date_font = ImageFont.load_default()

    # Draw ID (large, centered)
    id_bbox = draw.textbbox((0, 0), label_id, font=id_font)
    id_width = id_bbox[2] - id_bbox[0]
    id_height = id_bbox[3] - id_bbox[1]

    id_x = x + (width - id_width) // 2
    id_y = y + height // 3 - id_height // 2

    draw.text((id_x, id_y), label_id, fill="black", font=id_font)

    # Draw date (small, below ID)
    date_bbox = draw.textbbox((0, 0), label_date, font=date_font)
    date_width = date_bbox[2] - date_bbox[0]
    date_height = date_bbox[3] - date_bbox[1]

    date_x = x + (width - date_width) // 2
    date_y = y + 2 * height // 3 - date_height // 2

    draw.text((date_x, date_y), label_date, fill="gray", font=date_font)


def get_sheet_format(
    format_name: str,
    custom_formats: dict | None = None,
) -> dict:
    """Get sheet format by name.

    Args:
        format_name: Name of the format (e.g., "48x25-40").
        custom_formats: Optional dict of custom formats from config.

    Returns:
        Sheet format dictionary.

    Raises:
        ValueError: If format not found.
    """
    # Check custom formats first
    if custom_formats and format_name in custom_formats:
        return custom_formats[format_name]

    if format_name in SHEET_FORMATS:
        return SHEET_FORMATS[format_name]

    raise ValueError(f"Unknown sheet format: {format_name}. Available: {list(SHEET_FORMATS.keys())}")


def create_label_sheet(
    label_ids: list[str],
    base_url: str,
    sheet_format: str | dict = "48x25-40",
    style: str = "standard",
    label_date: str | None = None,
    custom_formats: dict | None = None,
) -> bytes:
    """Create a PDF with labels arranged on a sheet.

    Args:
        label_ids: List of label IDs to print.
        base_url: Base URL for QR codes.
        sheet_format: Format name or format dict.
        style: Label style ("standard", "compact", "duplicate").
        label_date: Date to show on labels (default: today).
        custom_formats: Optional custom formats from config.

    Returns:
        PDF file contents as bytes.
    """
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    # Get format spec
    if isinstance(sheet_format, dict):
        fmt = sheet_format
    else:
        fmt = get_sheet_format(sheet_format, custom_formats)

    # Page size
    page_width = fmt["page_width_mm"] * mm
    page_height = fmt["page_height_mm"] * mm

    # Label dimensions
    label_width = fmt["label_width_mm"] * mm
    label_height = fmt["label_height_mm"] * mm

    # Grid
    cols = fmt["cols"]
    rows = fmt["rows"]
    labels_per_page = cols * rows

    # Margins and gaps
    margin_top = fmt["margin_top_mm"] * mm
    margin_left = fmt["margin_left_mm"] * mm
    h_gap = fmt.get("h_gap_mm", 0) * mm
    v_gap = fmt.get("v_gap_mm", 0) * mm

    # Create PDF in memory
    pdf_buffer = io.BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=(page_width, page_height))

    # Process labels
    label_idx = 0
    while label_idx < len(label_ids):
        # Generate labels for this page
        for row in range(rows):
            for col in range(cols):
                if label_idx >= len(label_ids):
                    break

                label_id = label_ids[label_idx]

                # Calculate position (from top-left, but PDF uses bottom-left)
                x = margin_left + col * (label_width + h_gap)
                y = page_height - margin_top - (row + 1) * label_height - row * v_gap

                # Generate label image
                label_img = generate_label(
                    label_id,
                    base_url,
                    style=style,
                    label_date=label_date,
                    width_mm=fmt["label_width_mm"],
                    height_mm=fmt["label_height_mm"],
                )

                # Convert to bytes for reportlab
                img_buffer = io.BytesIO()
                label_img.save(img_buffer, format="PNG")
                img_buffer.seek(0)

                # Draw on PDF
                from reportlab.lib.utils import ImageReader

                c.drawImage(
                    ImageReader(img_buffer),
                    x,
                    y,
                    width=label_width,
                    height=label_height,
                )

                label_idx += 1

            if label_idx >= len(label_ids):
                break

        # New page if more labels
        if label_idx < len(label_ids):
            c.showPage()

    c.save()
    pdf_buffer.seek(0)
    return pdf_buffer.read()


def save_labels_as_png(
    label_ids: list[str],
    base_url: str,
    output_dir: str,
    style: str = "standard",
    label_date: str | None = None,
    width_mm: float = 48.5,
    height_mm: float = 25.4,
) -> list[str]:
    """Save labels as individual PNG files.

    Args:
        label_ids: List of label IDs.
        base_url: Base URL for QR codes.
        output_dir: Directory to save PNG files.
        style: Label style.
        label_date: Date for labels.
        width_mm: Label width in mm.
        height_mm: Label height in mm.

    Returns:
        List of created file paths.
    """
    from pathlib import Path

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    created_files = []
    for label_id in label_ids:
        img = generate_label(
            label_id,
            base_url,
            style=style,
            label_date=label_date,
            width_mm=width_mm,
            height_mm=height_mm,
        )
        filename = output_path / f"{label_id}.png"
        img.save(filename)
        created_files.append(str(filename))

    return created_files


def list_formats(custom_formats: dict | None = None) -> list[tuple[str, str]]:
    """List available sheet formats.

    Args:
        custom_formats: Optional custom formats from config.

    Returns:
        List of (name, description) tuples.
    """
    formats = []
    for name, spec in SHEET_FORMATS.items():
        formats.append((name, spec.get("description", f"{spec['cols']}x{spec['rows']} labels")))

    if custom_formats:
        for name, spec in custom_formats.items():
            desc = spec.get("description", f"{spec.get('cols', '?')}x{spec.get('rows', '?')} labels (custom)")
            formats.append((name, desc))

    return formats
