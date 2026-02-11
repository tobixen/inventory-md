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

import importlib.resources
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from . import skos

    SKOSClient = skos.SKOSClient

logger = logging.getLogger(__name__)

VIRTUAL_ROOT_ID = "_root"


# =============================================================================
# VOCABULARY FILE DISCOVERY
# =============================================================================


def _get_package_data_dir() -> Path | None:
    """Get the package data directory containing the default vocabulary.

    Returns:
        Path to the package data directory, or None if not found.
    """
    try:
        # Python 3.9+ way to get package resources
        files = importlib.resources.files("inventory_md")
        data_dir = files / "data"
        # Check if it's a real path (installed package) or traversable
        if hasattr(data_dir, "_path"):
            return Path(data_dir._path)
        # For editable installs, try to resolve the path
        with importlib.resources.as_file(data_dir) as path:
            return path
    except (ModuleNotFoundError, FileNotFoundError, TypeError):
        # Fallback: try relative to this file (for development)
        dev_path = Path(__file__).parent / "data"
        if dev_path.exists():
            return dev_path
    return None


def find_vocabulary_files() -> list[Path]:
    """Find all vocabulary files, in merge order (lowest priority first).

    Searches in order:
    1. Package default vocabulary (shipped with inventory-md)
    2. /etc/inventory-md/vocabulary.yaml
    3. ~/.config/inventory-md/vocabulary.yaml
    4. ./vocabulary.yaml or ./local-vocabulary.yaml (highest priority)

    Returns:
        List of found vocabulary files. Files later in the list override earlier.
    """
    found_files: list[Path] = []
    vocab_filenames = ["vocabulary.yaml", "vocabulary.yml", "vocabulary.json"]
    local_vocab_filenames = ["local-vocabulary.yaml", "local-vocabulary.yml", "local-vocabulary.json", *vocab_filenames]

    # 1. Package default vocabulary (lowest priority)
    pkg_data = _get_package_data_dir()
    if pkg_data:
        for filename in vocab_filenames:
            path = pkg_data / filename
            if path.exists():
                found_files.append(path)
                logger.debug("Found package vocabulary: %s", path)
                break

    # 2. System-wide config (/etc/inventory-md/)
    etc_dir = Path("/etc/inventory-md")
    if etc_dir.exists():
        for filename in vocab_filenames:
            path = etc_dir / filename
            if path.exists():
                found_files.append(path)
                logger.debug("Found system vocabulary: %s", path)
                break

    # 3. User config (~/.config/inventory-md/)
    user_dir = Path.home() / ".config" / "inventory-md"
    if user_dir.exists():
        for filename in vocab_filenames:
            path = user_dir / filename
            if path.exists():
                found_files.append(path)
                logger.debug("Found user vocabulary: %s", path)
                break

    # 4. Current directory (highest priority) - also check local-vocabulary.*
    cwd = Path.cwd()
    for filename in local_vocab_filenames:
        path = cwd / filename
        if path.exists():
            found_files.append(path)
            logger.debug("Found local vocabulary: %s", path)
            break

    return found_files


def load_global_vocabulary() -> dict[str, Concept]:
    """Load and merge vocabulary from all standard locations.

    Loads vocabularies from package defaults, system, user, and local
    directories, merging them with proper precedence (later overrides earlier).

    Returns:
        Merged vocabulary dictionary mapping concept IDs to Concept objects.
    """
    merged: dict[str, Concept] = {}
    pkg_data = _get_package_data_dir()

    for vocab_path in find_vocabulary_files():
        try:
            is_package = pkg_data is not None and vocab_path.parent == pkg_data
            vocab = load_local_vocabulary(
                vocab_path,
                default_source="package" if is_package else "local",
            )
            logger.info("Loaded %d concepts from %s", len(vocab), vocab_path)
            # Later files override earlier ones
            merged.update(vocab)
        except Exception as e:
            logger.warning("Failed to load vocabulary from %s: %s", vocab_path, e)

    logger.info("Total vocabulary: %d concepts from %d files", len(merged), len(find_vocabulary_files()))
    return merged


# =============================================================================
# LANGUAGE FALLBACK SUPPORT
# =============================================================================

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
    altLabels: list[str] = field(default_factory=list)  # Alternative labels/synonyms
    broader: list[str] = field(default_factory=list)  # Parent concept IDs
    narrower: list[str] = field(default_factory=list)  # Child concept IDs
    source: str = "local"  # "local", "agrovoc", "dbpedia"
    uri: str | None = None  # Original SKOS URI (for external linking)
    labels: dict[str, str] = field(default_factory=dict)  # lang -> prefLabel translations
    description: str | None = None  # Short description (from Wikipedia/DBpedia)
    wikipediaUrl: str | None = None  # Link to Wikipedia article
    descriptions: dict[str, str] = field(default_factory=dict)  # lang -> description
    source_uris: dict[str, str] = field(default_factory=dict)  # source name -> URI

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
        return result

    def get_label(self, lang: str) -> str:
        """Get label for a specific language, falling back to prefLabel."""
        return self.labels.get(lang, self.prefLabel)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Concept:
        """Create from dictionary."""
        return cls(
            id=data["id"],
            prefLabel=data.get("prefLabel", data["id"]),
            altLabels=data.get("altLabels", []),
            broader=data.get("broader", []),
            narrower=data.get("narrower", []),
            source=data.get("source", "local"),
            uri=data.get("uri"),
            labels=data.get("labels", {}),
            description=data.get("description"),
            wikipediaUrl=data.get("wikipediaUrl"),
            descriptions=data.get("descriptions", {}),
            source_uris=data.get("source_uris", {}),
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
            field. Use "package" for the bundled package vocabulary.

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

        # Handle altLabel as string or list
        alt_labels = concept_data.get("altLabel", [])
        if isinstance(alt_labels, str):
            alt_labels = [alt_labels]

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


def merge_vocabularies(local: dict[str, Concept], skos_concepts: dict[str, Concept]) -> dict[str, Concept]:
    """Merge local vocabulary with SKOS concepts.

    Local vocabulary takes precedence over SKOS concepts.

    Args:
        local: Local vocabulary concepts.
        skos_concepts: SKOS concepts from cache.

    Returns:
        Merged vocabulary with local concepts taking precedence.
    """
    merged = skos_concepts.copy()
    merged.update(local)  # Local overrides SKOS
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
        for alt_label in concept.altLabels:
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
            altLabels=v.altLabels.copy(),
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
        # Virtual root defines explicit roots via its narrower list
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
    use_skos: bool = False,
    lang: str = "en",
    languages: list[str] | None = None,
) -> dict[str, Concept]:
    """Build vocabulary from categories used in inventory data.

    Scans all items in inventory for category: metadata and creates
    concepts for each unique category path found.

    Args:
        inventory_data: Parsed inventory JSON data.
        local_vocab: Optional local vocabulary to merge with.
        use_skos: If True, look up categories in SKOS vocabularies.
        lang: Primary language code for SKOS lookups (used for matching).
        languages: List of language codes to fetch labels for (e.g., ["en", "nb", "de"]).
                   If None, only the primary language is used.

    Returns:
        Dictionary of concepts from inventory categories.
    """
    concepts: dict[str, Concept] = {}

    # Start with local vocabulary if provided
    if local_vocab:
        concepts.update(local_vocab)

    # Collect all unique category labels
    all_categories: set[str] = set()
    for container in inventory_data.get("containers", []):
        for item in container.get("items", []):
            categories = item.get("metadata", {}).get("categories", [])
            for category_path in categories:
                all_categories.add(category_path)

    # If SKOS enabled, enrich with SKOS lookups
    if use_skos and all_categories:
        concepts = _enrich_with_skos(all_categories, concepts, lang, languages)
    else:
        # Just add category paths without SKOS
        for category_path in all_categories:
            _add_category_path(concepts, category_path)

    return concepts


# Terms that are clearly food/agriculture related - use AGROVOC for these
_FOOD_TERMS = {
    "food",
    "vegetable",
    "vegetables",
    "fruit",
    "fruits",
    "meat",
    "fish",
    "grain",
    "grains",
    "cereal",
    "cereals",
    "dairy",
    "spice",
    "spices",
    "herb",
    "herbs",
    "potato",
    "potatoes",
    "carrot",
    "carrots",
    "onion",
    "onions",
    "tomato",
    "tomatoes",
    "apple",
    "apples",
    "banana",
    "bananas",
    "rice",
    "wheat",
    "corn",
    "maize",
    "bean",
    "beans",
    "pea",
    "peas",
    "lentil",
    "lentils",
    "nut",
    "nuts",
    "seed",
    "seeds",
    "oil",
    "oils",
    "sugar",
    "salt",
    "pepper",
    "garlic",
    "ginger",
    "cinnamon",
    "flour",
    "bread",
    "pasta",
    "noodle",
    "noodles",
    "cheese",
    "milk",
    "butter",
    "egg",
    "eggs",
    "chicken",
    "beef",
    "pork",
    "lamb",
    "salmon",
    "tuna",
    "shrimp",
    "crab",
    "lobster",
    "oyster",
    "mussel",
    "clam",
    "squid",
    "wine",
    "beer",
    "coffee",
    "tea",
    "juice",
    "water",
    "soda",
    "alcohol",
    "honey",
    "jam",
    "jelly",
    "syrup",
    "sauce",
    "vinegar",
    "mustard",
    "ketchup",
    "mayonnaise",
    "olive",
    "olives",
    "pickle",
    "pickles",
    "canned",
    "frozen",
    "dried",
    "fresh",
    "organic",
    "preserves",
}


def _normalize_to_singular(word: str) -> str:
    """Convert a plural word to singular form.

    Common English plural rules applied in reverse:
    - words ending in 'ies' -> 'y' (berries -> berry)
    - words ending in 'es' after s/x/z/ch/sh/o -> remove 'es' (boxes -> box)
    - words ending in 's' -> remove 's' (books -> book)

    Args:
        word: Word to convert to singular.

    Returns:
        Singular form of the word.
    """
    w = word.lower()

    # Skip very short words
    if len(w) <= 2:
        return word

    # Exceptions - words that shouldn't be modified
    exceptions = {
        "series",
        "species",
        "shoes",
        "canoes",
        "tiptoes",
        "glasses",
        "clothes",
        "scissors",
        "trousers",
        "pants",
        "shorts",
        "news",
        "mathematics",
        "physics",
        "economics",
        "politics",
        "athletics",
    }
    if w in exceptions:
        return word

    # Words ending in 'ies' -> 'y' (berries -> berry)
    if w.endswith("ies") and len(w) > 4:
        return word[:-3] + "y"

    # Words ending in 'es' after s/x/z/ch/sh -> remove 'es'
    if w.endswith("es") and len(w) > 3:
        stem = w[:-2]
        if stem.endswith(("s", "x", "z", "ch", "sh")):
            return word[:-2]
        # Words ending in 'oes' -> 'o' (potatoes -> potato)
        if w.endswith("oes") and len(w) > 4:
            return word[:-2]

    # Regular plurals ending in 's' (but not 'ss', 'us', 'is')
    if w.endswith("s") and not w.endswith(("ss", "us", "is", "ous", "ness", "ics")):
        return word[:-1]

    return word


def _is_singular_plural_variant(a: str, b: str) -> bool:
    """Check if two strings are singular/plural variants of each other."""
    a_singular = _normalize_to_singular(a.lower())
    b_singular = _normalize_to_singular(b.lower())
    return a_singular == b_singular


def _resolve_broader_chain(
    concept_id: str,
    local_vocab: dict[str, Concept],
    _visited: set[str] | None = None,
) -> str:
    """Resolve a local vocab concept ID to its full hierarchical path.

    Walks up the broader chain so that e.g. ``sandpaper`` with
    ``broader: consumables`` resolves to ``consumables/sandpaper``.
    """
    if _visited is None:
        _visited = set()
    if concept_id in _visited:
        return concept_id  # cycle protection
    _visited.add(concept_id)

    concept = local_vocab.get(concept_id)
    if not concept or not concept.broader:
        return concept_id  # root or not in vocab

    parent_ref = concept.broader[0]

    # Already a path that embeds the parent (e.g. "food/vegetables" broader "food")
    # But the parent itself might need resolution (e.g. "automotive/accessories"
    # where "automotive" has broader "transport" → "transport/automotive/accessories")
    if concept_id.startswith(parent_ref + "/"):
        resolved_parent = _resolve_broader_chain(parent_ref, local_vocab, _visited)
        if resolved_parent != parent_ref:
            suffix = concept_id[len(parent_ref) :]
            return resolved_parent + suffix
        return concept_id

    # Singular/plural merge: concept collapses into its parent
    parent_leaf = parent_ref.split("/")[-1]
    if _is_singular_plural_variant(concept_id, parent_leaf):
        return _resolve_broader_chain(parent_ref, local_vocab, _visited)

    # Resolve parent first, then build full path
    resolved_parent = _resolve_broader_chain(parent_ref, local_vocab, _visited)
    return f"{resolved_parent}/{concept_id}"


def _enrich_with_skos(
    categories: set[str],
    existing_concepts: dict[str, Concept],
    lang: str,
    languages: list[str] | None = None,
) -> dict[str, Concept]:
    """Enrich categories with SKOS lookups.

    Args:
        categories: Set of category paths to look up.
        existing_concepts: Existing concepts (from local vocabulary).
        lang: Primary language code for SKOS lookups (used for matching).
        languages: List of language codes to fetch labels for.

    Returns:
        Dictionary of concepts enriched with SKOS data.
    """
    try:
        from . import skos
    except ImportError:
        logger.warning("SKOS module not available, falling back to local vocabulary")
        concepts = existing_concepts.copy()
        for cat in categories:
            _add_category_path(concepts, cat)
        return concepts

    concepts = existing_concepts.copy()
    # Enable Oxigraph for label fetches - loading takes ~35s but provides
    # better language coverage (e.g., Norwegian labels not in remote API)
    # The loading time is acceptable when fetching translations for many concepts.
    client = skos.SKOSClient(use_oxigraph=True)

    # Extract ALL labels to look up (all path components, not just leaves)
    # This ensures intermediate path components like "food" in "food/vegetables"
    # also get SKOS lookups
    labels_to_lookup: dict[str, set[str]] = {}  # label -> set of normalized paths
    all_path_components: set[str] = set()  # all intermediate path components

    def normalize_path(path: str) -> str:
        """Normalize a category path: singular form, lowercase."""
        parts = path.split("/")
        normalized_parts = [_normalize_to_singular(p.lower()) for p in parts]
        return "/".join(normalized_parts)

    for cat_path in categories:
        parts = cat_path.split("/")
        # Build all intermediate paths, normalized
        for i in range(len(parts)):
            original_component_path = "/".join(parts[: i + 1])
            normalized_component_path = normalize_path(original_component_path)
            all_path_components.add(normalized_component_path)
            # Get the label for this component
            label = parts[i]
            # Normalize: replace - and _ with space for lookup
            lookup_label = label.replace("-", " ").replace("_", " ")
            # Normalize plural to singular for consistent lookups
            lookup_label = _normalize_to_singular(lookup_label)
            if lookup_label not in labels_to_lookup:
                labels_to_lookup[lookup_label] = set()
            labels_to_lookup[lookup_label].add(normalized_component_path)

    logger.info("Looking up %d unique labels in SKOS...", len(labels_to_lookup))
    skos_found = 0
    skos_not_found = 0

    # Phase 1: Look up all concepts and build the vocabulary
    for label, paths in labels_to_lookup.items():
        # Skip if already in vocabulary with a SKOS source (not "inventory")
        # We still want to look up labels that only exist from path expansion
        existing_with_skos = any(
            c.prefLabel.lower() == label.lower() and c.source != "inventory" for c in concepts.values()
        )
        if existing_with_skos:
            continue

        # Try SKOS lookup - choose source based on term type
        # AGROVOC is agricultural vocabulary, so use DBpedia first for non-food terms
        is_food_term = label.lower() in _FOOD_TERMS
        primary_source = "agrovoc" if is_food_term else "dbpedia"
        fallback_source = "dbpedia" if is_food_term else "agrovoc"

        concept_data = client.lookup_concept(label, lang=lang, source=primary_source)

        # Check if AGROVOC returned an inappropriate agricultural result
        # (e.g., "bedding" = "litter for animals" is not household bedding)
        if concept_data and concept_data.get("source") == "agrovoc":
            pref = concept_data.get("prefLabel", "").lower()
            # If AGROVOC's prefLabel is very different from search term, try DBpedia
            if pref and label.lower() not in pref and pref not in label.lower():
                logger.debug(
                    "AGROVOC mismatch: searched '%s', got '%s' - trying DBpedia", label, concept_data.get("prefLabel")
                )
                alt_data = client.lookup_concept(label, lang=lang, source="dbpedia")
                if alt_data and alt_data.get("uri"):
                    # Check if DBpedia's label is closer match
                    dbpedia_pref = alt_data.get("prefLabel", "").lower()
                    if label.lower() in dbpedia_pref or dbpedia_pref in label.lower():
                        concept_data = alt_data

        if not concept_data or not concept_data.get("uri"):
            # Try fallback source
            concept_data = client.lookup_concept(label, lang=lang, source=fallback_source)

        if concept_data and concept_data.get("uri"):
            skos_found += 1
            # Create concept from SKOS data
            pref_label = concept_data.get("prefLabel", label)
            broader_data = concept_data.get("broader", [])

            # Build broader list from SKOS hierarchy
            # Filter out irrelevant DBpedia categories (Wikipedia meta categories)
            broader_ids = []
            for b in broader_data[:5]:  # Check first 5, keep up to 3 useful ones
                broader_label = b.get("label", "")
                if broader_label and not skos._is_irrelevant_dbpedia_category(broader_label):
                    broader_ids.append(broader_label.lower().replace(" ", "_"))
                    if len(broader_ids) >= 3:
                        break

            # Add the concept for each path that uses this label (without translations yet)
            for cat_path in paths:
                # Create or update concept (overwrite "inventory" source with SKOS)
                existing = concepts.get(cat_path)
                if existing is None or existing.source == "inventory":
                    concepts[cat_path] = Concept(
                        id=cat_path,
                        prefLabel=pref_label,
                        altLabels=[],
                        broader=broader_ids[:1] if broader_ids else [],  # Just first broader
                        narrower=[],
                        source=concept_data.get("source", "skos"),
                        uri=concept_data.get("uri"),
                        description=concept_data.get("description"),
                        wikipediaUrl=concept_data.get("wikipediaUrl"),
                    )

                # Also add broader concepts (overwrite "inventory" source)
                for i, broader_id in enumerate(broader_ids):
                    existing_broader = concepts.get(broader_id)
                    if existing_broader is None or existing_broader.source == "inventory":
                        # Get broader URI from SKOS data if available
                        broader_uri = None
                        if i < len(broader_data):
                            broader_uri = broader_data[i].get("uri")
                        concepts[broader_id] = Concept(
                            id=broader_id,
                            prefLabel=broader_id.replace("_", " ").title(),
                            source="skos",
                            uri=broader_uri,
                        )
        else:
            skos_not_found += 1
            # Fall back to adding path without SKOS enrichment
            for cat_path in paths:
                _add_category_path(concepts, cat_path)

    logger.info("SKOS lookup complete: %d found, %d not found", skos_found, skos_not_found)

    # Phase 2: Batch fetch translations if multiple languages requested
    if languages and len(languages) > 1:
        other_langs = [lng for lng in languages if lng != lang]
        if other_langs:
            # Collect all URIs that need translations
            uris_to_fetch: list[tuple[str, str]] = []
            for concept in concepts.values():
                if concept.uri and concept.source in ("agrovoc", "dbpedia"):
                    uris_to_fetch.append((concept.uri, concept.source))

            if uris_to_fetch:
                logger.info(
                    "Fetching translations for %d concepts in %d languages...", len(uris_to_fetch), len(other_langs)
                )

                # Batch fetch all translations
                all_translations = client.get_batch_labels(uris_to_fetch, other_langs)

                # Apply translations to concepts
                for concept in concepts.values():
                    if concept.uri and concept.uri in all_translations:
                        labels = all_translations[concept.uri].copy()
                        labels[lang] = concept.prefLabel  # Add primary language
                        concept.labels = labels

                logger.info("Translations fetched successfully")

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


# Mapping from AGROVOC top-level concepts to user-friendly labels
# These are the roots that users expect to see in the UI
AGROVOC_ROOT_MAPPING = {
    # Products hierarchy → Food
    "products": "food",
    "plant products": "food",
    "animal products": "food",
    "processed products": "food",
    "aquatic products": "food",
    # Keep others as-is but with better labels
    "equipment": "tools",
    "materials": "materials",
    "chemicals": "chemicals",
    "organisms": "organisms",  # Live animals/plants - not food
}


def build_skos_hierarchy_paths(
    concept_label: str,
    client: SKOSClient,  # from .skos module
    lang: str = "en",
) -> tuple[list[str], bool, dict[str, str], list[str]]:
    """Build all hierarchy paths for a concept from SKOS.

    Given a concept label like "potatoes", queries AGROVOC to find
    all paths from root to the concept:
    - food/vegetables/root_vegetables/potatoes
    - food/plant_products/vegetables/potatoes

    Args:
        concept_label: The concept label to look up (e.g., "potatoes").
        client: SKOSClient instance with Oxigraph enabled.
        lang: Language code for labels.

    Returns:
        Tuple of (list of hierarchy paths, bool indicating if SKOS was found,
        dict mapping concept_id to AGROVOC URI,
        list of raw paths before root mapping).
    """
    store = client._get_oxigraph_store()
    if store is None or not store.is_loaded:
        logger.warning("Oxigraph not available for hierarchy building")
        return [concept_label.lower().replace(" ", "_")], False, {}, []

    # First, find the concept URI
    uri = _find_agrovoc_uri(concept_label, store)
    if not uri:
        logger.debug("No AGROVOC URI found for %s", concept_label)
        return [concept_label.lower().replace(" ", "_")], False, {}, []

    # Build all paths from this concept up to roots
    paths, uri_map, raw_paths = _build_paths_to_root(uri, store, lang)

    if not paths:
        # Fall back to just the concept label
        return [concept_label.lower().replace(" ", "_")], False, {}, []

    return paths, True, uri_map, raw_paths


def _find_agrovoc_uri(label: str, store) -> str | None:
    """Find AGROVOC URI for a label using Oxigraph.

    Tries multiple variations: exact match, plural form, singular form.

    Args:
        label: The label to look up.
        store: Oxigraph store instance.

    Returns:
        AGROVOC URI or None if not found.
    """
    # Generate variations to try (original, plural, singular)
    base = label.lower()
    variations = [base]

    # Add plural variation
    if not base.endswith("s"):
        if base.endswith("y") and len(base) > 2 and base[-2] not in "aeiou":
            variations.append(base[:-1] + "ies")  # berry -> berries
        elif base.endswith(("s", "x", "z", "ch", "sh", "o")):
            variations.append(base + "es")  # box -> boxes
        else:
            variations.append(base + "s")  # book -> books

    # Add singular variation
    if base.endswith("ies") and len(base) > 4:
        variations.append(base[:-3] + "y")  # berries -> berry
    elif base.endswith("es") and len(base) > 3:
        stem = base[:-2]
        if stem.endswith(("s", "x", "z", "ch", "sh")):
            variations.append(stem)  # boxes -> box
        elif base.endswith("oes"):
            variations.append(base[:-2])  # potatoes -> potato
    elif base.endswith("s") and not base.endswith(("ss", "us", "is")):
        variations.append(base[:-1])  # books -> book

    # Build all case variations to try (lowercase, Capitalized, UPPERCASE)
    all_variations = []
    for var in variations:
        all_variations.extend([var, var.capitalize(), var.upper(), var.lower()])
    all_variations = list(dict.fromkeys(all_variations))  # Remove duplicates, preserve order

    # Try exact match first (fast - uses index)
    for var in all_variations:
        query = f'''
        PREFIX skosxl: <http://www.w3.org/2008/05/skos-xl#>
        SELECT ?concept WHERE {{
            ?concept skosxl:prefLabel/skosxl:literalForm "{var}"@en .
        }} LIMIT 1
        '''
        results = list(store.query(query))
        if results:
            return results[0]["concept"]["value"]

    # Try altLabel exact match
    for var in all_variations:
        query = f'''
        PREFIX skosxl: <http://www.w3.org/2008/05/skos-xl#>
        SELECT ?concept WHERE {{
            ?concept skosxl:altLabel/skosxl:literalForm "{var}"@en .
        }} LIMIT 1
        '''
        results = list(store.query(query))
        if results:
            return results[0]["concept"]["value"]

    return None


def _get_agrovoc_label(uri: str, store, lang: str = "en") -> str:
    """Get the prefLabel for an AGROVOC concept URI.

    Args:
        uri: AGROVOC concept URI.
        store: Oxigraph store instance.
        lang: Language code.

    Returns:
        Label string, or last part of URI if not found.
    """
    query = f'''
    PREFIX skosxl: <http://www.w3.org/2008/05/skos-xl#>
    SELECT ?labelText WHERE {{
        <{uri}> skosxl:prefLabel ?labelRes .
        ?labelRes skosxl:literalForm ?labelText .
        FILTER(LANG(?labelText) = "{lang}")
    }} LIMIT 1
    '''

    results = list(store.query(query))
    if results:
        return results[0]["labelText"]["value"]

    # Fall back to English
    if lang != "en":
        query = f"""
        PREFIX skosxl: <http://www.w3.org/2008/05/skos-xl#>
        SELECT ?labelText WHERE {{
            <{uri}> skosxl:prefLabel ?labelRes .
            ?labelRes skosxl:literalForm ?labelText .
            FILTER(LANG(?labelText) = "en")
        }} LIMIT 1
        """

        results = list(store.query(query))
        if results:
            return results[0]["labelText"]["value"]

    # Fall back to URI fragment
    return uri.split("/")[-1]


def _get_all_labels(
    uri: str,
    store,
    languages: list[str],
    use_fallbacks: bool = True,
    fallbacks: dict[str, list[str]] | None = None,
) -> dict[str, str]:
    """Get prefLabels for an AGROVOC concept URI in multiple languages.

    Args:
        uri: AGROVOC concept URI.
        store: Oxigraph store instance.
        languages: List of language codes to fetch.
        use_fallbacks: If True, use language fallbacks for missing translations.
        fallbacks: Custom fallback configuration (uses defaults if None).

    Returns:
        Dict mapping language code to label string.
    """
    # Build the set of all languages to query (requested + potential fallbacks)
    langs_to_query = set(languages)
    if use_fallbacks:
        for lang in languages:
            chain = get_fallback_chain(lang, fallbacks)
            langs_to_query.update(chain)

    # Fetch all available labels in one query for efficiency
    all_labels: dict[str, str] = {}
    for lang in langs_to_query:
        query = f'''
        PREFIX skosxl: <http://www.w3.org/2008/05/skos-xl#>
        SELECT ?labelText WHERE {{
            <{uri}> skosxl:prefLabel ?labelRes .
            ?labelRes skosxl:literalForm ?labelText .
            FILTER(LANG(?labelText) = "{lang}")
        }} LIMIT 1
        '''
        results = list(store.query(query))
        if results:
            all_labels[lang] = results[0]["labelText"]["value"]

    # Apply fallbacks if enabled
    if use_fallbacks:
        return apply_language_fallbacks(all_labels, languages, fallbacks)
    else:
        # Just return labels for requested languages
        return {lang: all_labels[lang] for lang in languages if lang in all_labels}


def _get_broader_concepts(uri: str, store) -> list[str]:
    """Get all broader concept URIs for a concept.

    Args:
        uri: AGROVOC concept URI.
        store: Oxigraph store instance.

    Returns:
        List of broader concept URIs.
    """
    query = f"""
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
    SELECT ?broader WHERE {{
        <{uri}> skos:broader ?broader .
    }}
    """

    results = list(store.query(query))
    return [r["broader"]["value"] for r in results]


def _build_paths_to_root(
    uri: str,
    store,
    lang: str = "en",
    visited: set | None = None,
    current_path: list | None = None,
    current_path_uris: list | None = None,
    uri_map: dict | None = None,
    raw_paths: list | None = None,
) -> tuple[list[str], dict[str, str], list[str]]:
    """Recursively build all paths from a concept to root(s).

    Args:
        uri: Starting concept URI.
        store: Oxigraph store instance.
        lang: Language code for labels.
        visited: Set of visited URIs to avoid cycles.
        current_path: Current path being built (concept labels).
        current_path_uris: URIs corresponding to each path component.
        uri_map: Dict mapping concept_id to URI for translation fetching.
        raw_paths: Accumulator for pre-mapping paths (before root mapping).

    Returns:
        Tuple of (list of complete paths, dict of concept_id -> URI,
        list of raw paths before root mapping).
    """
    if visited is None:
        visited = set()
    if current_path is None:
        current_path = []
    if current_path_uris is None:
        current_path_uris = []
    if uri_map is None:
        uri_map = {}
    if raw_paths is None:
        raw_paths = []

    if uri in visited:
        return [], uri_map, raw_paths
    visited.add(uri)

    # Get label for current concept
    label = _get_agrovoc_label(uri, store, lang)
    label_normalized = label.lower().replace(" ", "_").replace("-", "_")

    # Add to path (prepend since we're going up the hierarchy)
    new_path = [label_normalized] + current_path
    new_path_uris = [uri] + current_path_uris

    # Get broader concepts
    broader_uris = _get_broader_concepts(uri, store)

    if not broader_uris:
        # Save raw path before mapping
        raw_paths.append("/".join(new_path))

        # We've reached a root - apply mapping if available
        root_label = label.lower()
        root_was_mapped = root_label in AGROVOC_ROOT_MAPPING
        if root_was_mapped:
            new_path[0] = AGROVOC_ROOT_MAPPING[root_label]
        # Return the complete path
        full_path = "/".join(new_path)
        # Track URI for each concept in the path (using matching URIs)
        # Skip mapped roots (index 0) — synthetic concepts that don't
        # correspond to any single AGROVOC concept
        start_idx = 1 if root_was_mapped else 0
        for i in range(start_idx, len(new_path)):
            concept_id = "/".join(new_path[: i + 1])
            if concept_id not in uri_map:
                uri_map[concept_id] = new_path_uris[i]
        return [full_path], uri_map, raw_paths

    # Continue up the hierarchy for each broader concept
    all_paths = []
    for broader_uri in broader_uris:
        paths, uri_map, raw_paths = _build_paths_to_root(
            broader_uri, store, lang, visited.copy(), new_path, new_path_uris, uri_map, raw_paths
        )
        all_paths.extend(paths)

    return all_paths, uri_map, raw_paths


def expand_category_to_skos_paths(
    category_label: str,
    use_oxigraph: bool = True,
    lang: str = "en",
) -> list[str]:
    """Expand a simple category label to full SKOS hierarchy paths.

    This is the main entry point for the SKOS-based category system.
    Given a label like "potatoes", it returns all valid hierarchy paths.

    Example:
        >>> expand_category_to_skos_paths("potatoes")
        ['food/vegetables/root_vegetables/potatoes', 'food/plant_products/potatoes']

    Args:
        category_label: Simple category label (e.g., "potatoes", "hammer").
        use_oxigraph: Whether to use local AGROVOC database.
        lang: Language code for labels.

    Returns:
        List of hierarchy paths. Falls back to [category_label] if not found.
    """
    try:
        from . import skos
    except ImportError:
        logger.warning("SKOS module not available")
        return [category_label.lower().replace(" ", "_")]

    client = skos.SKOSClient(use_oxigraph=use_oxigraph)
    paths, _found, _uri_map, _raw = build_skos_hierarchy_paths(category_label, client, lang)
    return paths


# Words that are variations of each other and should be collapsed in paths
_SIMILAR_PATH_COMPONENTS: dict[str, str] = {
    "foods": "food",
    "beverages": "beverage",
    "drinks": "beverage",
    "meats": "meat",
    "vegetables": "vegetable",
    "fruits": "fruit",
}


def _normalize_hierarchy_path(path: str) -> str:
    """Normalize a hierarchy path by collapsing consecutive similar components.

    For example:
        "food/foods/prepared_foods" -> "food/prepared_foods"
        "food/food/condiments" -> "food/condiments"

    Args:
        path: Hierarchy path string with "/" separators.

    Returns:
        Normalized path with consecutive similar components collapsed.
    """
    parts = path.split("/")
    if len(parts) <= 1:
        return path

    result = [parts[0]]
    for part in parts[1:]:
        prev = result[-1]
        # Normalize both to base form for comparison
        prev_base = _SIMILAR_PATH_COMPONENTS.get(prev, prev)
        curr_base = _SIMILAR_PATH_COMPONENTS.get(part, part)

        # Skip if current is essentially the same as previous
        if prev_base == curr_base:
            continue
        # Skip if one starts with the other (e.g., "food" and "foods")
        if prev.startswith(curr_base) or curr_base.startswith(prev):
            continue

        result.append(part)

    return "/".join(result)


# Override labels for well-known concept IDs (avoids .title() mangling)
_CONCEPT_LABEL_OVERRIDES: dict[str, str] = {
    "category_by_source": "Category by Source",
    "category_by_source/off": "OpenFoodFacts",
    "category_by_source/agrovoc": "AGROVOC",
    "category_by_source/dbpedia": "DBpedia",
    "category_by_source/wikidata": "Wikidata",
    "category_by_source/local": "Local",
}

# Norwegian (nb) label overrides for synthetic concepts with no external source
_CONCEPT_LABEL_OVERRIDES_NB: dict[str, str] = {
    "category_by_source": "Kategori etter kilde",
    "category_by_source/off": "OpenFoodFacts",
    "category_by_source/agrovoc": "AGROVOC",
    "category_by_source/dbpedia": "DBpedia",
    "category_by_source/wikidata": "Wikidata",
    "category_by_source/local": "Lokal",
}


def _add_paths_to_concepts(
    paths: list[str],
    concepts: dict[str, Concept],
    source: str,
) -> None:
    """Add all path components from a list of paths to the concepts dict.

    Args:
        paths: List of hierarchy paths like "food/vegetables/potatoes".
        concepts: Concepts dict to update.
        source: Source string for new concepts (e.g., "off", "agrovoc").
    """
    for path in paths:
        parts = path.split("/")
        for i in range(len(parts)):
            concept_id = "/".join(parts[: i + 1])
            if concept_id not in concepts:
                concept_label = _CONCEPT_LABEL_OVERRIDES.get(concept_id, parts[i].replace("_", " ").title())
                labels: dict[str, str] = {}
                nb_label = _CONCEPT_LABEL_OVERRIDES_NB.get(concept_id)
                if nb_label:
                    labels["nb"] = nb_label
                concepts[concept_id] = Concept(
                    id=concept_id,
                    prefLabel=concept_label,
                    source=source,
                    labels=labels,
                )


def _merge_concept_data(
    primary_paths: list[str],
    primary_uri_map: dict[str, str],
    secondary_paths: list[str],
    secondary_uri_map: dict[str, str],
) -> tuple[list[str], dict[str, str]]:
    """Merge hierarchy paths and URI maps from two sources.

    Deduplicates identical paths and merges URI maps (primary wins on conflict).

    Args:
        primary_paths: Paths from the primary source.
        primary_uri_map: URI map from the primary source.
        secondary_paths: Paths from the secondary source.
        secondary_uri_map: URI map from the secondary source.

    Returns:
        Tuple of (merged paths, merged uri_map).
    """
    # Union paths, deduplicating
    seen = set(primary_paths)
    merged_paths = list(primary_paths)
    for path in secondary_paths:
        if path not in seen:
            merged_paths.append(path)
            seen.add(path)

    # Merge URI maps - primary wins on conflict
    merged_uris = dict(secondary_uri_map)
    merged_uris.update(primary_uri_map)

    return merged_paths, merged_uris


def _uri_to_source(uri: str) -> str | None:
    """Determine the source name from a URI prefix."""
    if uri.startswith("off:"):
        return "off"
    if uri.startswith("http://aims.fao.org/"):
        return "agrovoc"
    if uri.startswith("http://dbpedia.org/"):
        return "dbpedia"
    if uri.startswith("http://www.wikidata.org/"):
        return "wikidata"
    return None


def _populate_source_uris(
    concepts: dict[str, Concept],
    off_node_ids: dict[str, str],
    all_uri_maps: dict[str, str],
) -> None:
    """Populate source_uris on each concept from all available data.

    Examines off_node_ids, all_uri_maps, and concept.uri to build a
    complete map of source name -> URI for each concept.

    Args:
        concepts: Vocabulary concepts to update in-place.
        off_node_ids: Map of concept_id -> OFF node_id.
        all_uri_maps: Map of concept_id -> URI (from hierarchy building).
    """
    for cid, concept in concepts.items():
        # OFF node IDs
        if cid in off_node_ids:
            concept.source_uris["off"] = "off:" + off_node_ids[cid]

        # URIs from all_uri_maps
        uri = all_uri_maps.get(cid)
        if uri:
            source = _uri_to_source(uri)
            if source and source not in concept.source_uris:
                concept.source_uris[source] = uri

        # URIs from concept.uri
        if concept.uri:
            source = _uri_to_source(concept.uri)
            if source and source not in concept.source_uris:
                concept.source_uris[source] = concept.uri


def _resolve_missing_uris(
    concepts: dict[str, Concept],
    all_uri_maps: dict[str, str],
    client: SKOSClient,
    lang: str,
    enabled_sources: list[str],
) -> int:
    """Auto-resolve URIs for concepts that lack them via DBpedia/Wikidata lookup.

    Tries each concept's prefLabel against DBpedia and Wikidata (in that order,
    filtered by enabled_sources) to find a matching URI. On match, sets the
    concept's URI, updates all_uri_maps, and fills description/wikipediaUrl if
    missing.

    Args:
        concepts: Vocabulary concepts to scan.
        all_uri_maps: URI map to update (concept_id -> URI).
        client: SKOS client for lookups.
        lang: Primary language code for lookups.
        enabled_sources: Enabled taxonomy sources (filters which lookups to try).

    Returns:
        Number of concepts that received a new URI.
    """
    # Determine which lookup sources to try
    sources_to_try = [s for s in ["dbpedia", "wikidata"] if s in enabled_sources]
    if not sources_to_try:
        return 0

    # Collect candidates: concepts without URI, not meta/internal concepts
    candidates: list[tuple[str, Concept]] = []
    for cid, concept in concepts.items():
        if cid.startswith("_") or cid.startswith("category_by_source/"):
            continue
        if concept.uri is not None:
            continue
        if cid in all_uri_maps:
            continue
        candidates.append((cid, concept))

    if not candidates:
        return 0

    logger.info("Resolving URIs for %d concepts without URIs...", len(candidates))
    resolved_count = 0

    for idx, (cid, concept) in enumerate(candidates, 1):
        if idx % 10 == 0:
            logger.info("  URI resolution progress: %d/%d", idx, len(candidates))

        label = concept.prefLabel or cid.split("/")[-1].replace("_", " ")

        for source in sources_to_try:
            result = client.lookup_concept(label, lang, source=source)
            if not result or not result.get("uri"):
                continue

            # Sanity check: returned prefLabel must substring-match concept's prefLabel
            result_label = result.get("prefLabel", "")
            concept_label = concept.prefLabel or ""
            if result_label and concept_label:
                result_lower = result_label.lower()
                concept_lower = concept_label.lower()
                if result_lower not in concept_lower and concept_lower not in result_lower:
                    logger.debug(
                        "URI sanity check failed for %s: concept='%s', %s='%s'",
                        cid,
                        concept_label,
                        source,
                        result_label,
                    )
                    continue

            # Match found — set URI and fill missing metadata
            concept.uri = result["uri"]
            all_uri_maps[cid] = result["uri"]
            if not concept.description and result.get("description"):
                concept.description = result["description"]
            if not concept.wikipediaUrl and result.get("wikipediaUrl"):
                concept.wikipediaUrl = result["wikipediaUrl"]
            resolved_count += 1
            logger.debug("Resolved URI for %s via %s: %s", cid, source, result["uri"])
            break  # Stop after first successful source

    logger.info("Resolved URIs for %d/%d concepts", resolved_count, len(candidates))
    return resolved_count


def _find_additional_translation_uris(
    concepts: dict[str, Concept],
    all_uri_maps: dict[str, str],
    client: SKOSClient,
    lang: str,
    enabled_sources: list[str],
) -> int:
    """Find supplementary DBpedia/Wikidata URIs for concepts that already have a URI.

    Concepts matched via OFF or AGROVOC only have that source's URI. This function
    looks up additional DBpedia/Wikidata URIs so translation phases can query more
    sources, improving coverage (e.g., Norwegian from Wikidata).

    Args:
        concepts: Vocabulary concepts to scan.
        all_uri_maps: URI map (concept_id -> URI).
        client: SKOS client for lookups.
        lang: Primary language code for lookups.
        enabled_sources: Enabled taxonomy sources.

    Returns:
        Number of supplementary URIs found.
    """
    sources_to_try = [s for s in ["dbpedia", "wikidata"] if s in enabled_sources]
    if not sources_to_try:
        return 0

    candidates: list[tuple[str, Concept]] = []
    for cid, concept in concepts.items():
        if cid.startswith("_") or cid.startswith("category_by_source/"):
            continue
        # Must already have at least one URI (otherwise _resolve_missing_uris handles it)
        if not concept.uri and cid not in all_uri_maps:
            continue
        # Skip if already has all the sources we'd look up
        has_dbpedia = "dbpedia" in concept.source_uris
        has_wikidata = "wikidata" in concept.source_uris
        if has_dbpedia and has_wikidata:
            continue
        # Only look up sources the concept is missing
        needed = []
        if "dbpedia" in sources_to_try and not has_dbpedia:
            needed.append("dbpedia")
        if "wikidata" in sources_to_try and not has_wikidata:
            needed.append("wikidata")
        if needed:
            candidates.append((cid, concept))

    if not candidates:
        return 0

    logger.info("Finding additional translation URIs for %d concepts...", len(candidates))
    found_count = 0

    for idx, (cid, concept) in enumerate(candidates, 1):
        if idx % 10 == 0:
            logger.info("  Additional URI progress: %d/%d", idx, len(candidates))

        label = concept.prefLabel or cid.split("/")[-1].replace("_", " ")

        for source in sources_to_try:
            if source in concept.source_uris:
                continue  # Already have this source

            result = client.lookup_concept(label, lang, source=source)
            if not result or not result.get("uri"):
                continue

            # Sanity check: prefLabel must substring-match
            result_label = result.get("prefLabel", "")
            concept_label = concept.prefLabel or ""
            if result_label and concept_label:
                result_lower = result_label.lower()
                concept_lower = concept_label.lower()
                if result_lower not in concept_lower and concept_lower not in result_lower:
                    logger.debug(
                        "Additional URI sanity check failed for %s: concept='%s', %s='%s'",
                        cid,
                        concept_label,
                        source,
                        result_label,
                    )
                    continue

            concept.source_uris[source] = result["uri"]
            found_count += 1
            logger.debug("Found additional %s URI for %s: %s", source, cid, result["uri"])

    logger.info("Found %d additional translation URIs for %d candidates", found_count, len(candidates))
    return found_count


def _progress(
    callback: Callable[[str, str], None] | None,
    phase: str,
    detail: str = "",
) -> None:
    """Invoke progress callback if provided."""
    if callback:
        callback(phase, detail)


def build_vocabulary_with_skos_hierarchy(
    inventory_data: dict[str, Any],
    local_vocab: dict[str, Concept] | None = None,
    lang: str = "en",
    languages: list[str] | None = None,
    enabled_sources: list[str] | None = None,
    progress: Callable[[str, str], None] | None = None,
) -> tuple[dict[str, Concept], dict[str, list[str]]]:
    """Build vocabulary using SKOS hierarchy expansion.

    This mode expands each category label to its full hierarchy paths
    using multiple sources: OFF → AGROVOC → DBpedia (configurable).

    For example, "potatoes" becomes "food/vegetables/potatoes" via OFF
    and may also get additional paths from AGROVOC.

    Args:
        inventory_data: Parsed inventory JSON data.
        local_vocab: Optional local vocabulary to merge with.
        lang: Primary language code for lookups.
        languages: List of language codes to fetch labels for.
        enabled_sources: List of enabled sources in priority order.
                         Defaults to ["off", "agrovoc", "dbpedia", "wikidata"].
        progress: Optional callback invoked with (phase, detail) for progress
                  reporting.  Phases: "init", "expand", "warning", "resolve",
                  "translate".

    Returns:
        Tuple of:
        - Dictionary of concepts (the vocabulary tree)
        - Dictionary mapping original category labels to expanded paths
    """
    if enabled_sources is None:
        enabled_sources = ["off", "agrovoc", "dbpedia", "wikidata"]

    # Initialize OFF client if enabled
    off_client = None
    if "off" in enabled_sources:
        try:
            from .off import OFFTaxonomyClient

            off_client = OFFTaxonomyClient(languages=languages or [lang])
        except ImportError:
            logger.info("OFF module not available, skipping Open Food Facts lookups")

    # Initialize SKOS client if AGROVOC, DBpedia, or Wikidata enabled
    skos_module = None
    client = None
    if "agrovoc" in enabled_sources or "dbpedia" in enabled_sources or "wikidata" in enabled_sources:
        try:
            from . import skos as skos_module

            client = skos_module.SKOSClient(use_oxigraph=True)
        except ImportError:
            logger.info("SKOS module not available, skipping AGROVOC/DBpedia lookups")

    # Eagerly load the Oxigraph store so the delay is visible to the user
    if client is not None and "agrovoc" in enabled_sources:
        _progress(progress, "init", "Loading AGROVOC database...")
        client._get_oxigraph_store()  # Trigger lazy load

    if off_client is None and client is None:
        logger.warning("No taxonomy sources available")
        vocab = build_vocabulary_from_inventory(inventory_data, local_vocab)
        return vocab, {}

    concepts: dict[str, Concept] = {}
    category_mappings: dict[str, list[str]] = {}

    # Start with local vocabulary if provided
    if local_vocab:
        concepts.update(local_vocab)

    # Collect categories from inventory, separating leaf labels from path-based ones
    leaf_labels: set[str] = set()  # Simple labels for hierarchy expansion
    path_categories: set[str] = set()  # Path-based categories to keep as-is
    for container in inventory_data.get("containers", []):
        for item in container.get("items", []):
            categories = item.get("metadata", {}).get("categories", [])
            for category_path in categories:
                if "/" in category_path:
                    # Path-based category - keep the full path structure
                    path_categories.add(category_path)
                else:
                    # Simple label - will be expanded via taxonomy sources
                    leaf_label = category_path.replace("-", " ").replace("_", " ")
                    leaf_labels.add(leaf_label)

    # First, register path-based categories directly in the vocabulary tree
    for path_cat in sorted(path_categories):
        parts = path_cat.split("/")
        # Map the full path to itself
        local_src_path = f"category_by_source/local/{path_cat}"
        category_mappings[path_cat] = [path_cat, local_src_path]
        _add_paths_to_concepts([local_src_path], concepts, "local")
        # Create concept for each path component
        for i in range(len(parts)):
            concept_id = "/".join(parts[: i + 1])
            if concept_id not in concepts:
                concept_label = parts[i].replace("_", " ").replace("-", " ").title()
                concepts[concept_id] = Concept(
                    id=concept_id,
                    prefLabel=concept_label,
                    source="inventory",
                )

    logger.info("Expanding %d leaf labels to hierarchies...", len(leaf_labels))
    _progress(progress, "expand", f"Expanding {len(leaf_labels)} categories to hierarchies...")

    # Track all URIs for translation fetching
    all_uri_maps: dict[str, str] = {}
    # Track OFF node IDs for OFF-specific translation fetching
    off_node_ids: dict[str, str] = {}  # concept_id -> OFF node_id

    # Build index of local vocab labels for quick lookup
    local_vocab_labels: dict[str, str] = {}  # label -> concept_id
    if local_vocab:
        for concept_id, concept in local_vocab.items():
            # Index by concept ID (both original and normalized forms)
            local_vocab_labels[concept_id.lower()] = concept_id
            # Also index singular form so "alarm" matches "alarms" concept
            singular_id = _normalize_to_singular(concept_id.lower())
            if singular_id != concept_id.lower():
                local_vocab_labels[singular_id] = concept_id
            # Also index with - and _ replaced by space (to match leaf label normalization)
            normalized_id = concept_id.lower().replace("-", " ").replace("_", " ")
            if normalized_id != concept_id.lower():
                local_vocab_labels[normalized_id] = concept_id
            # Index by prefLabel (e.g., "Lumber" for concept "construction/lumber")
            if concept.prefLabel:
                pref_lower = concept.prefLabel.lower()
                if pref_lower not in local_vocab_labels:
                    local_vocab_labels[pref_lower] = concept_id
                # Also singular form of prefLabel
                pref_singular = _normalize_to_singular(pref_lower)
                if pref_singular != pref_lower and pref_singular not in local_vocab_labels:
                    local_vocab_labels[pref_singular] = concept_id
            # Index all alt labels
            for alt in concept.altLabels:
                local_vocab_labels[alt.lower()] = concept_id
                # Also normalized form
                normalized_alt = alt.lower().replace("-", " ").replace("_", " ")
                if normalized_alt != alt.lower():
                    local_vocab_labels[normalized_alt] = concept_id

    # Add local vocab concepts that need enrichment (have broader but lack metadata)
    if local_vocab:
        existing_lower = {lbl.lower() for lbl in leaf_labels}
        for concept_id, concept in local_vocab.items():
            if not concept.broader:
                continue  # Skip root categories
            if concept.uri and concept.description:
                continue  # Already has metadata
            label = concept.prefLabel or concept_id
            if label.lower() not in existing_lower:
                leaf_labels.add(label)
                existing_lower.add(label.lower())

    # Expand each leaf label using source priority chain
    total = len(leaf_labels)
    for idx, label in enumerate(sorted(leaf_labels), 1):
        if idx % 4 == 0 or idx == 1:
            _progress(progress, "expand", f"[{idx}/{total}] {label}")

        # Check if label matches a local vocabulary entry
        # Local vocab provides hierarchy (broader), external sources provide metadata (URI, translations)
        label_lower = label.lower()
        local_concept_id = None
        local_concept = None
        local_broader_path = None

        if label_lower in local_vocab_labels:
            local_concept_id = local_vocab_labels[label_lower]
            local_concept = local_vocab[local_concept_id]

            # If the local entry has an AGROVOC URI, use it for hierarchy expansion
            if local_concept.uri and "agrovoc" in local_concept.uri.lower() and client:
                store = client._get_oxigraph_store()
                if store is not None and store.is_loaded:
                    paths, uri_map, agrovoc_raw = _build_paths_to_root(local_concept.uri, store, lang)
                    if paths:
                        category_mappings[label] = paths
                        for k, v in uri_map.items():
                            if k not in all_uri_maps:
                                all_uri_maps[k] = v
                        _add_paths_to_concepts(paths, concepts, "agrovoc")
                        # Store raw source paths under category_by_source
                        agrovoc_src_paths = []
                        for rp in agrovoc_raw:
                            src_path = f"category_by_source/agrovoc/{rp}"
                            _add_paths_to_concepts([src_path], concepts, "agrovoc")
                            agrovoc_src_paths.append(src_path)
                        category_mappings[label].extend(agrovoc_src_paths)
                        logger.debug("Local vocab '%s' -> AGROVOC hierarchy: %s", label, paths)
                        continue

            # Record local broader for later use (but still do external lookups for metadata)
            if local_concept.broader:
                # Resolve the full ancestor chain so that e.g. sandpaper-sheet
                # (broader: sandpaper, which has broader: consumables) becomes
                # consumables/sandpaper/sandpaper-sheet, not sandpaper/sandpaper-sheet
                original_broader = local_concept.broader[0]
                broader_path = _resolve_broader_chain(original_broader, local_vocab)
                parent_leaf = broader_path.split("/")[-1]
                if _is_singular_plural_variant(local_concept_id, parent_leaf):
                    # Concept is singular/plural of parent - merge into parent
                    local_broader_path = broader_path
                elif local_concept_id.startswith(broader_path + "/"):
                    local_broader_path = local_concept_id
                elif local_concept_id.startswith(original_broader + "/"):
                    # ID already embeds the original parent (e.g. "automotive/accessories"
                    # with broader "automotive") — replace prefix with resolved path
                    suffix = local_concept_id[len(original_broader) :]
                    local_broader_path = broader_path + suffix
                else:
                    local_broader_path = f"{broader_path}/{local_concept_id}"

        # Try sources in priority order, collecting paths from all that match
        all_paths: list[str] = []
        all_uris: dict[str, str] = {}
        all_raw_paths: list[str] = []
        primary_source: str | None = None
        sources_found: list[str] = []

        # --- OFF lookup ---
        if off_client is not None:
            off_result = off_client.lookup_concept(label, lang=lang)
            if off_result and off_result.get("node_id"):
                node_id = off_result["node_id"]
                off_paths, off_uri_map, off_raw = off_client.build_paths_to_root(node_id, lang=lang)
                if off_paths:
                    all_paths, all_uris = off_paths, off_uri_map
                    all_raw_paths.extend(off_raw)
                    primary_source = "off"
                    sources_found.append("off")
                    # Track OFF node IDs for translation fetching (first-wins)
                    for cid, uri in off_uri_map.items():
                        if uri.startswith("off:") and cid not in off_node_ids:
                            off_node_ids[cid] = uri[4:]  # Strip "off:" prefix
                    logger.debug("OFF found '%s' -> %d paths", label, len(off_paths))

        # --- AGROVOC lookup ---
        skip_agrovoc = local_concept is not None and local_concept.uri and "agrovoc" not in local_concept.uri.lower()
        if client is not None and "agrovoc" in enabled_sources and not skip_agrovoc:
            agrovoc_paths, found_in_agrovoc, agrovoc_uri_map, agrovoc_raw = build_skos_hierarchy_paths(
                label, client, lang
            )
            if found_in_agrovoc:
                # Check for mismatch: AGROVOC sometimes returns unrelated concepts
                # e.g., "bedding" -> "litter for animals" (farm bedding)
                agrovoc_mismatch = False
                if agrovoc_paths:
                    # Get the leaf concept from the first path
                    leaf = agrovoc_paths[0].split("/")[-1].replace("_", " ").lower()
                    search = label.lower()
                    # Mismatch if leaf doesn't contain search term and vice versa
                    if search not in leaf and leaf not in search and not _is_singular_plural_variant(search, leaf):
                        agrovoc_mismatch = True
                        logger.warning(
                            "AGROVOC mismatch for '%s': returned '%s'. "
                            "Consider adding to local-vocabulary.yaml with DBpedia URI.",
                            label,
                            leaf,
                        )
                        _progress(progress, "warning", f"AGROVOC mismatch: '{label}' -> '{leaf}' (skipping)")

                if not agrovoc_mismatch:
                    if primary_source is None:
                        all_paths, all_uris = agrovoc_paths, agrovoc_uri_map
                        primary_source = "agrovoc"
                    else:
                        # Merge additional paths from AGROVOC
                        all_paths, all_uris = _merge_concept_data(all_paths, all_uris, agrovoc_paths, agrovoc_uri_map)
                    all_raw_paths.extend(agrovoc_raw)
                    sources_found.append("agrovoc")
                    logger.debug("AGROVOC found '%s' -> %d paths", label, len(agrovoc_paths))

        # --- DBpedia fallback ---
        # Only use DBpedia hierarchy if we don't have local vocabulary hierarchy
        if primary_source is None and client is not None and "dbpedia" in enabled_sources:
            dbpedia_concept = client.lookup_concept(label, lang, source="dbpedia")
            if dbpedia_concept and dbpedia_concept.get("uri"):
                concept_id = label.lower().replace(" ", "_")

                # If local vocab provides hierarchy, just capture the URI for translations
                if local_broader_path:
                    all_uri_maps[local_broader_path] = dbpedia_concept["uri"]
                    primary_source = "dbpedia"
                    # Enrich local concept with DBpedia metadata
                    target_id = local_concept_id or local_broader_path.split("/")[-1]
                    if target_id in concepts:
                        c = concepts[target_id]
                        if not c.uri:
                            c.uri = dbpedia_concept["uri"]
                        if not c.description and dbpedia_concept.get("description"):
                            c.description = dbpedia_concept["description"]
                        if not c.wikipediaUrl and dbpedia_concept.get("wikipediaUrl"):
                            c.wikipediaUrl = dbpedia_concept["wikipediaUrl"]
                    # Don't continue - let the local_broader_path handling below run
                else:
                    # No local hierarchy - use DBpedia's hierarchy
                    dbpedia_broader = dbpedia_concept.get("broader", [])

                    # Build paths from both hypernym (is-a) and useful dct:subject categories
                    dbpedia_paths = []
                    broader_ids = []

                    for b in dbpedia_broader:
                        broader_label = b.get("label", "")
                        if not broader_label or skos_module._is_irrelevant_dbpedia_category(broader_label):
                            continue
                        broader_id = broader_label.lower().replace(" ", "_")
                        if broader_id in broader_ids or broader_id == concept_id:
                            continue
                        broader_ids.append(broader_id)
                        full_path = f"{broader_id}/{concept_id}"
                        if b.get("relType") == "hypernym":
                            dbpedia_paths.insert(0, full_path)
                        else:
                            dbpedia_paths.append(full_path)
                        if len(dbpedia_paths) >= 3:
                            break

                    if dbpedia_paths:
                        # Build category_by_source paths before assigning to mappings
                        dbpedia_src_paths = [f"category_by_source/dbpedia/{dp}" for dp in dbpedia_paths]
                        category_mappings[label] = dbpedia_paths + dbpedia_src_paths
                        _add_paths_to_concepts(dbpedia_paths, concepts, "dbpedia")
                        # Store DBpedia URI on leaf concept and in all_uri_maps
                        leaf_path = dbpedia_paths[0]
                        leaf_id = leaf_path.split("/")[-1] if "/" in leaf_path else leaf_path
                        # Find the leaf concept (could be full path or just leaf ID)
                        for candidate in (leaf_path, leaf_id, concept_id):
                            if candidate in concepts:
                                if not concepts[candidate].uri:
                                    concepts[candidate].uri = dbpedia_concept["uri"]
                                break
                        if leaf_path not in all_uri_maps:
                            all_uri_maps[leaf_path] = dbpedia_concept["uri"]
                        if concept_id not in all_uri_maps:
                            all_uri_maps[concept_id] = dbpedia_concept["uri"]
                        # Only set broader if concept doesn't come from local vocab
                        # (local vocab roots should remain roots, not get DBpedia broader)
                        if concept_id in concepts:
                            existing = concepts[concept_id]
                            if existing.source not in ("local", "package") and not existing.broader:
                                concepts[concept_id].broader = broader_ids[:3]
                        # Store raw source paths under category_by_source/dbpedia/
                        for sp in dbpedia_src_paths:
                            _add_paths_to_concepts([sp], concepts, "dbpedia")
                        logger.debug("DBpedia paths for '%s' -> %s", label, dbpedia_paths)
                    else:
                        category_mappings[label] = [concept_id]
                        # Only create new concept if it doesn't already exist
                        # (don't overwrite local vocabulary concepts)
                        if concept_id not in concepts:
                            concepts[concept_id] = Concept(
                                id=concept_id,
                                prefLabel=dbpedia_concept.get("prefLabel", label.title()),
                                altLabels=dbpedia_concept.get("altLabels", []),
                                source="dbpedia",
                                uri=dbpedia_concept["uri"],
                                description=dbpedia_concept.get("description"),
                                wikipediaUrl=dbpedia_concept.get("wikipediaUrl"),
                            )
                        else:
                            # Enrich existing concept with DBpedia metadata if missing
                            existing = concepts[concept_id]
                            if not existing.uri:
                                existing.uri = dbpedia_concept["uri"]
                            if not existing.description:
                                existing.description = dbpedia_concept.get("description")
                            if not existing.wikipediaUrl:
                                existing.wikipediaUrl = dbpedia_concept.get("wikipediaUrl")
                        logger.debug("DBpedia fallback for '%s' -> %s", label, dbpedia_concept["uri"])
                    continue

        # --- Wikidata fallback ---
        # Only use Wikidata hierarchy if no other source found it
        if primary_source is None and client is not None and "wikidata" in enabled_sources:
            wikidata_concept = client.lookup_concept(label, lang, source="wikidata")
            if wikidata_concept and wikidata_concept.get("uri"):
                concept_id = label.lower().replace(" ", "_")

                # If local vocab provides hierarchy, just capture the URI for translations
                if local_broader_path:
                    all_uri_maps[local_broader_path] = wikidata_concept["uri"]
                    primary_source = "wikidata"
                    # Enrich local concept with Wikidata metadata
                    target_id = local_concept_id or local_broader_path.split("/")[-1]
                    if target_id in concepts:
                        c = concepts[target_id]
                        if not c.uri:
                            c.uri = wikidata_concept["uri"]
                        if not c.description and wikidata_concept.get("description"):
                            c.description = wikidata_concept["description"]
                        if not c.wikipediaUrl and wikidata_concept.get("wikipediaUrl"):
                            c.wikipediaUrl = wikidata_concept["wikipediaUrl"]
                    # Don't continue - let the local_broader_path handling below run
                else:
                    # No local hierarchy - use Wikidata's hierarchy
                    wikidata_broader = wikidata_concept.get("broader", [])

                    # Build paths from instance_of and subclass_of relations
                    wikidata_paths = []
                    broader_ids = []

                    for b in wikidata_broader:
                        broader_label = b.get("label", "")
                        broader_uri = b.get("uri", "")
                        if not broader_label or skos_module._is_abstract_wikidata_class(broader_uri):
                            continue
                        broader_id = broader_label.lower().replace(" ", "_")
                        if broader_id in broader_ids or broader_id == concept_id:
                            continue
                        broader_ids.append(broader_id)
                        full_path = f"{broader_id}/{concept_id}"
                        if b.get("relType") == "instance_of":
                            wikidata_paths.insert(0, full_path)
                        else:
                            wikidata_paths.append(full_path)
                        if len(wikidata_paths) >= 3:
                            break

                    if wikidata_paths:
                        # Build category_by_source paths before assigning to mappings
                        wikidata_src_paths = [f"category_by_source/wikidata/{wp}" for wp in wikidata_paths]
                        category_mappings[label] = wikidata_paths + wikidata_src_paths
                        _add_paths_to_concepts(wikidata_paths, concepts, "wikidata")
                        # Store Wikidata URI on leaf concept and in all_uri_maps
                        leaf_path = wikidata_paths[0]
                        leaf_id = leaf_path.split("/")[-1] if "/" in leaf_path else leaf_path
                        for candidate in (leaf_path, leaf_id, concept_id):
                            if candidate in concepts:
                                if not concepts[candidate].uri:
                                    concepts[candidate].uri = wikidata_concept["uri"]
                                break
                        if leaf_path not in all_uri_maps:
                            all_uri_maps[leaf_path] = wikidata_concept["uri"]
                        if concept_id not in all_uri_maps:
                            all_uri_maps[concept_id] = wikidata_concept["uri"]
                        # Only set broader if concept doesn't come from local vocab
                        if concept_id in concepts:
                            existing = concepts[concept_id]
                            if existing.source not in ("local", "package") and not existing.broader:
                                concepts[concept_id].broader = broader_ids[:3]
                        # Store raw source paths under category_by_source/wikidata/
                        for sp in wikidata_src_paths:
                            _add_paths_to_concepts([sp], concepts, "wikidata")
                        logger.debug("Wikidata paths for '%s' -> %s", label, wikidata_paths)
                    else:
                        category_mappings[label] = [concept_id]
                        if concept_id not in concepts:
                            concepts[concept_id] = Concept(
                                id=concept_id,
                                prefLabel=wikidata_concept.get("prefLabel", label.title()),
                                altLabels=wikidata_concept.get("altLabels", []),
                                source="wikidata",
                                uri=wikidata_concept["uri"],
                                description=wikidata_concept.get("description"),
                                wikipediaUrl=wikidata_concept.get("wikipediaUrl"),
                            )
                        else:
                            # Enrich existing concept with Wikidata metadata if missing
                            existing = concepts[concept_id]
                            if not existing.uri:
                                existing.uri = wikidata_concept["uri"]
                            if not existing.description:
                                existing.description = wikidata_concept.get("description")
                            if not existing.wikipediaUrl:
                                existing.wikipediaUrl = wikidata_concept.get("wikipediaUrl")
                        logger.debug("Wikidata fallback for '%s' -> %s", label, wikidata_concept["uri"])
                    continue

        if all_paths or local_broader_path:
            # If local vocabulary provides hierarchy, use it; otherwise use external paths
            if local_broader_path:
                # Local vocab provides hierarchy, external sources provide metadata
                final_paths = [local_broader_path]
                source = primary_source or "local"
                # Get URI from external source if available
                if all_uris:
                    # Use original concept ID for matching, not the (possibly redirected) path
                    match_id = local_concept_id if local_concept_id else local_broader_path.split("/")[-1]
                    for ext_cid, ext_uri in all_uris.items():
                        if ext_cid.endswith(match_id) or match_id in ext_cid:
                            all_uri_maps[local_broader_path] = ext_uri
                            if ext_uri.startswith("off:"):
                                off_node_ids[local_broader_path] = ext_uri[4:]
                            break
                elif local_concept and local_concept.uri:
                    # No external URI found, but local concept has a URI
                    all_uri_maps[local_broader_path] = local_concept.uri
                logger.debug("Local hierarchy '%s' enriched with %s metadata", label, source)
            else:
                # Use external hierarchy paths
                # Normalize paths to collapse consecutive similar components
                # e.g., "food/foods/prepared_foods" -> "food/prepared_foods"
                final_paths = [_normalize_hierarchy_path(p) for p in all_paths]
                source = primary_source or "inventory"

            category_mappings[label] = final_paths
            for k, v in all_uris.items():
                if k not in all_uri_maps:
                    all_uri_maps[k] = v
            _target_existed = local_broader_path in concepts
            _add_paths_to_concepts(final_paths, concepts, source)

            # Transfer metadata from flat local concept to path-prefixed concept
            # and remove the orphaned flat concept to eliminate duplication
            if (
                local_broader_path
                and local_concept_id
                and local_concept_id != local_broader_path
                and local_concept_id in concepts
                and local_broader_path in concepts
            ):
                _flat = concepts[local_concept_id]
                _target = concepts[local_broader_path]
                if not _target_existed:
                    # Newly created by _add_paths_to_concepts: overwrite metadata
                    _target.prefLabel = _flat.prefLabel
                    _target.altLabels = _flat.altLabels.copy()
                    # Preserve external source from enrichment; otherwise use
                    # the flat concept's source (e.g. "package" or "local")
                    if _target.source not in ("dbpedia", "off", "agrovoc", "wikidata"):
                        _target.source = _flat.source
                else:
                    # Existing concept (e.g., singular/plural merge): merge altLabels
                    existing_alts = set(_target.altLabels)
                    for alt in _flat.altLabels:
                        if alt not in existing_alts:
                            _target.altLabels.append(alt)
                # Propagate package/local source from the authoritative flat
                # concept, unless the target was enriched by an external source
                if _target.source not in ("dbpedia", "off", "agrovoc", "wikidata"):
                    _target.source = _flat.source
                # Fill missing metadata (works for both cases)
                if _flat.uri and not _target.uri:
                    _target.uri = _flat.uri
                if _flat.description and not _target.description:
                    _target.description = _flat.description
                if _flat.wikipediaUrl and not _target.wikipediaUrl:
                    _target.wikipediaUrl = _flat.wikipediaUrl
                if _flat.labels:
                    merged = dict(_flat.labels)
                    merged.update(_target.labels)
                    _target.labels = merged
                if _flat.descriptions:
                    merged = dict(_flat.descriptions)
                    merged.update(_target.descriptions)
                    _target.descriptions = merged
                if _flat.source_uris:
                    merged_su = dict(_flat.source_uris)
                    merged_su.update(_target.source_uris)
                    _target.source_uris = merged_su
                del concepts[local_concept_id]

            # Store raw source paths under category_by_source/<source>/
            if all_raw_paths and primary_source:
                for rp in all_raw_paths:
                    src_path = f"category_by_source/{primary_source}/{rp}"
                    _add_paths_to_concepts([src_path], concepts, primary_source)
                    category_mappings[label].append(src_path)
            # Also create category_by_source/local/ path for local vocab entries
            if local_broader_path:
                local_src_path = f"category_by_source/local/{local_broader_path}"
                _add_paths_to_concepts([local_src_path], concepts, "local")
                category_mappings[label].append(local_src_path)
        else:
            # No source found - fall back to label as-is
            fallback_id = label.lower().replace(" ", "_")
            local_src_path = f"category_by_source/local/{fallback_id}"
            category_mappings[label] = [fallback_id, local_src_path]
            _add_paths_to_concepts([fallback_id], concepts, "inventory")
            _add_paths_to_concepts([local_src_path], concepts, "local")

    # Auto-resolve URIs for concepts that lack them (before translation phases)
    if client is not None and languages and len(languages) > 1:
        _progress(progress, "resolve", "Resolving URIs for concepts without URIs...")
        _resolve_missing_uris(concepts, all_uri_maps, client, lang, enabled_sources)

    # Populate source_uris from all collected data
    _populate_source_uris(concepts, off_node_ids, all_uri_maps)

    # Find supplementary DBpedia/Wikidata URIs for better translation coverage
    if client is not None and languages and len(languages) > 1:
        _progress(progress, "resolve", "Finding additional translation URIs...")
        _find_additional_translation_uris(concepts, all_uri_maps, client, lang, enabled_sources)

    # Fetch translations for concepts with URIs
    if languages and len(languages) > 1:
        logger.info("Fetching translations for %d languages...", len(languages))
        _progress(progress, "translate", f"Fetching translations for {len(languages)} languages...")

        # OFF translations (fast - from local taxonomy data)
        if off_client is not None:
            _progress(progress, "translate", f"Fetching OFF translations for {len(off_node_ids)} concepts...")
            for concept_id, node_id in off_node_ids.items():
                if concept_id in concepts:
                    concept = concepts[concept_id]
                    off_labels = off_client.get_labels(node_id, languages, use_fallbacks=False)
                    if off_labels:
                        # Sanity check: skip if English label doesn't match concept
                        en_label = off_labels.get("en", "")
                        if en_label and concept.prefLabel:
                            en_lower = en_label.lower()
                            pref_lower = concept.prefLabel.lower()
                            if en_lower not in pref_lower and pref_lower not in en_lower:
                                logger.debug(
                                    "Skipping mismatched OFF labels for %s: prefLabel='%s', OFF en='%s'",
                                    concept_id,
                                    concept.prefLabel,
                                    en_label,
                                )
                                continue
                        # Merge: OFF labels as base, don't overwrite existing
                        merged_labels = dict(off_labels)
                        merged_labels.update(concept.labels)
                        concept.labels = merged_labels

        # AGROVOC translations (from Oxigraph store)
        if client is not None:
            _progress(progress, "translate", "Fetching AGROVOC translations...")
            store = client._get_oxigraph_store()
            if store is not None and store.is_loaded:
                for concept_id, concept in concepts.items():
                    candidate_uris = list(dict.fromkeys(filter(None, [all_uri_maps.get(concept_id), concept.uri])))
                    for uri in candidate_uris:
                        # Skip OFF, DBpedia, and Wikidata URIs for AGROVOC store lookups
                        if (
                            uri.startswith("off:")
                            or uri.startswith("http://dbpedia.org/")
                            or uri.startswith("http://www.wikidata.org/")
                        ):
                            continue
                        agrovoc_labels = _get_all_labels(uri, store, languages, use_fallbacks=False)
                        if agrovoc_labels:
                            # Sanity check: skip if English label doesn't match
                            en_label = agrovoc_labels.get("en", "")
                            if en_label and concept.prefLabel:
                                en_lower = en_label.lower()
                                pref_lower = concept.prefLabel.lower()
                                if en_lower not in pref_lower and pref_lower not in en_lower:
                                    logger.debug(
                                        "Skipping mismatched AGROVOC labels for %s: prefLabel='%s', AGROVOC en='%s'",
                                        concept_id,
                                        concept.prefLabel,
                                        en_label,
                                    )
                                    continue
                            # Merge: AGROVOC fills gaps, doesn't overwrite OFF
                            merged_labels = dict(agrovoc_labels)
                            merged_labels.update(concept.labels)
                            concept.labels = merged_labels
                            break

        # DBpedia translations (via SPARQL) — use source_uris for lookup
        # Multiple concepts can share the same DBpedia URI (e.g. root "electronics"
        # and AGROVOC path "subjects/.../electronics"), so map URI -> list[concept_id].
        if client is not None:
            dbpedia_uri_set: set[str] = set()
            dbpedia_uris: list[tuple[str, str]] = []
            dbpedia_concept_map: dict[str, list[str]] = {}
            for concept_id, concept in concepts.items():
                uri = concept.source_uris.get("dbpedia")
                if not uri:
                    continue
                if uri not in dbpedia_uri_set:
                    dbpedia_uris.append((uri, "dbpedia"))
                    dbpedia_uri_set.add(uri)
                dbpedia_concept_map.setdefault(uri, []).append(concept_id)

            if dbpedia_uris:
                _progress(progress, "translate", f"Fetching DBpedia translations for {len(dbpedia_uris)} concepts...")
                logger.info("Fetching DBpedia translations for %d concepts...", len(dbpedia_uris))
                dbpedia_translations = client.get_batch_labels(dbpedia_uris, languages)
                applied = 0
                for uri, labels in dbpedia_translations.items():
                    cids = dbpedia_concept_map.get(uri, [])
                    if not labels:
                        continue
                    for cid in cids:
                        if cid not in concepts:
                            continue
                        concept = concepts[cid]
                        # Sanity check: skip if English label doesn't match concept
                        en_label = labels.get("en", "")
                        if en_label and concept.prefLabel:
                            en_lower = en_label.lower()
                            pref_lower = concept.prefLabel.lower()
                            if en_lower not in pref_lower and pref_lower not in en_lower:
                                logger.debug(
                                    "Skipping mismatched DBpedia labels for %s: prefLabel='%s', DBpedia en='%s'",
                                    cid,
                                    concept.prefLabel,
                                    en_label,
                                )
                                continue
                        # Merge: DBpedia fills gaps, doesn't overwrite OFF/AGROVOC
                        merged_labels = dict(labels)
                        merged_labels.update(concept.labels)
                        concept.labels = merged_labels
                        applied += 1
                logger.info("DBpedia translations applied to %d/%d concepts", applied, len(dbpedia_translations))

        # Wikidata translations (fills Norwegian/other gaps)
        # Use Wikidata URI if available, fall back to DBpedia URI (via sitelinks)
        # Multiple concepts can share the same URI, so map URI -> list[concept_id].
        if client is not None:
            wikidata_uri_set: set[str] = set()
            wikidata_uris: list[tuple[str, str]] = []
            wikidata_concept_map: dict[str, list[str]] = {}
            for concept_id, concept in concepts.items():
                uri = concept.source_uris.get("wikidata") or concept.source_uris.get("dbpedia")
                if not uri:
                    continue
                if uri not in wikidata_uri_set:
                    wikidata_uris.append((uri, "wikidata"))
                    wikidata_uri_set.add(uri)
                wikidata_concept_map.setdefault(uri, []).append(concept_id)

            if wikidata_uris:
                _progress(progress, "translate", f"Fetching Wikidata translations for {len(wikidata_uris)} concepts...")
                logger.info("Fetching Wikidata translations for %d concepts...", len(wikidata_uris))
                wikidata_translations = client.get_batch_labels(wikidata_uris, languages)
                for uri, labels in wikidata_translations.items():
                    cids = wikidata_concept_map.get(uri, [])
                    if not labels:
                        continue
                    for cid in cids:
                        if cid not in concepts:
                            continue
                        concept = concepts[cid]
                        # Merge: Wikidata fills gaps, doesn't overwrite
                        merged_labels = dict(labels)
                        merged_labels.update(concept.labels)
                        concept.labels = merged_labels

    # Apply language fallbacks to fill remaining gaps (e.g., nb from sv)
    if languages and len(languages) > 1:
        _progress(progress, "translate", "Applying language fallbacks...")
        for concept in concepts.values():
            if concept.labels:
                concept.labels = apply_language_fallbacks(concept.labels, languages)

    # Final dedup pass: move local concepts to their resolved path-prefixed form.
    # Flat versions can be (re-)created as intermediate nodes by _add_paths_to_concepts
    # when processing child concepts or path-based categories.
    if local_vocab:
        to_delete = []
        for concept_id, concept in local_vocab.items():
            if concept_id.startswith("_") or not concept.broader:
                continue
            resolved = _resolve_broader_chain(concept_id, local_vocab)
            if resolved == concept_id or concept_id not in concepts:
                continue
            _flat = concepts[concept_id]
            if resolved in concepts:
                # Both exist: merge metadata into the path-prefixed target
                _target = concepts[resolved]
                # Propagate package/local source from the authoritative flat
                # concept, unless the target was enriched by an external source
                if _target.source not in ("dbpedia", "off", "agrovoc", "wikidata"):
                    _target.source = _flat.source
                if _flat.prefLabel and not _target.prefLabel:
                    _target.prefLabel = _flat.prefLabel
                existing_alts = set(_target.altLabels)
                for alt in _flat.altLabels:
                    if alt not in existing_alts:
                        _target.altLabels.append(alt)
                if _flat.uri and not _target.uri:
                    _target.uri = _flat.uri
                if _flat.description and not _target.description:
                    _target.description = _flat.description
                if _flat.wikipediaUrl and not _target.wikipediaUrl:
                    _target.wikipediaUrl = _flat.wikipediaUrl
                if _flat.labels:
                    merged = dict(_flat.labels)
                    merged.update(_target.labels)
                    _target.labels = merged
                if _flat.descriptions:
                    merged = dict(_flat.descriptions)
                    merged.update(_target.descriptions)
                    _target.descriptions = merged
                if _flat.source_uris:
                    merged_su = dict(_flat.source_uris)
                    merged_su.update(_target.source_uris)
                    _target.source_uris = merged_su
            else:
                # Only flat exists: move it to the resolved path
                _add_paths_to_concepts([resolved], concepts, _flat.source)
                _target = concepts[resolved]
                _target.prefLabel = _flat.prefLabel
                _target.altLabels = _flat.altLabels.copy()
                _target.uri = _flat.uri
                _target.description = _flat.description
                _target.wikipediaUrl = _flat.wikipediaUrl
                _target.labels = dict(_flat.labels)
                _target.descriptions = dict(_flat.descriptions)
                _target.source_uris = dict(_flat.source_uris)
                _target.source = _flat.source
            to_delete.append(concept_id)
        for cid in to_delete:
            del concepts[cid]
        if to_delete:
            logger.debug("Final dedup removed %d flat concepts: %s", len(to_delete), to_delete)

    logger.info(
        "Built vocabulary with %d concepts (%d leaf labels, %d path categories)",
        len(concepts),
        len(leaf_labels),
        len(path_categories),
    )

    return concepts, category_mappings
