"""
Local vocabulary management for SKOS-based category system.

Provides functions to:
- Load local vocabulary definitions from YAML files
- Merge local vocabularies with SKOS cache
- Build category trees for the UI
- Look up concepts by label (including altLabels)

Local vocabulary format (local-vocabulary.yaml):
    concepts:
      christmas-decorations:
        prefLabel: "Christmas decorations"
        altLabel: ["jul", "xmas", "julepynt"]
        broader: "seasonal/winter"

      boat-equipment:
        prefLabel: "Boat equipment"
        narrower:
          - "boat-equipment/safety"
          - "boat-equipment/navigation"

      boat-equipment/safety:
        prefLabel: "Safety equipment"
        altLabel: ["life vests", "flares"]

      seal:
        prefLabel: "Seal"
        altLabel: ["rubber seal", "gasket", "o-ring"]
        uri: "http://dbpedia.org/resource/Hermetic_seal"
        # source is always "local" unless explicitly overridden
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import niquests

logger = logging.getLogger(__name__)

VIRTUAL_ROOT_ID = "_root"

_EAN_CACHE_TTL_DAYS = 7
_LOOKUP_CACHE_TTL_DAYS = 7


def _cache_read(path: Path, ttl_days: int) -> dict | None:
    """Read a JSON cache entry; return None if missing or expired."""
    try:
        entry = json.loads(path.read_text(encoding="utf-8"))
        cached_at = datetime.fromisoformat(entry["cached_at"])
        age = datetime.now(timezone.utc) - cached_at.astimezone(timezone.utc)
        if age.days < ttl_days:
            return entry
    except Exception:  # noqa: BLE001
        pass
    return None


def _cache_write(path: Path, **fields: Any) -> None:
    """Write a JSON cache entry, adding a ``cached_at`` timestamp."""
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {"cached_at": datetime.now(timezone.utc).isoformat(), **fields}
    path.write_text(json.dumps(entry, ensure_ascii=False), encoding="utf-8")


class TingbokUnavailableError(RuntimeError):
    """Raised when the tingbok service cannot be reached or returns an error."""


# =============================================================================
# VOCABULARY FILE DISCOVERY
# =============================================================================


def find_vocabulary_files() -> list[Path]:
    """Find all vocabulary files, in merge order (lowest priority first).

    Searches in order:
    1. /etc/inventory-md/vocabulary.yaml
    2. ~/.config/inventory-md/vocabulary.yaml
    3. ./vocabulary.yaml or ./local-vocabulary.yaml (highest priority)

    The canonical package vocabulary is fetched from tingbok; use
    load_global_vocabulary(tingbok_url=...) for the full vocabulary.

    Returns:
        List of found vocabulary files. Files later in the list override earlier.
    """
    found_files: list[Path] = []
    vocab_filenames = ["vocabulary.yaml", "vocabulary.yml", "vocabulary.json"]
    # vocabulary.json is excluded from the CWD list because it is the generated
    # parse output; accepting it as input would cause a feedback loop.
    local_vocab_filenames = [
        "local-vocabulary.yaml",
        "local-vocabulary.yml",
        "local-vocabulary.json",
        "vocabulary.yaml",
        "vocabulary.yml",
    ]

    # 1. System-wide config (/etc/inventory-md/)
    etc_dir = Path("/etc/inventory-md")
    if etc_dir.exists():
        for filename in vocab_filenames:
            path = etc_dir / filename
            if path.exists():
                found_files.append(path)
                logger.debug("Found system vocabulary: %s", path)
                break

    # 2. User config (~/.config/inventory-md/)
    user_dir = Path.home() / ".config" / "inventory-md"
    if user_dir.exists():
        for filename in vocab_filenames:
            path = user_dir / filename
            if path.exists():
                found_files.append(path)
                logger.debug("Found user vocabulary: %s", path)
                break

    # 3. Current directory (highest priority) - also check local-vocabulary.*
    cwd = Path.cwd()
    for filename in local_vocab_filenames:
        path = cwd / filename
        if path.exists():
            found_files.append(path)
            logger.debug("Found local vocabulary: %s", path)
            break

    return found_files


def load_global_vocabulary(
    tingbok_url: str | None = None,
    skip_cwd: bool = False,
    session: niquests.Session | None = None,
) -> dict[str, Concept]:
    """Load and merge vocabulary from all standard locations.

    The canonical package vocabulary is fetched from tingbok (lowest priority).
    Local overrides from /etc/inventory-md/, ~/.config/inventory-md/, and the
    current directory are merged on top (highest priority last).

    Args:
        tingbok_url: URL of a running tingbok service. If provided, the package
            vocabulary is fetched from tingbok. If unreachable, no package-level
            concepts are loaded.
        skip_cwd: If True, skip vocabulary files found in the current working
            directory (useful when local vocab is loaded separately).

    Returns:
        Merged vocabulary dictionary mapping concept IDs to Concept objects.
    """
    merged: dict[str, Concept] = {}

    # Fetch package vocabulary from tingbok (lowest priority)
    if tingbok_url:
        pkg_vocab = fetch_vocabulary_from_tingbok(tingbok_url, session=session)
        if pkg_vocab:
            logger.info("Loaded %d concepts from tingbok (%s)", len(pkg_vocab), tingbok_url)
            merged.update(pkg_vocab)

    for vocab_path in find_vocabulary_files():
        try:
            if skip_cwd and vocab_path.parent == Path.cwd():
                continue
            vocab = load_local_vocabulary(vocab_path)
            logger.info("Loaded %d concepts from %s", len(vocab), vocab_path)
            # Later files override earlier ones
            merged.update(vocab)
        except Exception as e:
            logger.warning("Failed to load vocabulary from %s: %s", vocab_path, e)

    logger.info("Total vocabulary: %d concepts", len(merged))
    return merged


def fetch_vocabulary_from_tingbok(url: str, session: niquests.Session | None = None) -> dict[str, Concept]:
    """Fetch the package vocabulary from a running tingbok service.

    Args:
        url:     Base URL of the tingbok service (e.g. "https://tingbok.plann.no").
        session: Optional niquests.Session to reuse (enables HTTP/2 multiplexing).

    Returns:
        Dictionary mapping concept IDs to Concept objects with source="tingbok",
        or an empty dict if the service is unreachable or returns an error.
    """
    import niquests

    getter = session.get if session is not None else niquests.get
    base = url.rstrip("/")
    endpoint = f"{base}/api/vocabulary"
    try:
        response = getter(endpoint, timeout=5.0)
        response.raise_for_status()
        data: dict[str, Any] = response.json()
    except Exception as e:
        raise TingbokUnavailableError(f"Failed to fetch vocabulary from tingbok {endpoint}: {e}") from e

    concepts: dict[str, Concept] = {}
    for concept_id, raw in data.items():
        raw = dict(raw)  # shallow copy — avoid mutating the parsed response dict
        # tingbok uses "altLabel" (SKOS convention); Concept.from_dict expects "altLabels"
        raw["altLabels"] = raw.pop("altLabel", {})
        raw["id"] = concept_id
        raw["source"] = "tingbok"
        # Convert source_uris from list[str] → dict[str, str] (source name → URI)
        raw_source_uris: list[str] = raw.pop("source_uris", [])
        try:
            concept = Concept.from_dict(raw)
            for u in raw_source_uris:
                src = _uri_to_source(u)
                if src and src not in concept.source_uris:
                    concept.source_uris[src] = u
            concepts[concept_id] = concept
        except Exception as e:
            logger.warning("Skipping malformed concept '%s' from tingbok: %s", concept_id, e)

    return concepts


# =============================================================================
# LANGUAGE FALLBACK SUPPORT
# =============================================================================

# Language code aliases — codes that refer to the same language.
# Unlike fallbacks (which cross language boundaries), aliases are alternate
# codes for the same language and should always be fetched together.
# Example: "nb" (Norwegian Bokmål) and "no" (Norwegian) are used
# interchangeably by different data sources (OFF uses "no", DBpedia uses "nb").
LANGUAGE_CODE_ALIASES: dict[str, list[str]] = {
    "nb": ["no"],
    "no": ["nb"],
}


def expand_languages_with_aliases(languages: list[str]) -> list[str]:
    """Expand a languages list to include alias codes.

    Returns a new list with alias languages appended (no duplicates).
    """
    expanded = list(languages)
    for lang in languages:
        for alias in LANGUAGE_CODE_ALIASES.get(lang, []):
            if alias not in expanded:
                expanded.append(alias)
    return expanded


# Default language fallback chains (can be overridden via config)
DEFAULT_LANGUAGE_FALLBACKS: dict[str, list[str]] = {
    # Scandinavian - mutually intelligible cluster
    "nb": ["no", "da", "nn", "sv"],
    "nn": ["no", "nb", "sv", "da"],
    "da": ["no", "nb", "sv", "nn"],
    "sv": ["no", "nb", "da", "nn"],
    "no": ["nb", "da", "nn", "sv"],
    # Germanic
    "de": ["de-AT", "de-CH", "nl"],
    "nl": ["de"],
    # Romance
    "es": ["pt", "it", "fr"],
    "pt": ["es", "it", "fr"],
    "fr": ["es", "it", "pt"],
    "it": ["es", "fr", "pt"],
    # Slavic
    "ru": ["uk", "be", "bg"],
    "uk": ["ru", "be", "pl"],
    "pl": ["cs", "sk"],
    "cs": ["sk", "pl"],
}


def get_fallback_chain(
    lang: str,
    fallbacks: dict[str, list[str]] | None = None,
    final_fallback: str = "en",
) -> list[str]:
    """Get the full fallback chain for a language.

    Args:
        lang: Primary language code.
        fallbacks: Language fallback configuration. If None, uses defaults.
        final_fallback: Final fallback language (usually "en").

    Returns:
        List of language codes to try, in order (including the primary).
    """
    if fallbacks is None:
        fallbacks = DEFAULT_LANGUAGE_FALLBACKS

    chain = [lang]
    if lang in fallbacks:
        chain.extend(fallbacks[lang])
    if final_fallback not in chain:
        chain.append(final_fallback)
    return chain


def apply_language_fallbacks(
    labels: dict[str, str],
    requested_languages: list[str],
    fallbacks: dict[str, list[str]] | None = None,
    final_fallback: str = "en",
) -> dict[str, str]:
    """Apply language fallbacks to fill in missing translations.

    For each requested language that doesn't have a label, tries fallback
    languages in order until one is found.

    Args:
        labels: Dict of available labels (lang -> label).
        requested_languages: Languages the user requested.
        fallbacks: Language fallback configuration.
        final_fallback: Final fallback language.

    Returns:
        Dict with labels for all requested languages (using fallbacks where needed).
    """
    result: dict[str, str] = {}

    for lang in requested_languages:
        if lang in labels:
            # Direct match
            result[lang] = labels[lang]
        else:
            # Try fallback chain
            chain = get_fallback_chain(lang, fallbacks, final_fallback)
            for fallback_lang in chain[1:]:  # Skip first (it's the same as lang)
                if fallback_lang in labels:
                    result[lang] = labels[fallback_lang]
                    logger.debug("Using %s fallback for %s", fallback_lang, lang)
                    break

    return result


@dataclass
class Concept:
    """A SKOS concept with labels and hierarchy."""

    id: str  # Unique identifier (path like "food/vegetables/potatoes")
    prefLabel: str  # Preferred display label (primary language)
    altLabels: dict[str, list[str]] = field(default_factory=dict)  # lang -> alternative labels
    broader: list[str] = field(default_factory=list)  # Parent concept IDs
    narrower: list[str] = field(default_factory=list)  # Child concept IDs
    source: str = "local"  # "local", "agrovoc", "dbpedia"
    uri: str | None = None  # Original SKOS URI (for external linking)
    labels: dict[str, str] = field(default_factory=dict)  # lang -> prefLabel translations
    description: str | None = None  # Short description (from Wikipedia/DBpedia)
    wikipediaUrl: str | None = None  # Link to Wikipedia article
    descriptions: dict[str, str] = field(default_factory=dict)  # lang -> description
    source_uris: dict[str, str] = field(default_factory=dict)  # source name -> URI
    excluded_sources: list[str] = field(default_factory=list)  # sources checked and rejected

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "id": self.id,
            "prefLabel": self.prefLabel,
            "altLabels": self.altLabels,
            "broader": self.broader,
            "narrower": self.narrower,
            "source": self.source,
        }
        if self.uri:
            result["uri"] = self.uri
        if self.labels:
            result["labels"] = self.labels
        if self.description:
            result["description"] = self.description
        if self.wikipediaUrl:
            result["wikipediaUrl"] = self.wikipediaUrl
        if self.descriptions:
            result["descriptions"] = self.descriptions
        if self.source_uris:
            result["source_uris"] = self.source_uris
        if self.excluded_sources:
            result["excluded_sources"] = self.excluded_sources
        return result

    def get_label(self, lang: str) -> str:
        """Get label for a specific language, falling back to prefLabel."""
        return self.labels.get(lang, self.prefLabel)

    def get_alt_labels(self, lang: str | None = None) -> list[str]:
        """Get altLabels for a specific language, or all if lang is None."""
        if lang is None:
            seen: set[str] = set()
            result: list[str] = []
            for labels in self.altLabels.values():
                for label in labels:
                    if label not in seen:
                        seen.add(label)
                        result.append(label)
            return result
        return list(self.altLabels.get(lang, []))

    def get_all_alt_labels_flat(self) -> list[str]:
        """All altLabels across all languages (deduplicated)."""
        return self.get_alt_labels(lang=None)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Concept:
        """Create from dictionary."""
        raw_alt = data.get("altLabels", {})
        if isinstance(raw_alt, list):
            alt_labels = {"en": raw_alt} if raw_alt else {}
        elif isinstance(raw_alt, dict):
            alt_labels = raw_alt
        else:
            alt_labels = {}
        return cls(
            id=data["id"],
            prefLabel=data.get("prefLabel", data["id"]),
            altLabels=alt_labels,
            broader=data.get("broader", []),
            narrower=data.get("narrower", []),
            source=data.get("source", "local"),
            uri=data.get("uri"),
            labels=data.get("labels", {}),
            description=data.get("description"),
            wikipediaUrl=data.get("wikipediaUrl"),
            descriptions=data.get("descriptions", {}),
            source_uris=data.get("source_uris", {}),
            excluded_sources=data.get("excluded_sources", []),
        )


@dataclass
class CategoryTree:
    """Hierarchical tree structure for category browser UI."""

    concepts: dict[str, Concept]  # All concepts by ID
    roots: list[str]  # Top-level concept IDs (no broader)
    label_index: dict[str, str]  # Maps lowercase labels to concept IDs

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "concepts": {k: v.to_dict() for k, v in self.concepts.items()},
            "roots": self.roots,
            "labelIndex": self.label_index,
        }


def load_local_vocabulary(path: Path, default_source: str = "local") -> dict[str, Concept]:
    """Load local vocabulary from YAML or JSON file.

    Args:
        path: Path to local-vocabulary.yaml or local-vocabulary.json
        default_source: Default source for concepts without an explicit source
            field. Use "tingbok" for the bundled package vocabulary.

    Returns:
        Dictionary mapping concept IDs to Concept objects.
    """
    if not path.exists():
        logger.debug("Local vocabulary file not found: %s", path)
        return {}

    try:
        if path.suffix in (".yaml", ".yml"):
            try:
                import yaml
            except ImportError as e:
                raise ImportError(
                    "PyYAML required for .yaml vocabulary files. Install with: pip install inventory-md[yaml]"
                ) from e
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        else:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
    except Exception as e:
        logger.warning("Failed to load vocabulary from %s: %s", path, e)
        return {}

    concepts_data = data.get("concepts", {})
    concepts = {}

    for concept_id, concept_data in concepts_data.items():
        if concept_data is None:
            concept_data = {}

        # Handle altLabel as string, list, or dict
        raw_alt = concept_data.get("altLabel", {})
        if isinstance(raw_alt, str):
            alt_labels = {"en": [raw_alt]}
        elif isinstance(raw_alt, list):
            alt_labels = {"en": raw_alt} if raw_alt else {}
        elif isinstance(raw_alt, dict):
            alt_labels = {k: ([v] if isinstance(v, str) else v) for k, v in raw_alt.items()}
        else:
            alt_labels = {}

        # Handle broader as string or list
        broader = concept_data.get("broader", [])
        if isinstance(broader, str):
            broader = [broader]

        # Handle narrower as string or list
        narrower = concept_data.get("narrower", [])
        if isinstance(narrower, str):
            narrower = [narrower]

        # Handle labels dict for translations
        labels = concept_data.get("labels", {})

        # The URI is just metadata for enrichment (translations, descriptions)
        # not an indication of where the concept definition comes from
        uri = concept_data.get("uri")
        source = concept_data.get("source", default_source)

        concepts[concept_id] = Concept(
            id=concept_id,
            prefLabel=concept_data.get("prefLabel", concept_id),
            altLabels=alt_labels,
            broader=broader,
            narrower=narrower,
            source=source,
            uri=uri,
            labels=labels,
            description=concept_data.get("description"),
        )

    return concepts


def merge_vocabularies(local: dict[str, Concept], base: dict[str, Concept]) -> dict[str, Concept]:
    """Merge local vocabulary with a base vocabulary.

    Local vocabulary takes precedence over base concepts.

    Args:
        local: Local vocabulary concepts (higher priority).
        base: Base vocabulary concepts (lower priority).

    Returns:
        Merged vocabulary with local concepts taking precedence.
    """
    merged = base.copy()
    merged.update(local)  # Local overrides base
    return merged


def build_label_index(concepts: dict[str, Concept]) -> dict[str, str]:
    """Build an index mapping all labels to concept IDs.

    Includes prefLabel and all altLabels, lowercased for case-insensitive lookup.

    Args:
        concepts: Dictionary of concepts.

    Returns:
        Dictionary mapping lowercase labels to concept IDs.
    """
    index = {}
    for concept_id, concept in concepts.items():
        # Add prefLabel
        index[concept.prefLabel.lower()] = concept_id
        # Add all altLabels
        for alt_label in concept.get_all_alt_labels_flat():
            index[alt_label.lower()] = concept_id
        # Also add the ID itself
        index[concept_id.lower()] = concept_id
    return index


def lookup_concept(label: str, vocabulary: dict[str, Concept]) -> Concept | None:
    """Look up a concept by label (prefLabel or altLabel).

    Args:
        label: Label to search for (case-insensitive).
        vocabulary: Dictionary of concepts.

    Returns:
        Concept if found, None otherwise.
    """
    label_lower = label.lower()

    # First, check if label matches a concept ID directly
    if label in vocabulary:
        return vocabulary[label]

    # Build label index and search
    index = build_label_index(vocabulary)
    concept_id = index.get(label_lower)

    if concept_id:
        return vocabulary.get(concept_id)

    return None


def get_broader_concepts(concept: Concept, vocabulary: dict[str, Concept]) -> list[Concept]:
    """Get all broader (parent) concepts.

    Args:
        concept: The concept to get parents for.
        vocabulary: Dictionary of all concepts.

    Returns:
        List of parent concepts.
    """
    parents = []
    for broader_id in concept.broader:
        if broader_id in vocabulary:
            parents.append(vocabulary[broader_id])
    return parents


def get_narrower_concepts(concept: Concept, vocabulary: dict[str, Concept]) -> list[Concept]:
    """Get all narrower (child) concepts.

    Args:
        concept: The concept to get children for.
        vocabulary: Dictionary of all concepts.

    Returns:
        List of child concepts.
    """
    children = []
    for narrower_id in concept.narrower:
        if narrower_id in vocabulary:
            children.append(vocabulary[narrower_id])
    return children


def _infer_hierarchy(concepts: dict[str, Concept]) -> None:
    """Infer hierarchy relationships from concept IDs with path separators.

    For concepts like "food/vegetables/potatoes", automatically adds:
    - broader: ["food/vegetables"] (if not already set from SKOS)
    - narrower: ["food/vegetables/potatoes"] to parent (always)

    Modifies concepts in place.

    Args:
        concepts: Dictionary of concepts to update.
    """
    # Sort by path depth to process parents before children
    concept_ids = sorted(concepts.keys(), key=lambda x: x.count("/"))

    for concept_id in concept_ids:
        concept = concepts[concept_id]

        # Infer parent from path
        if "/" in concept_id:
            parent_id = "/".join(concept_id.split("/")[:-1])
            if parent_id and parent_id in concepts:
                # Set broader if not already set from SKOS
                if not concept.broader:
                    concept.broader = [parent_id]
                # ALWAYS add this concept to parent's narrower list
                # This ensures the path hierarchy is preserved for navigation
                parent = concepts[parent_id]
                if concept_id not in parent.narrower:
                    parent.narrower.append(concept_id)


def build_category_tree(vocabulary: dict[str, Concept], infer_hierarchy: bool = True) -> CategoryTree:
    """Build a category tree structure for the UI.

    Args:
        vocabulary: Dictionary of concepts.
        infer_hierarchy: If True, infer parent/child relationships from paths.

    Returns:
        CategoryTree with roots and label index.
    """
    # Make a copy to avoid modifying the original
    concepts = {
        k: Concept(
            id=v.id,
            prefLabel=v.prefLabel,
            altLabels={lang: ls.copy() for lang, ls in v.altLabels.items()},
            broader=v.broader.copy(),
            narrower=v.narrower.copy(),
            source=v.source,
            uri=v.uri,
            labels=v.labels.copy() if v.labels else {},
            description=v.description,
            wikipediaUrl=v.wikipediaUrl,
            descriptions=v.descriptions.copy() if v.descriptions else {},
            source_uris=v.source_uris.copy() if v.source_uris else {},
        )
        for k, v in vocabulary.items()
    }

    if infer_hierarchy:
        _infer_hierarchy(concepts)

    # Find roots - concepts that should appear at the top level of the tree
    if VIRTUAL_ROOT_ID in concepts:
        # Virtual root defines explicit roots via its narrower list.
        # This is a whitelist: only concepts named in _root.narrower appear at
        # the top of the tree.  External/orphaned concepts are excluded.
        virtual_root = concepts[VIRTUAL_ROOT_ID]
        roots = [cid for cid in virtual_root.narrower if cid in concepts]
        del concepts[VIRTUAL_ROOT_ID]
    else:
        # Fallback: infer roots from concepts with no broader and no "/"
        roots = [cid for cid, c in concepts.items() if "/" not in cid and not c.broader]
        roots.sort(key=lambda x: concepts[x].prefLabel.lower())

    # Build label index
    label_index = build_label_index(concepts)

    return CategoryTree(
        concepts=concepts,
        roots=roots,
        label_index=label_index,
    )


def build_vocabulary_from_inventory(
    inventory_data: dict[str, Any],
    local_vocab: dict[str, Concept] | None = None,
) -> dict[str, Concept]:
    """Build vocabulary from categories used in inventory data.

    Scans all items in inventory for category: metadata and creates
    concepts for each unique category path found.

    Args:
        inventory_data: Parsed inventory JSON data.
        local_vocab: Optional local vocabulary to merge with.

    Returns:
        Dictionary of concepts from inventory categories.
    """
    concepts: dict[str, Concept] = {}

    # Start with local vocabulary if provided
    if local_vocab:
        concepts.update(local_vocab)

    # Add all category paths from inventory items
    for container in inventory_data.get("containers", []):
        for item in container.get("items", []):
            for category_path in item.get("metadata", {}).get("categories", []):
                _add_category_path(concepts, category_path)

    return concepts


def _add_category_path(concepts: dict[str, Concept], path: str) -> None:
    """Add a category path and all its parent paths to concepts.

    For "food/vegetables/potatoes", adds:
    - "food"
    - "food/vegetables"
    - "food/vegetables/potatoes"

    Args:
        concepts: Dictionary to add concepts to.
        path: Category path to add.
    """
    parts = path.split("/")

    for i in range(len(parts)):
        concept_id = "/".join(parts[: i + 1])
        if concept_id not in concepts:
            # Create a concept with default prefLabel from the last part
            concepts[concept_id] = Concept(
                id=concept_id,
                prefLabel=parts[i].replace("-", " ").replace("_", " ").title(),
                source="inventory",
            )


def save_vocabulary_json(
    vocabulary: dict[str, Concept],
    output_path: Path,
    category_mappings: dict[str, list[str]] | None = None,
) -> None:
    """Save vocabulary as JSON file for search.html.

    Args:
        vocabulary: Dictionary of concepts.
        output_path: Path to write vocabulary.json.
        category_mappings: Optional mapping from simple labels to expanded paths.
                          Used for SKOS hierarchy mode to enable search expansion.
    """
    tree = build_category_tree(vocabulary)
    output_data = tree.to_dict()

    # Include category mappings if provided (for SKOS hierarchy mode)
    if category_mappings:
        output_data["categoryMappings"] = category_mappings

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)


def count_items_per_category(inventory_data: dict[str, Any]) -> dict[str, int]:
    """Count items in each category (including items in child categories).

    Args:
        inventory_data: Parsed inventory JSON data.

    Returns:
        Dictionary mapping category paths to item counts.
    """
    counts: dict[str, int] = {}

    for container in inventory_data.get("containers", []):
        for item in container.get("items", []):
            categories = item.get("metadata", {}).get("categories", [])
            for category_path in categories:
                # Count the category itself
                counts[category_path] = counts.get(category_path, 0) + 1
                # Also count all parent categories
                parts = category_path.split("/")
                for i in range(len(parts) - 1):
                    parent_path = "/".join(parts[: i + 1])
                    counts[parent_path] = counts.get(parent_path, 0) + 1

    return counts


def resolve_categories_via_tingbok(
    unknown_labels: list[str],
    tingbok_url: str,
    lang: str = "en",
    sources: list[str] | None = None,
    session: niquests.Session | None = None,
) -> tuple[dict[str, Concept], dict[str, list[str]]]:
    """Resolve unknown category labels to hierarchy paths via tingbok.

    For each label, queries tingbok's ``/api/skos/hierarchy`` endpoint across
    multiple SKOS sources.  Stops at the first source that finds the concept.

    Args:
        unknown_labels: Category labels to resolve (e.g. ``["cumin", "bouillon"]``).
        tingbok_url:    Base URL of the tingbok service.
        lang:           BCP-47 language code for label matching.
        sources:        SKOS sources to try, in order.  Defaults to
                        ``["agrovoc", "dbpedia", "wikidata"]``.

    Returns:
        Tuple of:

        * *new_concepts* — ``dict[str, Concept]`` for all resolved path
          segments (including intermediate paths like ``"food/spices"``).
        * *category_mappings* — ``{label_lower: [path, ...]}`` for each
          successfully resolved label.
    """
    import niquests

    getter = session.get if session is not None else niquests.get
    if sources is None:
        sources = ["agrovoc", "dbpedia", "wikidata"]

    base = tingbok_url.rstrip("/")
    new_concepts: dict[str, Concept] = {}
    category_mappings: dict[str, list[str]] = {}

    for label in unknown_labels:
        for source in sources:
            try:
                response = getter(
                    f"{base}/api/skos/hierarchy",
                    params={"label": label, "lang": lang, "source": source},
                    timeout=5.0,
                )
                response.raise_for_status()
                data: dict = response.json()
            except Exception as exc:
                logger.debug("Category resolution failed for '%s' via %s: %s", label, source, exc)
                continue

            if data.get("found") and data.get("paths"):
                paths: list[str] = data["paths"]
                category_mappings[label.lower()] = paths
                for path in paths:
                    _add_category_path(new_concepts, path)
                break  # Found in this source — skip remaining sources

    return new_concepts, category_mappings


def enrich_categories_via_lookup(
    labels: list[str],
    tingbok_url: str,
    lang: str = "en",
    session: niquests.Session | None = None,
    cache_dir: Path | None = None,
) -> tuple[dict[str, Concept], dict[str, list[str]]]:
    """Enrich category concepts via ``GET /api/lookup/{label}``.

    Works for both bare labels (e.g. ``"cumin"``) and full paths (e.g.
    ``"food/spices/cumin"``).  All SKOS sources are queried in parallel by
    tingbok and the results merged, so the returned concepts carry translations,
    altLabels, descriptions, and source URIs from every available source.

    Args:
        labels:      Category IDs or bare labels to look up.
        tingbok_url: Base URL of the tingbok service.
        lang:        Preferred language for the lookup request.
        session:     Optional niquests.Session to reuse (enables HTTP/2 multiplexing).
        cache_dir:   Directory for the client-side lookup cache.  Successful
                     results are cached for :data:`_LOOKUP_CACHE_TTL_DAYS` days.
                     Pass ``None`` to disable (default).

    Returns:
        Tuple of:

        * *new_concepts* — enriched ``dict[str, Concept]`` for all resolved labels
          and their path segments (e.g. ``"food"``, ``"food/spices"``, ``"food/spices/cumin"``).
        * *category_mappings* — ``{label_lower: [path]}`` for bare labels that
          resolved to a different concept ID (used for search expansion).
    """
    import niquests

    getter = session.get if session is not None else niquests.get
    base = tingbok_url.rstrip("/")
    new_concepts: dict[str, Concept] = {}
    category_mappings: dict[str, list[str]] = {}

    total = len(labels)
    for i, label in enumerate(labels, 1):
        print(f"   [{i}/{total}] Looking up {label!r} ...", end=" ", flush=True)
        # Normalize the query label for SKOS sources: use the leaf node of a path,
        # replace hyphens with spaces, and strip OFF-style language tag prefixes
        # (e.g. "en:mashed-vegetables" → "mashed vegetables", "sk:džem" → "džem").
        query_label = label.split("/")[-1].replace("-", " ").replace("_", " ").strip()
        query_label = re.sub(r"^[a-z]{2,3}:", "", query_label)
        if not query_label:
            query_label = label

        data: dict | None = None
        if cache_dir is not None:
            cache_key = re.sub(r"[^\w.-]", "_", query_label)
            cache_path = cache_dir / f"lookup_{cache_key}.json"
            entry = _cache_read(cache_path, _LOOKUP_CACHE_TTL_DAYS)
            if entry is not None:
                data = entry.get("data")
                print("(cached)", end=" ", flush=True)

        if data is None:
            try:
                response = getter(f"{base}/api/lookup/{query_label}", params={"lang": lang}, timeout=120.0)
                if response.status_code == 404:
                    print("not found")
                    logger.debug("No lookup result for %r", label)
                    if cache_dir is not None:
                        _cache_write(cache_path, data=None)
                    continue
                response.raise_for_status()
                data = response.json()
                if cache_dir is not None:
                    _cache_write(cache_path, data=data)
            except Exception as exc:
                print(f"error: {exc}")
                logger.debug("Concept lookup failed for %r: %s", label, exc)
                continue

        concept_id: str = data.get("id", label)
        print(f"→ {concept_id}")

        # Convert VocabularyConcept format → Concept (same as fetch_vocabulary_from_tingbok)
        data["altLabels"] = data.pop("altLabel", {})
        data["id"] = concept_id
        data["source"] = "tingbok"
        raw_source_uris: list[str] = data.pop("source_uris", [])
        try:
            concept = Concept.from_dict(data)
        except Exception as exc:
            logger.warning("Skipping malformed lookup response for %r: %s", label, exc)
            continue
        for u in raw_source_uris:
            src = _uri_to_source(u)
            if src and src not in concept.source_uris:
                concept.source_uris[src] = u

        # Ensure all path segments exist (unenriched stubs for intermediates)
        _add_category_path(new_concepts, concept_id)
        # Overwrite the leaf with the fully enriched concept
        new_concepts[concept_id] = concept

        # Record mapping if a bare label resolved to a different (path-based) ID
        if label.lower() != concept_id.lower() and "/" not in label:
            category_mappings[label.lower()] = [concept_id]

    return new_concepts, category_mappings


def lookup_ean_via_tingbok(
    ean: str,
    tingbok_url: str,
    session: niquests.Session | None = None,
    cache_dir: Path | None = None,
) -> dict | None:
    """Look up a product by EAN via the tingbok service.

    Queries ``GET {tingbok_url}/api/ean/{ean}`` and returns the parsed JSON
    response dict (compatible with ``tingbok.models.ProductResponse``) or
    ``None`` on 404 or network failure.

    When *cache_dir* is provided, successful responses are cached for
    :data:`_EAN_CACHE_TTL_DAYS` days so repeat runs avoid unnecessary network
    calls.

    Args:
        ean:         EAN/UPC barcode string.
        tingbok_url: Base URL of the tingbok service.
        session:     Optional niquests.Session to reuse (enables HTTP/2 multiplexing).
        cache_dir:   Directory for the client-side EAN cache.  Pass ``None``
                     to disable caching (default).

    Returns:
        Product dict with keys ``ean``, ``name``, ``brand``, ``quantity``,
        ``categories``, ``image_url``, ``source`` — or ``None``.
    """
    import niquests

    if cache_dir is not None:
        cache_path = cache_dir / f"{ean}.json"
        entry = _cache_read(cache_path, _EAN_CACHE_TTL_DAYS)
        if entry is not None:
            return entry.get("data")  # None means 404 was cached

    getter = session.get if session is not None else niquests.get
    base = tingbok_url.rstrip("/")
    try:
        response = getter(f"{base}/api/ean/{ean}", timeout=5.0)
        if response.status_code == 404:
            if cache_dir is not None:
                _cache_write(cache_dir / f"{ean}.json", data=None)
            return None
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        logger.debug("EAN lookup failed for %s: %s", ean, exc)
        return None

    if cache_dir is not None:
        _cache_write(cache_dir / f"{ean}.json", data=data)
    return data


def ean_observation_needed(
    product: dict | None,
    categories: list[str],
    name: str | None,
    quantity: str | None,
    prices: list[dict] | None,
) -> bool:
    """Return True if a PUT is needed because *product* does not already reflect our observations.

    Compares the GET response from tingbok with what we would push.  A PUT is
    skipped when every piece of our inventory data is already present in the
    response — meaning a previous run already pushed it successfully.

    Args:
        product:    Result of :func:`lookup_ean_via_tingbok` (may be ``None``).
        categories: Category paths from the inventory.
        name:       Product name from the inventory (``None`` = unknown).
        quantity:   Weight/volume string (``None`` = unknown).
        prices:     Price observations to push (``None`` or empty = none).
    """
    if not categories and not name and not quantity and not prices:
        return False
    if product is None:
        return bool(categories or name or quantity or prices)

    existing_cats: list[str] = product.get("categories") or []
    if any(c not in existing_cats for c in categories):
        return True

    if quantity and quantity != product.get("quantity"):
        return True

    existing_prices: list[dict] = product.get("prices") or []

    def _price_key(p: dict) -> tuple:
        return (p.get("date"), p.get("currency"), p.get("price"), p.get("unit"))

    existing_keys = {_price_key(p) for p in existing_prices}
    if prices and any(_price_key(p) not in existing_keys for p in prices):
        return True

    return False


def report_ean_to_tingbok(
    ean: str,
    categories: list[str],
    name: str | None,
    tingbok_url: str,
    session: niquests.Session | None = None,
    quantity: str | None = None,
    prices: list[dict] | None = None,
    cache_dir: Path | None = None,
) -> None:
    """PUT inventory-sourced observations for *ean* to tingbok.

    Sends ``PUT {tingbok_url}/api/ean/{ean}`` with category, name, quantity
    and price data from the inventory.  Failures are silently ignored.

    When *cache_dir* is provided, the EAN GET cache is invalidated after a
    successful PUT so the next :func:`lookup_ean_via_tingbok` call fetches
    fresh data (which will reflect the PUT and suppress future pushes via
    :func:`ean_observation_needed`).

    Args:
        ean:         EAN/UPC barcode string.
        categories:  Category paths as classified in the inventory.
        name:        Clean product name from the inventory item text.
        tingbok_url: Base URL of the tingbok service.
        session:     Optional niquests.Session to reuse.
        quantity:    Weight or volume string (e.g. ``"140g"``).
        prices:      List of price dicts (``{currency, price, unit, date}``).
        cache_dir:   EAN cache directory.  On successful PUT the cache entry
                     for *ean* is deleted so the next GET is always fresh.
    """
    import niquests

    if not categories and not name and not quantity and not prices:
        return

    putter = session.put if session is not None else niquests.put
    base = tingbok_url.rstrip("/")
    payload: dict = {}
    if categories:
        payload["categories"] = categories
    if name:
        payload["name"] = name
    if quantity:
        payload["quantity"] = quantity
    if prices:
        payload["prices"] = prices
    try:
        response = putter(f"{base}/api/ean/{ean}", json=payload, timeout=5.0)
        response.raise_for_status()
        logger.debug("Reported EAN %s to tingbok: %s", ean, payload)
        if cache_dir is not None:
            cache_path = cache_dir / f"{ean}.json"
            if cache_path.exists():
                cache_path.unlink()
    except Exception as exc:
        logger.debug("Failed to report EAN %s to tingbok: %s", ean, exc)


def _uri_to_source(uri: str) -> str | None:
    """Determine the source name from a URI prefix."""
    if uri.startswith("off:"):
        return "off"
    if uri.startswith("gpt:"):
        return "gpt"
    if uri.startswith("http://aims.fao.org/"):
        return "agrovoc"
    if uri.startswith("http://dbpedia.org/") or uri.startswith("https://dbpedia.org/"):
        return "dbpedia"
    if uri.startswith("http://www.wikidata.org/") or uri.startswith("https://www.wikidata.org/"):
        return "wikidata"
    if uri.startswith("https://tingbok.plann.no/"):
        return "tingbok"
    return None
