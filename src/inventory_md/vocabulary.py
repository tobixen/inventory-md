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
        # source auto-detected as "dbpedia" from URI
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from . import skos
    SKOSClient = skos.SKOSClient

logger = logging.getLogger(__name__)


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


def load_local_vocabulary(path: Path) -> dict[str, Concept]:
    """Load local vocabulary from YAML or JSON file.

    Args:
        path: Path to local-vocabulary.yaml or local-vocabulary.json

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
                    "PyYAML required for .yaml vocabulary files. "
                    "Install with: pip install inventory-md[yaml]"
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

        # Determine source from URI if not explicitly set
        uri = concept_data.get("uri")
        source = concept_data.get("source", "local")
        if uri and source == "local":
            if "agrovoc" in uri.lower():
                source = "agrovoc"
            elif "dbpedia" in uri.lower():
                source = "dbpedia"

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


def merge_vocabularies(
    local: dict[str, Concept], skos_concepts: dict[str, Concept]
) -> dict[str, Concept]:
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


def build_category_tree(
    vocabulary: dict[str, Concept], infer_hierarchy: bool = True
) -> CategoryTree:
    """Build a category tree structure for the UI.

    Args:
        vocabulary: Dictionary of concepts.
        infer_hierarchy: If True, infer parent/child relationships from paths.

    Returns:
        CategoryTree with roots and label index.
    """
    # Make a copy to avoid modifying the original
    concepts = {k: Concept(
        id=v.id,
        prefLabel=v.prefLabel,
        altLabels=v.altLabels.copy(),
        broader=v.broader.copy(),
        narrower=v.narrower.copy(),
        source=v.source,
        uri=v.uri,
        labels=v.labels.copy() if v.labels else {},
    ) for k, v in vocabulary.items()}

    if infer_hierarchy:
        _infer_hierarchy(concepts)

    # Find roots - concepts that should appear at the top level of the tree
    # This includes:
    # 1. Path roots with children (e.g., "food" which has "food/vegetables")
    # 2. Standalone concepts without broader and without "/" (e.g., "hammer")
    roots = []

    for concept_id, concept in concepts.items():
        # Skip concepts with "/" - they're part of a hierarchy, not roots
        if "/" in concept_id:
            continue

        # Include if it has children (it's a category root like "food")
        if concept.narrower:
            roots.append(concept_id)
        # Also include if it has no broader (standalone concept like "hammer")
        elif not concept.broader:
            roots.append(concept_id)

    # Sort roots alphabetically by prefLabel
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
    "food", "vegetable", "vegetables", "fruit", "fruits", "meat", "fish",
    "grain", "grains", "cereal", "cereals", "dairy", "spice", "spices",
    "herb", "herbs", "potato", "potatoes", "carrot", "carrots", "onion",
    "onions", "tomato", "tomatoes", "apple", "apples", "banana", "bananas",
    "rice", "wheat", "corn", "maize", "bean", "beans", "pea", "peas",
    "lentil", "lentils", "nut", "nuts", "seed", "seeds", "oil", "oils",
    "sugar", "salt", "pepper", "garlic", "ginger", "cinnamon", "flour",
    "bread", "pasta", "noodle", "noodles", "cheese", "milk", "butter",
    "egg", "eggs", "chicken", "beef", "pork", "lamb", "salmon", "tuna",
    "shrimp", "crab", "lobster", "oyster", "mussel", "clam", "squid",
    "wine", "beer", "coffee", "tea", "juice", "water", "soda", "alcohol",
    "honey", "jam", "jelly", "syrup", "sauce", "vinegar", "mustard",
    "ketchup", "mayonnaise", "olive", "olives", "pickle", "pickles",
    "canned", "frozen", "dried", "fresh", "organic", "preserves",
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
    exceptions = {'series', 'species', 'shoes', 'canoes', 'tiptoes', 'glasses',
                  'clothes', 'scissors', 'trousers', 'pants', 'shorts', 'news',
                  'mathematics', 'physics', 'economics', 'politics', 'athletics'}
    if w in exceptions:
        return word

    # Words ending in 'ies' -> 'y' (berries -> berry)
    if w.endswith('ies') and len(w) > 4:
        return word[:-3] + 'y'

    # Words ending in 'es' after s/x/z/ch/sh -> remove 'es'
    if w.endswith('es') and len(w) > 3:
        stem = w[:-2]
        if stem.endswith(('s', 'x', 'z', 'ch', 'sh')):
            return word[:-2]
        # Words ending in 'oes' -> 'o' (potatoes -> potato)
        if w.endswith('oes') and len(w) > 4:
            return word[:-2]

    # Regular plurals ending in 's' (but not 'ss', 'us', 'is')
    if w.endswith('s') and not w.endswith(('ss', 'us', 'is', 'ous', 'ness', 'ics')):
        return word[:-1]

    return word


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
            c.prefLabel.lower() == label.lower() and c.source != "inventory"
            for c in concepts.values()
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
                logger.debug("AGROVOC mismatch: searched '%s', got '%s' - trying DBpedia",
                            label, concept_data.get("prefLabel"))
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
                logger.info("Fetching translations for %d concepts in %d languages...",
                           len(uris_to_fetch), len(other_langs))

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


def count_items_per_category(
    inventory_data: dict[str, Any]
) -> dict[str, int]:
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
) -> tuple[list[str], bool, dict[str, str]]:
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
        dict mapping concept_id to AGROVOC URI).
    """
    store = client._get_oxigraph_store()
    if store is None or not store.is_loaded:
        logger.warning("Oxigraph not available for hierarchy building")
        return [concept_label.lower().replace(" ", "_")], False, {}

    # First, find the concept URI
    uri = _find_agrovoc_uri(concept_label, store)
    if not uri:
        logger.debug("No AGROVOC URI found for %s", concept_label)
        return [concept_label.lower().replace(" ", "_")], False, {}

    # Build all paths from this concept up to roots
    paths, uri_map = _build_paths_to_root(uri, store, lang)

    if not paths:
        # Fall back to just the concept label
        return [concept_label.lower().replace(" ", "_")], False, {}

    return paths, True, uri_map


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
    if not base.endswith('s'):
        if base.endswith('y') and len(base) > 2 and base[-2] not in 'aeiou':
            variations.append(base[:-1] + 'ies')  # berry -> berries
        elif base.endswith(('s', 'x', 'z', 'ch', 'sh', 'o')):
            variations.append(base + 'es')  # box -> boxes
        else:
            variations.append(base + 's')  # book -> books

    # Add singular variation
    if base.endswith('ies') and len(base) > 4:
        variations.append(base[:-3] + 'y')  # berries -> berry
    elif base.endswith('es') and len(base) > 3:
        stem = base[:-2]
        if stem.endswith(('s', 'x', 'z', 'ch', 'sh')):
            variations.append(stem)  # boxes -> box
        elif base.endswith('oes'):
            variations.append(base[:-2])  # potatoes -> potato
    elif base.endswith('s') and not base.endswith(('ss', 'us', 'is')):
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
            return results[0]['concept']['value']

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
            return results[0]['concept']['value']

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
        return results[0]['labelText']['value']

    # Fall back to English
    if lang != "en":
        query = f'''
        PREFIX skosxl: <http://www.w3.org/2008/05/skos-xl#>
        SELECT ?labelText WHERE {{
            <{uri}> skosxl:prefLabel ?labelRes .
            ?labelRes skosxl:literalForm ?labelText .
            FILTER(LANG(?labelText) = "en")
        }} LIMIT 1
        '''

        results = list(store.query(query))
        if results:
            return results[0]['labelText']['value']

    # Fall back to URI fragment
    return uri.split('/')[-1]


def _get_all_labels(uri: str, store, languages: list[str]) -> dict[str, str]:
    """Get prefLabels for an AGROVOC concept URI in multiple languages.

    Args:
        uri: AGROVOC concept URI.
        store: Oxigraph store instance.
        languages: List of language codes to fetch.

    Returns:
        Dict mapping language code to label string.
    """
    labels = {}
    for lang in languages:
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
            labels[lang] = results[0]['labelText']['value']

    return labels


def _get_broader_concepts(uri: str, store) -> list[str]:
    """Get all broader concept URIs for a concept.

    Args:
        uri: AGROVOC concept URI.
        store: Oxigraph store instance.

    Returns:
        List of broader concept URIs.
    """
    query = f'''
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
    SELECT ?broader WHERE {{
        <{uri}> skos:broader ?broader .
    }}
    '''

    results = list(store.query(query))
    return [r['broader']['value'] for r in results]


def _build_paths_to_root(
    uri: str,
    store,
    lang: str = "en",
    visited: set | None = None,
    current_path: list | None = None,
    uri_map: dict | None = None,
) -> tuple[list[str], dict[str, str]]:
    """Recursively build all paths from a concept to root(s).

    Args:
        uri: Starting concept URI.
        store: Oxigraph store instance.
        lang: Language code for labels.
        visited: Set of visited URIs to avoid cycles.
        current_path: Current path being built (concept labels).
        uri_map: Dict mapping concept_id to URI for translation fetching.

    Returns:
        Tuple of (list of complete paths, dict of concept_id -> URI).
    """
    if visited is None:
        visited = set()
    if current_path is None:
        current_path = []
    if uri_map is None:
        uri_map = {}

    if uri in visited:
        return [], uri_map
    visited.add(uri)

    # Get label for current concept
    label = _get_agrovoc_label(uri, store, lang)
    label_normalized = label.lower().replace(" ", "_").replace("-", "_")

    # Add to path (prepend since we're going up the hierarchy)
    new_path = [label_normalized] + current_path

    # Get broader concepts
    broader_uris = _get_broader_concepts(uri, store)

    if not broader_uris:
        # We've reached a root - apply mapping if available
        root_label = label.lower()
        if root_label in AGROVOC_ROOT_MAPPING:
            mapped_root = AGROVOC_ROOT_MAPPING[root_label]
            new_path[0] = mapped_root
        # Return the complete path
        full_path = "/".join(new_path)
        # Track URI for each concept in the path
        for i in range(len(new_path)):
            concept_id = "/".join(new_path[: i + 1])
            if concept_id not in uri_map:
                uri_map[concept_id] = uri  # Store URI for leaf concept
        return [full_path], uri_map

    # Continue up the hierarchy for each broader concept
    all_paths = []
    for broader_uri in broader_uris:
        paths, uri_map = _build_paths_to_root(
            broader_uri, store, lang, visited.copy(), new_path, uri_map
        )
        all_paths.extend(paths)

    # Track URI for this concept
    for i in range(len(new_path)):
        concept_id = "/".join(new_path[: i + 1])
        if concept_id not in uri_map:
            uri_map[concept_id] = uri

    return all_paths, uri_map


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
    return build_skos_hierarchy_paths(category_label, client, lang)


def build_vocabulary_with_skos_hierarchy(
    inventory_data: dict[str, Any],
    local_vocab: dict[str, Concept] | None = None,
    lang: str = "en",
    languages: list[str] | None = None,
) -> tuple[dict[str, Concept], dict[str, list[str]]]:
    """Build vocabulary using SKOS hierarchy expansion.

    This mode expands each category label to its full SKOS hierarchy paths.
    For example, "potatoes" becomes "food/plant_products/vegetables/root_vegetables/potatoes".

    This ensures all food items can be found under a common "food" root,
    regardless of the original category path in inventory.md.

    Args:
        inventory_data: Parsed inventory JSON data.
        local_vocab: Optional local vocabulary to merge with.
        lang: Primary language code for SKOS lookups.
        languages: List of language codes to fetch labels for.

    Returns:
        Tuple of:
        - Dictionary of concepts (the vocabulary tree)
        - Dictionary mapping original category labels to expanded paths
    """
    try:
        from . import skos as skos_module
    except ImportError:
        logger.warning("SKOS module not available")
        vocab = build_vocabulary_from_inventory(inventory_data, local_vocab)
        return vocab, {}

    concepts: dict[str, Concept] = {}
    category_mappings: dict[str, list[str]] = {}

    # Start with local vocabulary if provided
    if local_vocab:
        concepts.update(local_vocab)

    # Collect all unique category labels from inventory
    all_category_labels: set[str] = set()
    for container in inventory_data.get("containers", []):
        for item in container.get("items", []):
            categories = item.get("metadata", {}).get("categories", [])
            for category_path in categories:
                # Extract leaf label from path (e.g., "food/vegetables" -> "vegetables")
                # or use whole label if no path separator
                leaf_label = category_path.split("/")[-1] if "/" in category_path else category_path
                # Normalize: replace - and _ with space (keep plural/singular as-is)
                leaf_label = leaf_label.replace("-", " ").replace("_", " ")
                all_category_labels.add(leaf_label)

    logger.info("Expanding %d category labels to SKOS hierarchies...", len(all_category_labels))
    print(f"   Expanding {len(all_category_labels)} categories to SKOS hierarchies...")

    # Create SKOS client with Oxigraph for faster lookups
    client = skos_module.SKOSClient(use_oxigraph=True)

    # Track all URIs for translation fetching
    all_uri_maps: dict[str, str] = {}

    # Build index of local vocab labels for quick lookup
    local_vocab_labels: dict[str, str] = {}  # label -> concept_id
    if local_vocab:
        for concept_id, concept in local_vocab.items():
            # Index by concept ID and all alt labels
            local_vocab_labels[concept_id.lower()] = concept_id
            for alt in concept.altLabels:
                local_vocab_labels[alt.lower()] = concept_id

    # Expand each label to SKOS paths
    total = len(all_category_labels)
    for idx, label in enumerate(sorted(all_category_labels), 1):
        if idx % 4 == 0 or idx == 1:
            print(f"   [{idx}/{total}] {label}", flush=True)

        # Check if label matches a local vocabulary entry (skip SKOS lookup)
        label_lower = label.lower()
        if label_lower in local_vocab_labels:
            local_concept_id = local_vocab_labels[label_lower]
            local_concept = local_vocab[local_concept_id]
            # Use the local concept's ID as the path
            category_mappings[label] = [local_concept_id]
            # Track URI if present
            if local_concept.uri:
                all_uri_maps[local_concept_id] = local_concept.uri
            logger.debug("Using local vocabulary for '%s' -> %s", label, local_concept_id)
            continue

        paths, found_in_skos, uri_map = build_skos_hierarchy_paths(label, client, lang)
        category_mappings[label] = paths

        # Collect URI mappings
        all_uri_maps.update(uri_map)

        # Determine source - "agrovoc" if found, "inventory" if fallback
        source = "agrovoc" if found_in_skos else "inventory"

        # Add all path components to vocabulary
        for path in paths:
            parts = path.split("/")
            for i in range(len(parts)):
                concept_id = "/".join(parts[: i + 1])
                if concept_id not in concepts:
                    # Create concept with label from path component
                    concept_label = parts[i].replace("_", " ").title()
                    concepts[concept_id] = Concept(
                        id=concept_id,
                        prefLabel=concept_label,
                        source=source,
                    )

    # Fetch translations for concepts with URIs
    if languages and len(languages) > 1:
        store = client._get_oxigraph_store()
        if store is not None and store.is_loaded:
            logger.info("Fetching translations for %d languages...", len(languages))
            print(f"   Fetching translations for {len(languages)} languages...")
            for concept_id, concept in concepts.items():
                if concept_id in all_uri_maps:
                    uri = all_uri_maps[concept_id]
                    labels = _get_all_labels(uri, store, languages)
                    if labels:
                        concept.labels = labels

    logger.info("Built vocabulary with %d concepts from %d category labels",
                len(concepts), len(all_category_labels))

    return concepts, category_mappings
