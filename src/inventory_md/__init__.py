"""
Inventory System - A flexible markdown-based inventory management system

Features:
- Parse hierarchical markdown inventory files
- Generate searchable web interfaces
- Support for images, metadata tags, and parent-child relationships
- CLI tools for initialization, parsing, and serving
"""

__version__ = "0.1.0"

from .parser import (
    add_container_id_prefixes,
    extract_metadata,
    load_json,
    parse_inventory,
    save_json,
    validate_inventory,
)

__all__ = [
    "parse_inventory",
    "extract_metadata",
    "validate_inventory",
    "add_container_id_prefixes",
    "save_json",
    "load_json",
]
