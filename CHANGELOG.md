# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **EAN observations pushed to tingbok** — after each parse run, `inventory-md` PUTs
  EAN observations (categories, name, quantity, price) to `PUT /api/ean/{ean}` on the
  configured tingbok server.  This feeds locally-observed product data back into the
  shared EAN database without requiring git-tracked JSON files.
- **`report_ean_to_tingbok()`** in `vocabulary.py` — helper that PUTs a single EAN
  observation to tingbok; silently ignores network failures so parse runs are never blocked.
- **`receipt_names` support in EAN observations** — the Lidl shopping skill now PUTs
  receipt name observations (Bulgarian/local receipt text) to tingbok via `curl -X PUT`
  instead of writing to the local `ean_cache.json`.

### Fixed
- **`enrich_categories_via_lookup`** now normalises labels before sending to
  `/api/lookup`: path-like labels (e.g. `bag/dry-bag`, `electronics/solar-panel`)
  use only the leaf node, and hyphens/underscores are replaced with spaces.
  Previously the raw path was sent verbatim, causing DBpedia to match wildly wrong
  concepts (e.g. `electronics/solar-panel` → `south_african_standard_time`).

### Removed
- **`skos.py`** module (SKOSClient, SPARQL queries to AGROVOC/DBpedia/Wikidata) — all
  source-specific lookups are now handled exclusively by tingbok.
- **`off.py`** module (Open Food Facts taxonomy client) — OFF lookups moved to tingbok.
- **`build_vocabulary_with_skos_hierarchy()`** and `_enrich_with_skos()` from
  `vocabulary.py` — hierarchy expansion is no longer done in inventory-md.
- **`inventory-md skos`** CLI command (`expand`, `lookup`, `cache` subcommands).
- **`--skos` / `--hierarchy`** flags from `inventory-md parse`.
- `skos_enabled`, `skos_hierarchy_mode`, and related config properties.

## [v0.7.0] - 2026-03-04

### Breaking Change
Ref the "Changed" section further down, this release is efficiently adding a hard dependency on my tingbok.plann.no service being up.  Tingbok, including the data, is open source and available both from pypi and github, so should the service be down it's easy to work around this dependency.

(There may be other breaking changes as well that I have forgotten to mention - it's still the 0.x-series, so I'm in my full rights to reorganize things - and as for now, I suppose I'm the only user in the world.  However, this is a concern I find worth flagging)

### Fixed
- **Category tree orphan promotion** removed — `build_category_tree()` no longer
  promotes unreachable concepts to root level.  `_root.narrower` is a whitelist;
  external orphans are excluded.
- **`vocabulary.json` feedback loop** — `find_vocabulary_files()` no longer picks up
  the generated `vocabulary.json` from the CWD as input vocabulary.
- **Shopping list `category:` items** — `parse_inventory_for_shopping()` now processes
  items with `category:` fields (the majority), mapping them to full vocabulary tag
  paths via `vocabulary.json`.  Previously only `tag:` items were processed.
- **`find_expiring_food.py`** — was checking `metadata.tags` (always empty) instead of
  `metadata.categories`; zero food items were found.  Now checks both.

### Added
- **`augmentContainerImagesFromRegistry()`** — items photographed at a parent-container
  level now appear when browsing a sub-container or filtering by category.
- **Multi-source URI support** via `source_uris` and `excluded_sources` on the `Concept`
  dataclass.  When fetched from tingbok, `source_uris` (a list in the API response) is
  converted to a `{source_name: uri}` dict, and `excluded_sources` is passed through.
- **`_should_query_source(source, concept)`** helper — centralised guard for deciding
  whether to query a given external source for a concept:
  - Always `False` for `"tingbok"` (informational only, no upstream lookups).
  - `False` when the source is in `concept.excluded_sources`.
  - `True` otherwise (auto-discover, including sources already in `source_uris`).
- **`_uri_to_source()`** now recognises `https://tingbok.plann.no/` URIs as `"tingbok"`.
### Changed
- **Source label `"package"` renamed to `"tingbok"`** throughout.  The
  `category_by_source/` mirror path now uses the matched concept's actual source
  instead of hardcoding `"local"`, so projects using only the tingbok vocabulary
  see `category_by_source/tingbok/` rather than `category_by_source/local/`.
- **Bundled `vocabulary.yaml` removed** — tingbok is now the sole authoritative source
  for the package vocabulary.  `_get_package_data_dir()` removed.  Local overrides in
  `/etc/inventory-md/`, `~/.config/inventory-md/`, and the current directory continue
  to work as before.  `fetch_vocabulary_from_tingbok()` now raises
  `TingbokUnavailableError` on any network or HTTP error; `parse` and `vocabulary`
  commands abort with `❌ …` and exit code 1 rather than writing a degraded
  `vocabulary.json`.
- **Expansion loop source guards**: all four sources (OFF, AGROVOC, DBpedia, Wikidata)
  now use `_should_query_source()`.  The previous ad-hoc `skip_agrovoc` heuristic
  (skip when concept has a non-AGROVOC URI) is removed; use `excluded_sources:
  [agrovoc]` in `vocabulary.yaml` instead.
- **`_resolve_missing_uris()`** skips concepts whose `source_uris` already contains
  `dbpedia` or `wikidata`, or where both are in `excluded_sources`.

## [v0.6.1] - 2026-02-24

### Fixed
- **Wheel packaging** — removed redundant `artifacts` and `force-include`
  entries for `inventory_md/data/`; `packages = ["src/inventory_md"]` already
  covers git-tracked data files, the duplicate entries caused a 400 error from
  PyPI on upload

## [v0.6.0] - 2026-02-24

### Added
- **Tingbok integration** — inventory-md now fetches the package vocabulary
  from [tingbok.plann.no](https://tingbok.plann.no) by default, with
  transparent fallback to the bundled `vocabulary.yaml` if unreachable
  - New `fetch_vocabulary_from_tingbok()` in `vocabulary.py`
  - `load_global_vocabulary()` gains `tingbok_url` and `skip_cwd` parameters
  - `Config.tingbok_url` property (config key `tingbok.url`,
    env var `INVENTORY_MD_TINGBOK__URL`); defaults to `https://tingbok.plann.no`
  - Set `tingbok.url` to an empty string or `"false"` to disable
- **Direct/REST lookups for DBpedia and Wikidata** — reduces SPARQL load and
  avoids Wikidata rate limiting
  - DBpedia: direct URI construction (Title_Case → resource URL) verified
    with a lightweight SPARQL query, before REST search and full SPARQL
  - Wikidata: MediaWiki Action API (`wbsearchentities` + `wbgetentities`),
    not subject to SPARQL rate limits, before SPARQL label search
  - Wikidata broader concept chain (P31/P279) resolved via REST, making the
    REST lookup path fully SPARQL-free
- **Retry with exponential backoff** for SPARQL and DBpedia REST queries —
  respects `Retry-After` headers on 429s; retries up to 3 times
- **Circuit breaker** — after 5 consecutive endpoint failures, subsequent
  queries are skipped immediately to avoid cascading timeouts
- **SKOS cache directory configurable** via `INVENTORY_MD_SKOS__CACHE_DIR`
  env var; defaults to `~/.cache/inventory-md/skos/`; cache TTL increased
  from 30 to 60 days
- **Multi-source tracking per concept** — new `source_uris` field on `Concept`
  tracks all taxonomy sources (OFF, AGROVOC, DBpedia, Wikidata) that matched
  each concept, with their URIs
  - `_populate_source_uris()` fills `source_uris` from hierarchy-building data
  - `_find_additional_translation_uris()` discovers supplementary DBpedia/Wikidata
    URIs for concepts originally matched via OFF/AGROVOC only
  - Translation phases use `source_uris` directly instead of filtering by URI prefix
  - Search UI shows colored badges for all sources per concept
  - `source_uris` persisted in vocabulary.json for downstream consumers
- **Global vocabulary shipped with package** — default vocabulary bundled in `inventory_md/data/`
  - Multi-location vocabulary loading with merge precedence:
    1. Package default (lowest priority)
    2. `/etc/inventory-md/vocabulary.yaml`
    3. `~/.config/inventory-md/vocabulary.yaml`
    4. `./vocabulary.yaml` or `./local-vocabulary.yaml` (highest priority)
  - New functions: `find_vocabulary_files()`, `load_global_vocabulary()`
- **Language fallback chains** for translations
  - Scandinavian: `nb` → `no` → `da` → `nn` → `sv` → `en`
  - Germanic: `de` → `de-AT` → `de-CH` → `nl` → `en`
  - Romance: `es` → `pt` → `it` → `fr` → `en`
  - Slavic: `ru` → `uk` → `be` → `bg` → `en`
  - Configurable via `language_fallbacks` in config
  - Integrated into AGROVOC (`_get_all_labels`) and OFF (`get_labels`) lookups
  - When a translation is missing, tries related languages before English
  - New functions: `get_fallback_chain()`, `apply_language_fallbacks()`
- **Config file naming** — `config.yaml`/`config.json` now supported in project directory
  - `inventory-md.yaml`/`inventory-md.json` still supported for backward compatibility
- **DBpedia descriptions, Wikipedia URLs, and source attribution**
  - Concepts enriched with short descriptions from DBpedia/Wikipedia
  - Wikipedia article links stored on concepts for UI linking
  - Source attribution tracks which external source provided each concept
- **Local vocab enrichment via DBpedia** — even concepts not in inventory get
  DBpedia metadata (URI, description, wikipediaUrl) when they have a `broader` field
- **`category_by_source` hierarchy preservation** — original source hierarchies
  stored under `category_by_source/<source>/` (OFF, AGROVOC, DBpedia, Wikidata)
  so the raw taxonomy paths survive root mapping
- **Virtual root node** (`_root`) for explicit root control and display ordering
- **Multi-source translation with URI resolution and gap filling**
  - OFF → AGROVOC → DBpedia → Wikidata translation pipeline
  - Each phase fills gaps without overwriting earlier sources
  - Sanity checks reject mismatched labels from every source
- **Wikidata as full independent category source**
  - Concept lookup via Wikidata API
  - Hierarchy building via P31 (instance of) and P279 (subclass of) relations
  - `category_by_source/wikidata/` entries following the same pattern as DBpedia
  - Opt-in via `enabled_sources=["off", "agrovoc", "dbpedia", "wikidata"]`
- **Wikidata translation source and final language fallback pass**
  - Wikidata labels fetched via sitelinks for multilingual coverage
  - Final pass applies `DEFAULT_LANGUAGE_FALLBACKS` to every concept after all
    translation phases, filling gaps like `nb` from `sv`/`da`/`nn`
- **Auto-resolve URIs for local vocab concepts** — new `_resolve_missing_uris()`
  helper batch-queries DBpedia/Wikidata by prefLabel for concepts without URIs,
  enabling translations for previously unreachable concepts

### Changed
- **SKOS lookups routed through tingbok on cache miss** — when `tingbok.url`
  is configured, `SKOSClient` calls tingbok's `/api/skos/lookup` and
  `/api/skos/labels/batch` instead of contacting upstream AGROVOC/DBpedia/Wikidata
  REST APIs directly; network errors fall back to the direct path transparently
- **Skip AGROVOC database load when tingbok is configured** —
  `build_vocabulary_with_skos_hierarchy()` now accepts `tingbok_url` and,
  when set, creates `SKOSClient(use_oxigraph=False)` so the local AGROVOC
  Oxigraph database (~30 s load) is never loaded; upstream SKOS lookups on
  cache misses fall through to the REST APIs as before
- **`Concept.altLabels` changed from `list[str]` to `dict[str, list[str]]`**
  (language → labels) — prevents cross-language false matches (e.g. Norwegian
  "barn" matching English "Barn"); new helpers `get_alt_labels(lang)` and
  `get_all_alt_labels_flat()`; backward compat: flat list wrapped as `{"en": [...]}`
- **Language alias expansion in translation fetch** — `nb↔no` and other aliases
  resolved in all four translation phases (OFF, AGROVOC, DBpedia, Wikidata) so
  OFF's `"no"` labels are fetched and normalised to `"nb"` via fallback chain
- **Distinct `source="package"` for bundled vocabulary** — concepts loaded from the
  package data directory now get `source="package"` instead of `source="local"`,
  making it possible to distinguish package-provided concepts from user-defined ones
- **Wikidata enabled by default** — `enabled_sources` now includes `"wikidata"` in
  all defaults (vocabulary.py, config.py, cli.py); no longer opt-in
- **SPARQL timeout reduced** from 300 s to 30 s
- **Cache empty label results** from succeeded SPARQL queries (to avoid redundant
  re-fetches of concepts with no labels in a given language)
- Merged 18 root categories down to 10: new `recreation` root (outdoor, sports,
  transport); `hardware` absorbs construction and consumables; `household` absorbs
  office, books, documents; `medical` renamed "Health & Safety" and absorbs
  safety-equipment; `hobby` deleted (redundant with transport)
- Renamed `toilet_consumable_paper` → `toilet_paper` in package vocabulary
- Vocabulary deduplication: flat concepts with `broader` are merged into their
  path-prefixed form (e.g., `ac-cable` → `electronics/ac-cable`), removing 138
  orphaned flat duplicates
- Vocabulary slimmed to ~258 concepts (from 596) by removing pure-redirect leaves
- `lang` field written to `inventory.json` so the search UI can auto-detect the
  inventory language; bare `no` in YAML config correctly mapped to language code
- Category label language in search UI initialised from inventory `lang` config
  (was hardcoded to `en`)

### Fixed
- **Parser dropping containers under ID-less structural sections** — sections
  without an explicit `ID:` tag are now treated as organizational wrappers; their
  subsections are still processed as containers but the wrapper itself is not added
  to the inventory; previously a section like "# Oversikt over boksene" caused a
  hard return that silently dropped all 189 containers nested beneath it; hard-coded
  Norwegian/English section name strings removed — configurable via
  `sections.intro` and `sections.numbering_scheme` config keys
- **AGROVOC cross-language mismatches** — leaf URI looked up from the full path
  key; singular/plural variants accepted; false positives from cross-language
  matches eliminated
- **AGROVOC mismatch warnings eliminated** — 14 further false-positive warnings
  during vocabulary build suppressed:
  - AGROVOC lookup skipped when local concept already has a non-AGROVOC URI (9 cases)
  - DBpedia URIs added to mushrooms, lumber, marine_propulsion, medicine (4 cases)
- **altLabel translation map** not using language fallback chain (fixed)
- **Orphan categories promoted** to tree roots for UI visibility
- **Oxigraph startup warning** silenced when `use_oxigraph=False`
- Multi-source translation URI resolution: candidate URIs collected from both
  `all_uri_maps` and `concept.uri`, filtered by source type
- Duplicate connector definitions removed from vocabulary.yaml
- Full broader chain resolution (e.g., `sandpaper-sheet` → `consumables/sandpaper/sandpaper-sheet`)
- OFF mapped roots excluded from URI map to prevent translation mismatches

## [v0.5.0] - 2026-02-04

### Added
- `--version` / `-V` flag to display installed version
- Shell tab completion support via argcomplete
  - Install with `pip install 'inventory-md[completion]'`
  - Activate with `eval "$(register-python-argcomplete inv-md)"`

### Fixed
- `parse` command now respects `skos.enabled` and `skos.hierarchy_mode` config settings even without `--auto` flag

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
