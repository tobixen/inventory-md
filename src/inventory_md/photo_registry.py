"""
Photo Registry Parser

Parses photo-registry.md files to extract photo-to-item mappings.
The registry maps individual photos to specific item IDs, enabling
filtered photo viewing when searching for specific items.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def parse_photo_registry(file_path: Path | str) -> dict[str, Any]:
    """Parse a photo-registry.md file into structured JSON data.

    The photo registry format consists of:
    - Session headers (## Session: YYYY-MM-DD)
    - Location/box headers (### BOX-ID description)
    - Tables with | Photo | Item IDs | columns

    Args:
        file_path: Path to the photo-registry.md file.

    Returns:
        Dictionary with structure:
        {
            "photos": {
                "IMG_xxx.jpg": {
                    "items": ["item-id-1", "item-id-2"],
                    "container": "BOX-ID",
                    "session": "2026-01-03",
                    "notes": "(overview)" or null
                }
            },
            "items": {
                "item-id-1": ["IMG_xxx.jpg", "IMG_yyy.jpg"],
                "item-id-2": ["IMG_xxx.jpg"]
            },
            "containers": {
                "BOX-ID": ["IMG_xxx.jpg", "IMG_yyy.jpg"]
            }
        }
    """
    file_path = Path(file_path)
    if not file_path.exists():
        return {"photos": {}, "items": {}, "containers": {}}

    content = file_path.read_text(encoding="utf-8")

    photos: dict[str, dict] = {}
    items: dict[str, list[str]] = {}
    containers: dict[str, list[str]] = {}

    current_session: str | None = None
    current_container: str | None = None

    # Regex patterns
    session_pattern = re.compile(r"^##\s+Session:\s*(\d{4}-\d{2}-\d{2})")
    container_pattern = re.compile(r"^###\s+(\S+)")
    # Table row pattern: | filename.jpg | ID:xxx, ID:yyy | or | filename.jpg | (note) |
    table_row_pattern = re.compile(r"^\|\s*([^|]+)\s*\|\s*([^|]*)\s*\|")

    for line in content.split("\n"):
        line = line.strip()

        # Check for session header
        session_match = session_pattern.match(line)
        if session_match:
            current_session = session_match.group(1)
            continue

        # Check for container/location header
        container_match = container_pattern.match(line)
        if container_match:
            current_container = container_match.group(1)
            continue

        # Check for table row (skip header rows)
        row_match = table_row_pattern.match(line)
        if row_match:
            photo_cell = row_match.group(1).strip()
            items_cell = row_match.group(2).strip()

            # Skip header rows
            if photo_cell.lower() in ("photo", "foto", "bilde", "---", "-------"):
                continue
            if items_cell.lower() in ("item ids", "item id", "items", "---", "-------"):
                continue
            # Skip separator rows
            if photo_cell.startswith("-") or items_cell.startswith("-"):
                continue

            # Must look like a filename
            if not _is_photo_filename(photo_cell):
                continue

            # Parse item IDs and notes
            item_ids, notes = _parse_items_cell(items_cell)

            # Store photo data
            photo_data = {
                "items": item_ids,
                "container": current_container,
                "session": current_session,
            }
            if notes:
                photo_data["notes"] = notes

            photos[photo_cell] = photo_data

            # Update reverse indexes
            for item_id in item_ids:
                if item_id not in items:
                    items[item_id] = []
                if photo_cell not in items[item_id]:
                    items[item_id].append(photo_cell)

            if current_container:
                if current_container not in containers:
                    containers[current_container] = []
                if photo_cell not in containers[current_container]:
                    containers[current_container].append(photo_cell)

    return {
        "photos": photos,
        "items": items,
        "containers": containers,
    }


def _is_photo_filename(text: str) -> bool:
    """Check if text looks like a photo filename."""
    text_lower = text.lower()
    return any(
        text_lower.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".gif", ".heic", ".webp")
    )


def _parse_items_cell(cell: str) -> tuple[list[str], str | None]:
    """Parse the items cell from a table row.

    Args:
        cell: The cell content, e.g., "ID:drill-einhell, ID:wrench-force17"
              or "(overview)" or "ID:item (note about item)"

    Returns:
        Tuple of (list of item IDs, optional notes string)
    """
    item_ids: list[str] = []
    notes: str | None = None

    # Check for notes in parentheses
    # Could be the whole cell "(overview)" or attached to items "ID:item (note)"
    paren_match = re.search(r"\(([^)]+)\)", cell)
    if paren_match:
        # If the whole cell is just a note like "(overview)"
        if cell.strip() == paren_match.group(0):
            notes = paren_match.group(1)
            return item_ids, notes
        else:
            # Extract notes but continue parsing items
            notes = paren_match.group(1)

    # Find all ID:xxx patterns
    id_pattern = re.compile(r"ID:([a-zA-Z0-9_-]+)")
    for match in id_pattern.finditer(cell):
        item_id = match.group(1).lower()
        if item_id not in item_ids:
            item_ids.append(item_id)

    return item_ids, notes


def get_photos_for_items(
    registry: dict[str, Any],
    item_ids: list[str],
) -> list[dict[str, Any]]:
    """Get all photos that show any of the specified items.

    Args:
        registry: Parsed photo registry data.
        item_ids: List of item IDs to find photos for.

    Returns:
        List of photo info dicts with filename and metadata.
    """
    result = []
    seen = set()

    for item_id in item_ids:
        item_id_lower = item_id.lower()
        if item_id_lower in registry.get("items", {}):
            for photo_filename in registry["items"][item_id_lower]:
                if photo_filename not in seen:
                    seen.add(photo_filename)
                    photo_data = registry["photos"].get(photo_filename, {})
                    result.append({
                        "filename": photo_filename,
                        "container": photo_data.get("container"),
                        "items": photo_data.get("items", []),
                        "notes": photo_data.get("notes"),
                    })

    return result


def get_item_photo_count(registry: dict[str, Any]) -> dict[str, int]:
    """Get photo count per item.

    Args:
        registry: Parsed photo registry data.

    Returns:
        Dict mapping item ID to number of photos.
    """
    return {item_id: len(photos) for item_id, photos in registry.get("items", {}).items()}
