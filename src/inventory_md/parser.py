#!/usr/bin/env python3
"""
Inventory System Parser

Parses markdown inventory files into structured JSON data.
Supports hierarchical organization, metadata tags, and automatic image discovery.
Automatically creates resized thumbnails when missing.
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


def create_thumbnail(source_path: Path, dest_path: Path, max_size: int = 800) -> bool:
    """
    Create a resized thumbnail from a source image.

    Args:
        source_path: Path to source image
        dest_path: Path to save thumbnail
        max_size: Maximum width or height in pixels

    Returns:
        True if thumbnail was created, False otherwise
    """
    try:
        from PIL import Image
    except ImportError:
        print("⚠️  Pillow not installed. Run: pip install Pillow", file=sys.stderr)
        return False

    try:
        # Open and resize image
        with Image.open(source_path) as img:
            # Convert RGBA to RGB if needed (for JPEG)
            if img.mode == "RGBA":
                rgb_img = Image.new("RGB", img.size, (255, 255, 255))
                rgb_img.paste(img, mask=img.split()[3])
                img = rgb_img

            # Calculate new size maintaining aspect ratio
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

            # Ensure destination directory exists
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            # Save thumbnail
            img.save(dest_path, quality=85, optimize=True)
            return True
    except Exception as e:
        print(f"⚠️  Failed to resize {source_path.name}: {e}", file=sys.stderr)
        return False


def discover_images(container_id: str, base_path: Path) -> list[dict[str, str]]:
    """
    Automatically discover images for a container from filesystem.

    Looks for images in:
    - photos/{container_id}/*.{jpg,jpeg,png,gif}
    - resized/{container_id}/*.{jpg,jpeg,png,gif}

    Automatically creates missing thumbnails from photos directory.

    Returns list of image dicts with 'alt', 'thumb', and 'full' keys.
    """
    images = []

    # Image extensions to look for
    extensions = (".jpg", ".jpeg", ".png", ".gif", ".JPG", ".JPEG", ".PNG", ".GIF")

    # First, scan photos directory to find all source images
    photos_dir = base_path / "photos" / container_id
    resized_dir = base_path / "resized" / container_id

    if not photos_dir.exists() or not photos_dir.is_dir():
        # No photos directory - nothing to discover
        return images

    # Get all image files from photos directory, sorted by name
    photo_files = sorted([f for f in photos_dir.iterdir() if f.is_file() and f.name.endswith(extensions)])

    # Track thumbnails created
    thumbnails_created = 0

    for photo_file in photo_files:
        # Check if thumbnail exists
        thumb_file = resized_dir / photo_file.name

        if not thumb_file.exists():
            # Create missing thumbnail
            if create_thumbnail(photo_file, thumb_file):
                thumbnails_created += 1

        # Add to images list
        thumb_path = f"resized/{container_id}/{photo_file.name}"
        full_path = f"photos/{container_id}/{photo_file.name}"
        alt_text = f"{container_id}/{photo_file.name}"

        images.append({"alt": alt_text, "thumb": thumb_path, "full": full_path})

    # Report thumbnail creation
    if thumbnails_created > 0:
        print(f"  ✓ Created {thumbnails_created} thumbnail(s) for {container_id}", file=sys.stderr)

    return images


def extract_metadata(text: str) -> dict[str, Any]:
    """
    Extract all key:value pairs from text.

    Patterns:
    - key:value (space-separated)
    - (key:value) (parenthesized)
    - Special handling for tags: tag:value1,value2,value3 becomes ["value1", "value2", "value3"]
    - Special handling for categories: category:path1,path2 becomes ["path1", "path2"]

    Returns: {
        "metadata": {"id": "...", "parent": "...", "type": "...", "tags": [...], "categories": [...]},
        "name": "remaining text after extraction"
    }
    """
    metadata = {}
    tags = []
    categories = []
    remaining = text

    # Match key:value patterns (with or without parentheses)
    # Pattern matches: key:value or (key:value)
    pattern = r"\(?(\w+):([^)\s]+)\)?"

    matches = []
    for match in re.finditer(pattern, text):
        key = match.group(1).lower()
        value = match.group(2).strip()

        # Special handling for tags: split by comma
        if key == "tag":
            tags.extend([tag.strip() for tag in value.split(",") if tag.strip()])
        # Special handling for categories: split by comma, normalize to lowercase
        elif key == "category":
            for cat in value.split(","):
                cat = cat.strip()
                if cat:
                    # Normalize path: lowercase only (keep plural/singular as-is)
                    parts = cat.split("/")
                    normalized_parts = [p.lower() for p in parts]
                    categories.append("/".join(normalized_parts))
        else:
            metadata[key] = value
        matches.append(match)

    # Add tags to metadata if any were found
    if tags:
        metadata["tags"] = tags

    # Add categories to metadata if any were found
    if categories:
        metadata["categories"] = categories

    # Remove matched patterns from text to get clean name
    # Go in reverse to maintain positions
    for match in reversed(matches):
        remaining = remaining[: match.start()] + remaining[match.end() :]

    # Clean up extra spaces
    remaining = re.sub(r"\s+", " ", remaining).strip()

    return {"metadata": metadata, "name": remaining}


def parse_inventory(md_file: Path) -> dict[str, Any]:
    """
    Parse the markdown inventory file into structured data using markdown-it-py.

    This is a refactored version that uses the markdown-it-py library for base parsing.
    It maintains backward compatibility with the original parse_inventory output format.

    Returns:
        {
            'intro': str,
            'numbering_scheme': str,
            'containers': [...]
        }
    """
    from . import md_adapter

    with open(md_file, encoding="utf-8") as f:
        content = f.read()

    result: dict[str, Any] = {"intro": "", "numbering_scheme": "", "containers": []}

    # Parse the markdown structure using markdown-it-py
    sections = md_adapter.parse_markdown_string(content)

    # Track parent relationships from heading hierarchy
    inferred_parents: dict[str, str] = {}

    def process_section(section: md_adapter.MarkdownSection, parent_container_id: str | None = None) -> None:
        """Process a section and its subsections recursively."""
        heading = section.heading

        # Skip special sections
        if heading.strip().startswith("Intro"):
            result["intro"] = "\n\n".join(section.paragraphs)
            return
        if heading.strip().startswith("Nummereringsregime"):
            result["numbering_scheme"] = "\n\n".join(section.paragraphs)
            return
        if heading.strip().startswith("Oversikt over"):
            return

        # Extract metadata from heading
        parsed = extract_metadata(heading)

        # Get container ID
        if parsed["metadata"].get("id"):
            container_id = parsed["metadata"]["id"]
        else:
            # Generate ID from heading text
            clean_heading = parsed["name"] if parsed["name"] else heading
            sanitized = re.sub(r"[^\w\s-]", "", clean_heading)
            sanitized = re.sub(r"\s+", "-", sanitized.strip())
            container_id = sanitized[:50] if sanitized else f"Container-{section.level}"

        # Determine parent
        parent_id = parsed["metadata"].get("parent")
        if not parent_id and parent_container_id:
            parent_id = parent_container_id
            inferred_parents[container_id] = parent_id

        # Parse items from the section's list_items
        items = []
        for list_item in section.list_items:
            item_text = list_item["text"]
            item_parsed = extract_metadata(item_text)

            # Track parent inference for items with IDs
            if item_parsed["metadata"].get("id"):
                item_id = item_parsed["metadata"]["id"]
                inferred_parents[item_id] = container_id

            items.append(
                {
                    "id": item_parsed["metadata"].get("id"),
                    "parent": item_parsed["metadata"].get("parent"),
                    "name": item_parsed["name"],
                    "raw_text": item_text,
                    "metadata": item_parsed["metadata"],
                    "indented": False,
                }
            )

            # Handle nested items
            for nested_item in list_item.get("nested", []):
                nested_text = nested_item["text"]
                nested_parsed = extract_metadata(nested_text)
                items.append(
                    {
                        "id": nested_parsed["metadata"].get("id"),
                        "parent": nested_parsed["metadata"].get("parent"),
                        "name": nested_parsed["name"],
                        "raw_text": nested_text,
                        "metadata": nested_parsed["metadata"],
                        "indented": True,
                    }
                )

        # Handle section headers in paragraphs (like **Arabic:**)
        for para in section.paragraphs:
            if para.startswith("**") and para.endswith(":**"):
                section_name = para[2:-3]
                items.append(
                    {
                        "id": None,
                        "parent": None,
                        "name": section_name,
                        "raw_text": para,
                        "metadata": {},
                        "is_section_header": True,
                    }
                )

        # Get description from paragraphs (excluding section headers and images)
        description_parts = []
        for para in section.paragraphs:
            if para.startswith("**") and para.endswith(":**"):
                continue
            if para.startswith("!["):
                continue
            description_parts.append(para)

        # Create container
        container = {
            "id": container_id,
            "parent": parent_id,
            "heading": parsed["name"],
            "description": " ".join(description_parts),
            "items": items,
            "images": [],
            "photos_link": "",
            "metadata": parsed["metadata"],
        }
        result["containers"].append(container)

        # Process subsections with this container as parent
        for subsection in section.subsections:
            process_section(subsection, container_id)

    # Process all top-level sections
    for section in sections:
        process_section(section)

    # Apply inferred parent relationships (for cases not handled during recursion)
    for container in result["containers"]:
        if not container.get("parent") and container["id"] in inferred_parents:
            container["parent"] = inferred_parents[container["id"]]

    # Discover images from filesystem for each container
    base_path = md_file.parent
    for container in result["containers"]:
        container_id = container.get("id")
        if container_id:
            photo_dir = None
            if container.get("metadata") and container["metadata"].get("photos"):
                photo_dir = container["metadata"]["photos"]
            if not photo_dir:
                photos_link = container.get("photos_link", "")
                if photos_link:
                    photo_dir = photos_link.replace("photos/", "").strip("/")
            if not photo_dir:
                photo_dir = container_id
            discovered_images = discover_images(photo_dir, base_path)
            container["images"] = discovered_images

    return result


def add_container_id_prefixes(md_file: Path) -> tuple[int, dict[str, list[str]]]:
    """
    Add ID: prefix to all container headers and handle duplicates.

    Returns: (num_changes, duplicate_map)
    """
    with open(md_file, encoding="utf-8") as f:
        lines = f.readlines()

    # First pass: collect all container IDs and detect duplicates
    container_ids = defaultdict(list)
    container_lines = []
    in_intro_section = False

    for i, line in enumerate(lines):
        # Track if we're in the Intro or Nummereringsregime sections
        if line.startswith("# Intro") or line.startswith("# Nummereringsregime"):
            in_intro_section = True
            continue
        elif line.startswith("# ") and not line.startswith("## "):
            in_intro_section = False

        if line.startswith("## ") and not line.startswith("### "):
            # Skip subsections within intro/numbering sections
            if in_intro_section:
                continue

            # Skip location sections
            if "Oversikt over ting lagret" in line or "Oversikt over boksene" in line:
                continue

            heading = line[3:].strip()
            parsed = extract_metadata(heading)

            # If already has ID:, use that
            if parsed["metadata"].get("id"):
                container_id = parsed["metadata"]["id"]
            else:
                # Extract container ID from heading (first word usually)
                # Patterns: "Box 9", "A23", "C12", "H5", "Seb1", etc.
                match = re.match(r"^([A-Z]\d+|Box \d+|[A-Z]{1,3}\d+|Seb\d+|[A-Za-z]+\d*)", heading)
                if match:
                    container_id = match.group(1).replace(" ", "")  # "Box 9" -> "Box9"
                else:
                    container_id = None

            if container_id:
                container_ids[container_id].append(i)
                container_lines.append((i, container_id, heading))

    # Second pass: update lines with ID: prefix and handle duplicates
    changes = 0
    duplicate_map = {}

    for line_num, container_id, heading in container_lines:
        parsed = extract_metadata(heading)

        # Check if this container ID is duplicated
        if len(container_ids[container_id]) > 1:
            # Find which occurrence this is
            occurrence = container_ids[container_id].index(line_num) + 1
            unique_id = f"{container_id}-{occurrence}"
            duplicate_map[container_id] = duplicate_map.get(container_id, []) + [unique_id]
        else:
            unique_id = container_id

        # Add ID: prefix if not already present
        if not parsed["metadata"].get("id"):
            new_heading = f"## ID:{unique_id} {heading}\n"
            lines[line_num] = new_heading
            changes += 1

    # Write back if there were changes
    if changes > 0:
        with open(md_file, "w", encoding="utf-8") as f:
            f.writelines(lines)

    return changes, duplicate_map


def validate_inventory(data: dict[str, Any]) -> list[str]:
    """
    Validate inventory data and return list of issues.
    """
    issues = []

    # Build ID map of containers only (items with IDs are just references to containers)
    id_map = {}
    containers_with_parents = defaultdict(list)  # container_id -> list of parents

    # Collect all containers
    for container in data.get("containers", []):
        if container.get("id"):
            if container["id"] in id_map:
                issues.append(f"⚠️  Duplicate container ID: {container['id']}")
            id_map[container["id"]] = container

            # Track if this container has a parent
            if container.get("parent"):
                containers_with_parents[container["id"]].append(container["parent"])

    # Check for containers with multiple parents
    for container_id, parents in containers_with_parents.items():
        if len(parents) > 1:
            unique_parents = list(set(parents))
            if len(unique_parents) > 1:
                issues.append(f"⚠️  {container_id} has multiple parents: {', '.join(unique_parents)}")

    # Check parent references exist
    for container in data.get("containers", []):
        if container.get("parent") and container["parent"] not in id_map:
            issues.append(f"❌ {container['id']}: parent '{container['parent']}' not found")

    # Note: Items with IDs that don't have container sections are fine - they're just references
    # We don't validate this as it's normal to reference containers before they're detailed

    return issues


def save_json(data: dict[str, Any], output_file: Path) -> None:
    """Save inventory data to JSON file."""
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_json(json_file: Path) -> dict[str, Any]:
    """Load inventory data from JSON file."""
    with open(json_file, encoding="utf-8") as f:
        return json.load(f)


def generate_photo_listings(base_path: Path) -> tuple[int, int]:
    """
    Generate photo directory listings for backup purposes.

    Scans photos/* directories and creates photo-listings/{container_id}.txt
    files containing lists of photo filenames (not paths, just filenames).

    Args:
        base_path: Base directory containing photos/ folder

    Returns:
        Tuple of (containers_processed, files_created)
    """
    photos_dir = base_path / "photos"
    listings_dir = base_path / "photo-listings"

    if not photos_dir.exists():
        print(f"⚠️  No photos directory found at {photos_dir}")
        return 0, 0

    # Create listings directory if needed
    listings_dir.mkdir(exist_ok=True)

    containers_processed = 0
    files_created = 0

    # Image extensions to look for
    extensions = (".jpg", ".jpeg", ".png", ".gif", ".JPG", ".JPEG", ".PNG", ".GIF")

    # Process each subdirectory in photos/
    for container_dir in sorted(photos_dir.iterdir()):
        if not container_dir.is_dir():
            continue

        container_id = container_dir.name

        # Get all image files, sorted by name
        photo_files = sorted([f.name for f in container_dir.iterdir() if f.is_file() and f.name.endswith(extensions)])

        if not photo_files:
            # Skip empty directories
            continue

        # Write listing file
        listing_file = listings_dir / f"{container_id}.txt"
        with open(listing_file, "w", encoding="utf-8") as f:
            f.write("\n".join(photo_files) + "\n")

        containers_processed += 1
        files_created += 1

    return containers_processed, files_created
