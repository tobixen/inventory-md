# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [v0.4.0] - 2026-01-28

### Added
- QR label generation feature for printing inventory labels **Not tested at all** (sorry - I'll get to it)
  - New `labels` command with `generate`, `formats`, and `preview` subcommands
  - Support for label sheets (configurable formats in mm)
  - Three label styles: standard (QR + ID + date), compact (QR only), duplicate (two QRs)
  - Configurable via config file (`labels.base_url`, `labels.sheet_format`, etc.)
  - `--dupes` option to print multiple copies of each label
- Configuration files
  - Supports `inventory-md.json`, `inventory-md.yaml`
  - Config file may be in the inventory repository, under ~/.config/inventory-md/ or under /etc/inventory-md.
  - If multiple config files are found, data is merged, with local config taking pecedence.
  - All CLI options can be set as defaults in config
  - Environment variables (`INVENTORY_MD_*`) have highest priority
  - Language supported
      - default language for instance
	  - alternative languages for the categories
- Photo registry integration for item-specific photo viewing
  - New `photo_registry.py` parser converts `photo-registry.md` to JSON
  - Parse command generates `photo-registry.json` alongside other files
  - Search interface shows 📷 icon next to items with photos in registry
  - Item-specific lightbox mode for viewing only photos of a specific item
- Proper error handling with tracebacks for server startup
- `update-template` command to refresh search.html to latest version (it's a simple copy actually)
- SKOS vocabulary support for hierarchical tag expansion
  - New `skos` command with `expand`, `lookup`, and `cache` subcommands
  - Queries AGROVOC and DBpedia SPARQL endpoints
  - On-demand lookups with local caching (~/.cache/inventory-md/skos/)
  - Expands simple tags to hierarchical paths (e.g., "potatoes" → "vegetables/potatoes")
  - `--skos` flag for `parse` command to enable SKOS enrichment
  - Category browser in search.html for navigating hierarchical categories
  - Local Oxigraph support for offline AGROVOC lookups
  - DBpedia REST Lookup API support as fallback
  - Multi-language support for category labels (Norwegian, English)
  - Wikipedia links in vocabulary entries
  - Generates `vocabulary.json` with category metadata
- Open Food Facts taxonomy as primary food category source
  - Uses OFF product categories for food item classification
  - AGROVOC mismatch detection with warnings
- New markdown-it-py based parser implementation
- Shared `md-viewer-common.js` library for search interface

### Changed
- Systemd service config path changed to `/etc/inventory-system/`
- Switched HTTP library from `requests` to `niquests` (actively maintained fork)

## [0.3.0] - 2026-01-16

### Added
- `--host` option for `serve` and `api` commands to bind to specific interfaces
- `--api-proxy` option for built-in reverse proxy in `serve` command
- Quick Start Makefile targets (`make quickstart`, `make dev`, `make serve-demo`)
- OCR support for text extraction from images
- Norwegian National Library (nb.no) API for ISBN lookup
- Support for dated wanted-items files in shopping list generator
- Puppet module for automated deployment (puppet-inventory-md)
- GitHub Actions workflows for CI and PyPI publishing
- Pre-commit hooks configuration
- Automatic image discovery from filesystem
  - Parser now scans `photos/{container_id}/` directories for source images
  - Automatically creates missing thumbnails in `resized/{container_id}/`
  - No more manual image list maintenance in markdown
  - Supports `.jpg`, `.jpeg`, `.png`, `.gif` formats
  - Images automatically sorted by filename
  - Uses PIL/Pillow for high-quality resizing (max 800px, quality 85)
- Photo directory metadata support
  - Containers can specify photo directory via `photos:dirname` in heading
  - Allows split containers to share photo directories
- Container-level tag support
  - Tags can be added to container headings (e.g., `tag:jul,påske`)
  - Search interface shows container-level tag badges when filtering
  - Parser extracts metadata from container headings
- Click-to-view full resolution in lightbox
  - Clicking on lightbox image opens full resolution in new tab
  - Zoom-in cursor and tooltip indicate clickability
  - Provides access to original unscaled images

### Changed
- Migrated build system from setuptools to Hatch with hatch-vcs
- Renamed package from `inventory-system` to `inventory-md` as inventory-system is occupied on pypi.
- Default binding changed to localhost (127.0.0.1) for security
- Ruff configuration updated to use recommended rule sets
- **Breaking:** Image references and photo links in markdown are now ignored
  - Images are discovered from filesystem instead of markdown `![...]` syntax
  - Workflow: copy photos to directories → re-parse → done
  - Optional `photos:dirname` metadata may be included
  - Parser no longer parses photo link lines
  - Cleaner markdown files with less clutter
- Parser creates `metadata` field for all containers
  - Includes tags, parent, type, photos, and other metadata from headings

## [0.2.0] - 2025-12-15

### Added
- Multi-language support with English and Norwegian translations
  - Configurable via `LANGUAGE` constant in search.html
  - All UI strings translated (titles, labels, messages, etc.)
- Hierarchical heading parsing for all markdown heading levels (H1-H6)
  - Automatic parent-child relationships inferred from heading structure
  - Supports deeply nested location hierarchies (e.g., boat compartments)
- Dynamic filter button generation based on container ID prefixes
  - No more hardcoded filter buttons for specific series
  - Automatically detects and displays top 10 container prefixes
- Improved container ID generation from headings
  - Sanitizes heading text to create valid IDs
  - Handles special characters and spaces
  - Truncates long IDs to 50 characters
- Demo inventory with comprehensive examples
  - Shows hierarchical organization
  - Demonstrates tagging system
  - Includes sample data for testing
- `.gitignore` file for Python projects

### Changed
- Generic container terminology throughout UI
  - Changed "bokser" (boxes) to "containere" (containers)
  - Removed hardcoded references to specific box series
  - Search placeholder updated to be more generic
- Parser now creates containers for all heading levels, not just H1 and H2
- Heading stack tracking for proper parent inference
- Python version requirement changed to >=3.13,<4.0 (was >=3.14,<4.0)

### Fixed
- Container navigation links now work properly
  - Fixed event bubbling issue with parent links
  - Toggle container function checks if click originated from link
- Filter matching updated to work with dynamic prefixes
  - Uses same prefix extraction logic as filter generation

## [0.1.0] - 2025-12-15

### Added
- Initial release of inventory-md package
- Markdown-based inventory parser
  - Parse inventory.md files into structured JSON
  - Support for hierarchical containers
  - Metadata extraction (ID, parent, type, tags)
  - Image reference parsing
- CLI tool with three commands:
  - `init` - Initialize new inventory
  - `parse` - Parse and validate inventory
  - `serve` - Start local web server
- Web-based search interface
  - Searchable container and item database
  - Lazy-loaded images with lightbox viewer
  - Tag-based filtering with AND logic
  - Gallery view for browsing all images
  - Alias search support
- Package structure with templates
  - Reusable search.html template
  - Aliases.json template for search aliases
  - Example inventory.md template
- Automatic version management with setuptools-scm
- Ruff configuration for code quality
