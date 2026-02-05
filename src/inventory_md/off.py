"""Open Food Facts taxonomy client for food category lookups.

Uses the openfoodfacts PyPI package to access the OFF category taxonomy
(~14K category nodes) with localized names, synonyms, and hierarchy navigation.

No SPARQL or custom parser needed - the package handles download, caching,
and navigation.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Mapping from OFF top-level categories to user-friendly root labels.
# OFF top-level nodes like "Plant-based foods and beverages" are verbose;
# we map them to concise roots matching the existing AGROVOC pattern.
OFF_ROOT_MAPPING: dict[str, str] = {
    "plant-based foods and beverages": "food",
    "plant-based foods": "food",
    "animal-based foods": "food",
    "beverages": "food",
    "dairies": "food",
    "meats": "food",
    "seafood": "food",
    "cereals and potatoes": "food",
    "cereals and their products": "food",
    "fats": "food",
    "sugary snacks": "food",
    "salty snacks": "food",
    "snacks": "food",
    "meals": "food",
    "breakfasts": "food",
    "desserts": "food",
    "spreads": "food",
    "sweeteners": "food",
    "condiments": "food",
    "sauces": "food",
    "baby foods": "food",
    "dietary supplements": "food",
    "frozen foods": "food",
    "canned foods": "food",
    "dried products": "food",
    "fried foods": "food",
    "groceries": "food",
    "food additives": "food",
    "ingredients": "food",
}

# Words that are variations of the same concept and should be collapsed
_SIMILAR_WORDS: dict[str, str] = {
    "foods": "food",
    "food": "food",
    "beverages": "beverages",
    "drinks": "beverages",
}


def _normalize_path(path_parts: list[str]) -> list[str]:
    """Normalize a path by collapsing consecutive similar components.

    For example:
        ["food", "food", "condiments"] -> ["food", "condiments"]
        ["food", "foods", "prepared_foods"] -> ["food", "prepared_foods"]

    Args:
        path_parts: List of path component strings.

    Returns:
        Normalized path with consecutive similar components collapsed.
    """
    if not path_parts:
        return path_parts

    result = [path_parts[0]]

    for part in path_parts[1:]:
        prev = result[-1]
        # Check if current part is similar to previous (both map to same base)
        prev_base = _SIMILAR_WORDS.get(prev, prev)
        curr_base = _SIMILAR_WORDS.get(part, part)

        # Skip if it's a duplicate or variation of the previous component
        if prev_base == curr_base:
            continue
        # Also skip if the current part starts with the previous (e.g., "food" followed by "foods")
        if part.startswith(prev) or prev.startswith(part):
            continue

        result.append(part)

    return result


def _find_orig_index(orig_path: list[str], norm_path: list[str], norm_idx: int) -> int | None:
    """Find the original path index corresponding to a normalized path index.

    Args:
        orig_path: Original path components.
        norm_path: Normalized path components.
        norm_idx: Index in normalized path.

    Returns:
        Corresponding index in original path, or None if not found.
    """
    if norm_idx >= len(norm_path):
        return None

    target = norm_path[norm_idx]
    count = 0
    for i, part in enumerate(orig_path):
        # Check if this part normalizes to the target
        if part == target or _SIMILAR_WORDS.get(part, part) == target:
            if count == norm_idx:
                return i
            count += 1

    return None


class OFFTaxonomyClient:
    """Client for Open Food Facts category taxonomy lookups.

    Lazily loads the taxonomy on first use and builds a reverse label index
    for O(1) lookups by name or synonym.
    """

    def __init__(self, languages: list[str] | None = None):
        """Initialize the OFF taxonomy client.

        Args:
            languages: Languages to index for label lookups.
                       Defaults to ["en"].
        """
        self._taxonomy = None
        self._label_index: dict[str, str] | None = None
        self._languages = languages or ["en"]

    def _get_taxonomy(self):
        """Lazily load the OFF category taxonomy.

        Returns:
            Taxonomy object, or None if openfoodfacts is not installed.
        """
        if self._taxonomy is not None:
            return self._taxonomy

        try:
            from openfoodfacts.taxonomy import get_taxonomy
        except ImportError:
            logger.warning(
                "openfoodfacts package not installed. "
                "Install with: pip install inventory-md[off]"
            )
            return None

        logger.info("Loading Open Food Facts category taxonomy...")
        self._taxonomy = get_taxonomy("category")
        logger.info("OFF taxonomy loaded: %d categories", len(self._taxonomy))
        return self._taxonomy

    def _build_label_index(self) -> dict[str, str]:
        """Build reverse index: lowercase label -> node ID.

        Indexes all names and synonyms across configured languages.
        Built once on first lookup, then cached.

        Returns:
            Dict mapping lowercase label strings to OFF node IDs.
        """
        if self._label_index is not None:
            return self._label_index

        taxonomy = self._get_taxonomy()
        if taxonomy is None:
            self._label_index = {}
            return self._label_index

        index: dict[str, str] = {}
        # Use iter_nodes() - iterating directly yields None values
        for node in taxonomy.iter_nodes():
            if node is None:
                continue
            node_id = node.id

            # Index names in configured languages
            for lang in self._languages:
                name = node.names.get(lang)
                if name:
                    index[name.lower()] = node_id

            # Index synonyms in configured languages
            for lang in self._languages:
                syns = node.synonyms.get(lang, [])
                for syn in syns:
                    key = syn.lower()
                    # Don't overwrite a name entry with a synonym
                    if key not in index:
                        index[key] = node_id

        self._label_index = index
        logger.info("OFF label index built: %d entries", len(index))
        return self._label_index

    def lookup_concept(self, label: str, lang: str = "en") -> dict[str, Any] | None:
        """Look up a concept by label in the OFF taxonomy.

        Tries exact match, then singular/plural variations.

        Args:
            label: Label to search for (e.g., "soy sauce").
            lang: Language code for the label.

        Returns:
            Dict matching SKOSClient.lookup_concept() format:
            {"uri": "off:en:soy-sauces", "prefLabel": "Soy sauces",
             "source": "off", "broader": [...]}
            or None if not found.
        """
        taxonomy = self._get_taxonomy()
        if taxonomy is None:
            return None

        index = self._build_label_index()
        label_lower = label.lower().strip()

        # Try exact match
        node_id = index.get(label_lower)

        # Try singular/plural variations if not found
        if node_id is None:
            node_id = self._try_variations(label_lower)

        if node_id is None:
            return None

        node = taxonomy[node_id]
        pref_label = node.get_localized_name(lang)
        # If get_localized_name returns the node ID (fallback), try English
        if pref_label == node_id and lang != "en":
            en_name = node.names.get("en")
            if en_name:
                pref_label = en_name

        # Build broader list from parents
        broader = []
        for parent in node.parents:
            parent_label = parent.get_localized_name(lang)
            if parent_label == parent.id and lang != "en":
                en_name = parent.names.get("en")
                if en_name:
                    parent_label = en_name
            broader.append({
                "uri": f"off:{parent.id}",
                "label": parent_label,
            })

        return {
            "uri": f"off:{node_id}",
            "prefLabel": pref_label,
            "source": "off",
            "broader": broader,
            "node_id": node_id,
        }

    def _try_variations(self, label_lower: str) -> str | None:
        """Try singular/plural variations of a label.

        Args:
            label_lower: Lowercase label to try variations of.

        Returns:
            Node ID if found, None otherwise.
        """
        index = self._build_label_index()
        variations = _generate_variations(label_lower)

        for var in variations:
            if var in index:
                return index[var]

        return None

    def get_labels(self, node_id: str, languages: list[str]) -> dict[str, str]:
        """Get localized labels for a taxonomy node.

        Reads directly from node.names - no network calls needed.

        Args:
            node_id: OFF node ID (e.g., "en:soy-sauces").
            languages: List of language codes to fetch.

        Returns:
            Dict mapping language code to label string.
        """
        taxonomy = self._get_taxonomy()
        if taxonomy is None or node_id not in taxonomy:
            return {}

        node = taxonomy[node_id]
        labels: dict[str, str] = {}
        for lang in languages:
            name = node.names.get(lang)
            if name:
                labels[lang] = name

        return labels

    def build_paths_to_root(
        self, node_id: str, lang: str = "en"
    ) -> tuple[list[str], dict[str, str]]:
        """Build all hierarchy paths from root to a node.

        Returns paths matching the AGROVOC interface format.
        OFF is a DAG, so multiple paths may exist (e.g., "Soy sauces"
        under both "Condiments" and "Sauces").

        Args:
            node_id: OFF node ID (e.g., "en:soy-sauces").
            lang: Language code for path labels.

        Returns:
            Tuple of (list of path strings, dict of concept_id -> OFF URI).
            Paths use "/" separators like "food/condiments/sauces/soy_sauces".
        """
        taxonomy = self._get_taxonomy()
        if taxonomy is None or node_id not in taxonomy:
            return [], {}

        node = taxonomy[node_id]
        paths: list[list[str]] = []
        uri_map: dict[str, str] = {}

        self._collect_paths(node, lang, [], [], paths, uri_map, set())

        # Normalize paths: collapse consecutive similar components
        # e.g., ["food", "food", "condiments"] -> ["food", "condiments"]
        # e.g., ["food", "foods", "prepared_foods"] -> ["food", "prepared_foods"]
        normalized_paths = []
        for path_parts in paths:
            normalized = _normalize_path(path_parts)
            normalized_paths.append(normalized)

        # Rebuild uri_map for normalized paths
        normalized_uri_map: dict[str, str] = {}
        for path_parts, orig_path in zip(normalized_paths, paths):
            # Map original node IDs to normalized concept IDs
            for i in range(len(path_parts)):
                concept_id = "/".join(path_parts[: i + 1])
                if concept_id not in normalized_uri_map:
                    # Find the corresponding original node ID
                    # We need to track which original index maps to this normalized index
                    orig_idx = _find_orig_index(orig_path, path_parts, i)
                    if orig_idx is not None and f"off:{orig_path[orig_idx]}" in str(uri_map.values()):
                        # Find the URI from original path
                        orig_concept = "/".join(orig_path[: orig_idx + 1])
                        if orig_concept in uri_map:
                            normalized_uri_map[concept_id] = uri_map[orig_concept]

        # Convert path lists to path strings
        result_paths = []
        for path_parts in normalized_paths:
            result_paths.append("/".join(path_parts))

        return result_paths, normalized_uri_map if normalized_uri_map else uri_map

    def _collect_paths(
        self,
        node,
        lang: str,
        current_path: list[str],
        current_ids: list[str],
        all_paths: list[list[str]],
        uri_map: dict[str, str],
        visited: set[str],
    ) -> None:
        """Recursively collect all paths from a node to roots.

        Args:
            node: Current TaxonomyNode.
            lang: Language code for labels.
            current_path: Path components collected so far (leaf to current).
            current_ids: Node IDs corresponding to path components.
            all_paths: Accumulator for complete paths.
            uri_map: Accumulator for concept_id -> URI mappings.
            visited: Set of visited node IDs to avoid cycles.
        """
        if node.id in visited:
            return
        visited = visited | {node.id}  # Copy to allow branching

        # Get label for this node
        label = self._node_label(node, lang)
        label_normalized = label.lower().replace(" ", "_").replace("-", "_")

        new_path = [label_normalized] + current_path
        new_ids = [node.id] + current_ids

        if not node.parents:
            # Reached a root - apply mapping
            root_label = label.lower()
            if root_label in OFF_ROOT_MAPPING:
                new_path[0] = OFF_ROOT_MAPPING[root_label]
            # Build uri_map entries for this path
            for i in range(len(new_path)):
                concept_id = "/".join(new_path[: i + 1])
                if concept_id not in uri_map:
                    uri_map[concept_id] = f"off:{new_ids[i]}"
            all_paths.append(new_path)
            return

        for parent in node.parents:
            self._collect_paths(
                parent, lang, new_path, new_ids, all_paths, uri_map, visited
            )

    def _node_label(self, node, lang: str) -> str:
        """Get a human-readable label for a node.

        Args:
            node: TaxonomyNode.
            lang: Preferred language code.

        Returns:
            Label string.
        """
        name = node.names.get(lang)
        if name:
            return name
        # Fall back to English
        en_name = node.names.get("en")
        if en_name:
            return en_name
        # Last resort: extract from node ID
        # e.g., "en:soy-sauces" -> "Soy sauces"
        return node.id.split(":", 1)[-1].replace("-", " ").title()


def _generate_variations(label: str) -> list[str]:
    """Generate singular/plural variations of a label.

    Args:
        label: Lowercase label.

    Returns:
        List of variation strings to try (excluding the original).
    """
    variations = []

    # Plural -> singular
    if label.endswith("ies") and len(label) > 4:
        variations.append(label[:-3] + "y")
    elif label.endswith("oes") and len(label) > 4:
        variations.append(label[:-2])
    elif label.endswith("es") and len(label) > 3:
        stem = label[:-2]
        if stem.endswith(("s", "x", "z", "ch", "sh")):
            variations.append(stem)
        else:
            variations.append(label[:-1])  # Just remove trailing 's'
    elif label.endswith("s") and not label.endswith(("ss", "us", "is")):
        variations.append(label[:-1])

    # Singular -> plural
    if not label.endswith("s"):
        if label.endswith("y") and len(label) > 2 and label[-2] not in "aeiou":
            variations.append(label[:-1] + "ies")
        elif label.endswith(("s", "x", "z", "ch", "sh", "o")):
            variations.append(label + "es")
        else:
            variations.append(label + "s")

    return variations
