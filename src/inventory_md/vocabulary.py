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
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Concept:
    """A SKOS concept with labels and hierarchy."""

    id: str  # Unique identifier (path like "food/vegetables/potatoes")
    prefLabel: str  # Preferred display label
    altLabels: list[str] = field(default_factory=list)  # Alternative labels/synonyms
    broader: list[str] = field(default_factory=list)  # Parent concept IDs
    narrower: list[str] = field(default_factory=list)  # Child concept IDs
    source: str = "local"  # "local", "agrovoc", "dbpedia"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "prefLabel": self.prefLabel,
            "altLabels": self.altLabels,
            "broader": self.broader,
            "narrower": self.narrower,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Concept":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            prefLabel=data.get("prefLabel", data["id"]),
            altLabels=data.get("altLabels", []),
            broader=data.get("broader", []),
            narrower=data.get("narrower", []),
            source=data.get("source", "local"),
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

        concepts[concept_id] = Concept(
            id=concept_id,
            prefLabel=concept_data.get("prefLabel", concept_id),
            altLabels=alt_labels,
            broader=broader,
            narrower=narrower,
            source="local",
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
    - broader: ["food/vegetables"]
    - narrower: ["food/vegetables/potatoes"] to parent

    Modifies concepts in place.

    Args:
        concepts: Dictionary of concepts to update.
    """
    # Sort by path depth to process parents before children
    concept_ids = sorted(concepts.keys(), key=lambda x: x.count("/"))

    for concept_id in concept_ids:
        concept = concepts[concept_id]

        # Skip if broader is already explicitly set
        if concept.broader:
            continue

        # Infer parent from path
        if "/" in concept_id:
            parent_id = "/".join(concept_id.split("/")[:-1])
            if parent_id and parent_id in concepts:
                concept.broader = [parent_id]
                # Also add this concept to parent's narrower list
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
    ) for k, v in vocabulary.items()}

    if infer_hierarchy:
        _infer_hierarchy(concepts)

    # Find root concepts (no broader relationships)
    roots = [
        concept_id
        for concept_id, concept in concepts.items()
        if not concept.broader
    ]

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
) -> dict[str, Concept]:
    """Build vocabulary from categories used in inventory data.

    Scans all items in inventory for category: metadata and creates
    concepts for each unique category path found.

    Args:
        inventory_data: Parsed inventory JSON data.
        local_vocab: Optional local vocabulary to merge with.
        use_skos: If True, look up categories in SKOS vocabularies.
        lang: Language code for SKOS lookups.

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
        concepts = _enrich_with_skos(all_categories, concepts, lang)
    else:
        # Just add category paths without SKOS
        for category_path in all_categories:
            _add_category_path(concepts, category_path)

    return concepts


def _enrich_with_skos(
    categories: set[str],
    existing_concepts: dict[str, Concept],
    lang: str,
) -> dict[str, Concept]:
    """Enrich categories with SKOS lookups.

    Args:
        categories: Set of category paths to look up.
        existing_concepts: Existing concepts (from local vocabulary).
        lang: Language code for SKOS lookups.

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
    client = skos.SKOSClient()

    # Extract leaf labels to look up (last part of each path)
    labels_to_lookup: dict[str, set[str]] = {}  # label -> set of full paths
    for cat_path in categories:
        # Get the leaf label (last part of path)
        leaf = cat_path.split("/")[-1]
        # Normalize: replace - and _ with space for lookup
        lookup_label = leaf.replace("-", " ").replace("_", " ")
        if lookup_label not in labels_to_lookup:
            labels_to_lookup[lookup_label] = set()
        labels_to_lookup[lookup_label].add(cat_path)

    logger.info("Looking up %d unique labels in SKOS...", len(labels_to_lookup))
    skos_found = 0
    skos_not_found = 0

    for label, paths in labels_to_lookup.items():
        # Skip if already in local vocab
        if label.lower() in [c.prefLabel.lower() for c in concepts.values()]:
            continue

        # Try SKOS lookup
        concept_data = client.lookup_concept(label, lang=lang, source="agrovoc")
        if not concept_data or not concept_data.get("uri"):
            # Try DBpedia
            concept_data = client.lookup_concept(label, lang=lang, source="dbpedia")

        if concept_data and concept_data.get("uri"):
            skos_found += 1
            # Create concept from SKOS data
            pref_label = concept_data.get("prefLabel", label)
            broader_data = concept_data.get("broader", [])

            # Build broader list from SKOS hierarchy
            broader_ids = []
            for b in broader_data[:3]:  # Limit to first 3 broader concepts
                broader_label = b.get("label", "").lower().replace(" ", "_")
                if broader_label:
                    broader_ids.append(broader_label)

            # Add the concept for each path that uses this label
            for cat_path in paths:
                if cat_path not in concepts:
                    concepts[cat_path] = Concept(
                        id=cat_path,
                        prefLabel=pref_label,
                        altLabels=[],
                        broader=broader_ids[:1] if broader_ids else [],  # Just first broader
                        narrower=[],
                        source=concept_data.get("source", "skos"),
                    )

                # Also add broader concepts
                for broader_id in broader_ids:
                    if broader_id not in concepts:
                        concepts[broader_id] = Concept(
                            id=broader_id,
                            prefLabel=broader_id.replace("_", " ").title(),
                            source="skos",
                        )
        else:
            skos_not_found += 1
            # Fall back to adding path without SKOS enrichment
            for cat_path in paths:
                _add_category_path(concepts, cat_path)

    logger.info("SKOS lookup complete: %d found, %d not found", skos_found, skos_not_found)
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


def save_vocabulary_json(vocabulary: dict[str, Concept], output_path: Path) -> None:
    """Save vocabulary as JSON file for search.html.

    Args:
        vocabulary: Dictionary of concepts.
        output_path: Path to write vocabulary.json.
    """
    tree = build_category_tree(vocabulary)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(tree.to_dict(), f, ensure_ascii=False, indent=2)


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
