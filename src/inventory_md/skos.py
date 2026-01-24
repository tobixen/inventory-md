"""
SKOS (Simple Knowledge Organization System) support for tag hierarchies.

Provides on-demand lookup of concepts from SKOS vocabularies (AGROVOC, DBpedia)
with local caching. Used to expand user tags into hierarchical paths.

Example:
    >>> from inventory_md.skos import SKOSClient
    >>> client = SKOSClient()
    >>> client.expand_tag("potatoes")
    ['food/vegetables/potatoes', 'food/staples/potatoes']
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

logger = logging.getLogger(__name__)


# SPARQL endpoints
ENDPOINTS = {
    "agrovoc": "https://agrovoc.fao.org/sparql",
    "dbpedia": "https://dbpedia.org/sparql",
}

# Cache settings
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "inventory-md" / "skos"
CACHE_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days
DEFAULT_TIMEOUT = 30.0  # SPARQL endpoints can be slow


def _get_cache_path(cache_dir: Path, key: str) -> Path:
    """Get cache file path for a lookup key."""
    # Use hash to avoid filesystem issues with special characters
    key_hash = hashlib.sha256(key.encode()).hexdigest()[:16]
    safe_key = "".join(c if c.isalnum() else "_" for c in key[:50])
    return cache_dir / f"{safe_key}_{key_hash}.json"


def _load_from_cache(cache_path: Path, ttl: int = CACHE_TTL_SECONDS) -> dict | None:
    """Load cached data if it exists and is not expired."""
    if not cache_path.exists():
        return None
    try:
        with open(cache_path, encoding="utf-8") as f:
            data = json.load(f)
        # Check TTL
        if time.time() - data.get("_cached_at", 0) > ttl:
            return None
        return data
    except (json.JSONDecodeError, OSError) as e:
        logger.debug("Cache read failed for %s: %s", cache_path, e)
        return None


def _save_to_cache(cache_path: Path, data: dict) -> None:
    """Save data to cache."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    data["_cached_at"] = time.time()
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError as e:
        logger.warning("Cache write failed for %s: %s", cache_path, e)


class SKOSClient:
    """Client for querying SKOS vocabularies with caching."""

    def __init__(
        self,
        cache_dir: Path | None = None,
        endpoints: dict[str, str] | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        enabled_sources: list[str] | None = None,
    ):
        """Initialize SKOS client.

        Args:
            cache_dir: Directory for cached lookups. Default: ~/.cache/inventory-md/skos/
            endpoints: Custom SPARQL endpoints. Default: AGROVOC and DBpedia.
            timeout: Request timeout in seconds.
            enabled_sources: List of sources to query. Default: ["agrovoc", "dbpedia"]
        """
        self.cache_dir = cache_dir or DEFAULT_CACHE_DIR
        self.endpoints = endpoints or ENDPOINTS.copy()
        self.timeout = timeout
        self.enabled_sources = enabled_sources or ["agrovoc", "dbpedia"]

    def _sparql_query(self, endpoint: str, query: str) -> list[dict]:
        """Execute a SPARQL query and return results.

        Args:
            endpoint: SPARQL endpoint URL.
            query: SPARQL query string.

        Returns:
            List of result bindings (dicts with variable names as keys).
        """
        try:
            import requests
        except ImportError as e:
            raise ImportError(
                "requests required for SKOS lookups. "
                "Install with: pip install inventory-md[skos]"
            ) from e

        headers = {"Accept": "application/sparql-results+json"}
        params = {"query": query, "format": "json"}

        try:
            response = requests.get(
                endpoint, params=params, headers=headers, timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()
            return data.get("results", {}).get("bindings", [])
        except requests.RequestException as e:
            logger.warning("SPARQL query failed for %s: %s", endpoint, e)
            return []

    def lookup_concept(
        self, label: str, lang: str = "en", source: str = "agrovoc"
    ) -> dict | None:
        """Look up a concept by label.

        Args:
            label: The label to search for (e.g., "potatoes").
            lang: Language code for label matching.
            source: Which source to query ("agrovoc" or "dbpedia").

        Returns:
            Concept data dict with uri, prefLabel, altLabels, broader, narrower,
            or None if not found.
        """
        cache_key = f"concept:{source}:{lang}:{label.lower()}"
        cache_path = _get_cache_path(self.cache_dir, cache_key)

        # Check cache
        cached = _load_from_cache(cache_path)
        if cached is not None:
            return cached if cached.get("uri") else None

        # Query the appropriate endpoint
        if source == "agrovoc":
            concept = self._lookup_agrovoc(label, lang)
        elif source == "dbpedia":
            concept = self._lookup_dbpedia(label, lang)
        else:
            logger.warning("Unknown source: %s", source)
            return None

        # Cache result (even if None, to avoid repeated lookups)
        _save_to_cache(cache_path, concept or {"uri": None})
        return concept

    def _lookup_agrovoc(self, label: str, lang: str) -> dict | None:
        """Look up concept in AGROVOC."""
        endpoint = self.endpoints.get("agrovoc")
        if not endpoint:
            return None

        # First, find the concept URI by label
        query = f"""
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        PREFIX skosxl: <http://www.w3.org/2008/05/skos-xl#>

        SELECT DISTINCT ?concept ?prefLabel WHERE {{
            {{
                ?concept skosxl:prefLabel/skosxl:literalForm ?label .
                FILTER(lcase(str(?label)) = "{label.lower()}"@{lang} || lcase(str(?label)) = "{label.lower()}")
            }} UNION {{
                ?concept skosxl:altLabel/skosxl:literalForm ?label .
                FILTER(lcase(str(?label)) = "{label.lower()}"@{lang} || lcase(str(?label)) = "{label.lower()}")
            }}
            ?concept skosxl:prefLabel/skosxl:literalForm ?prefLabel .
            FILTER(lang(?prefLabel) = "{lang}" || lang(?prefLabel) = "")
        }}
        LIMIT 1
        """

        results = self._sparql_query(endpoint, query)
        if not results:
            return None

        concept_uri = results[0]["concept"]["value"]
        pref_label = results[0].get("prefLabel", {}).get("value", label)

        # Get broader concepts (hierarchy)
        broader = self._get_broader_agrovoc(concept_uri, lang)

        return {
            "uri": concept_uri,
            "prefLabel": pref_label,
            "source": "agrovoc",
            "broader": broader,
        }

    def _get_broader_agrovoc(self, concept_uri: str, lang: str) -> list[dict]:
        """Get broader (parent) concepts from AGROVOC."""
        endpoint = self.endpoints.get("agrovoc")
        if not endpoint:
            return []

        query = f"""
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        PREFIX skosxl: <http://www.w3.org/2008/05/skos-xl#>

        SELECT ?broader ?label WHERE {{
            <{concept_uri}> skos:broader+ ?broader .
            ?broader skosxl:prefLabel/skosxl:literalForm ?label .
            FILTER(lang(?label) = "{lang}" || lang(?label) = "")
        }}
        """

        results = self._sparql_query(endpoint, query)
        return [
            {"uri": r["broader"]["value"], "label": r["label"]["value"]}
            for r in results
        ]

    def _lookup_dbpedia(self, label: str, lang: str) -> dict | None:
        """Look up concept in DBpedia."""
        endpoint = self.endpoints.get("dbpedia")
        if not endpoint:
            return None

        # DBpedia uses Wikipedia article names, try to find matching resource
        query = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX dct: <http://purl.org/dc/terms/>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        PREFIX dbo: <http://dbpedia.org/ontology/>

        SELECT DISTINCT ?resource ?label ?category WHERE {{
            ?resource rdfs:label ?label .
            FILTER(lcase(str(?label)) = "{label.lower()}"@{lang})
            OPTIONAL {{ ?resource dct:subject ?category }}
        }}
        LIMIT 1
        """

        results = self._sparql_query(endpoint, query)
        if not results:
            return None

        resource_uri = results[0]["resource"]["value"]
        pref_label = results[0].get("label", {}).get("value", label)

        # Get category hierarchy
        broader = self._get_broader_dbpedia(resource_uri, lang)

        return {
            "uri": resource_uri,
            "prefLabel": pref_label,
            "source": "dbpedia",
            "broader": broader,
        }

    def _get_broader_dbpedia(self, resource_uri: str, lang: str) -> list[dict]:
        """Get broader (parent) categories from DBpedia."""
        endpoint = self.endpoints.get("dbpedia")
        if not endpoint:
            return []

        # Get categories and their parent categories
        query = f"""
        PREFIX dct: <http://purl.org/dc/terms/>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT DISTINCT ?category ?label WHERE {{
            <{resource_uri}> dct:subject/skos:broader* ?category .
            ?category rdfs:label ?label .
            FILTER(lang(?label) = "{lang}")
        }}
        LIMIT 20
        """

        results = self._sparql_query(endpoint, query)
        return [
            {"uri": r["category"]["value"], "label": r["label"]["value"]}
            for r in results
        ]

    def get_hierarchy_path(self, concept: dict) -> list[str]:
        """Build hierarchy path(s) from a concept's broader relations.

        Args:
            concept: Concept dict with 'prefLabel' and 'broader' list.

        Returns:
            List of hierarchy paths like ["food/vegetables/potatoes"].
        """
        if not concept or not concept.get("broader"):
            return [concept["prefLabel"]] if concept else []

        # Build paths from broader concepts
        paths = []
        label = concept["prefLabel"].lower().replace(" ", "_")

        # Group broader concepts and build simple paths
        broader_labels = [b["label"].lower().replace(" ", "_") for b in concept["broader"]]

        if broader_labels:
            # Create paths with broader concepts
            for broader in broader_labels[:5]:  # Limit to avoid too many paths
                paths.append(f"{broader}/{label}")

        if not paths:
            paths = [label]

        return paths

    def expand_tag(self, tag: str, lang: str = "en") -> list[str]:
        """Expand a tag to its hierarchical paths.

        Queries enabled SKOS sources and returns hierarchy paths.

        Args:
            tag: The tag to expand (e.g., "potatoes").
            lang: Language code for lookups.

        Returns:
            List of hierarchical paths (e.g., ["food/vegetables/potatoes"]).
            Returns [tag] if no hierarchy found.
        """
        all_paths = []

        for source in self.enabled_sources:
            concept = self.lookup_concept(tag, lang=lang, source=source)
            if concept and concept.get("uri"):
                paths = self.get_hierarchy_path(concept)
                all_paths.extend(paths)

        # Deduplicate and return
        seen = set()
        unique_paths = []
        for path in all_paths:
            if path not in seen:
                seen.add(path)
                unique_paths.append(path)

        return unique_paths if unique_paths else [tag.lower().replace(" ", "_")]

    def expand_tags(self, tags: list[str], lang: str = "en") -> dict[str, list[str]]:
        """Expand multiple tags to their hierarchical paths.

        Args:
            tags: List of tags to expand.
            lang: Language code for lookups.

        Returns:
            Dict mapping each tag to its list of hierarchical paths.
        """
        return {tag: self.expand_tag(tag, lang=lang) for tag in tags}

    def clear_cache(self) -> int:
        """Clear all cached lookups.

        Returns:
            Number of cache files deleted.
        """
        if not self.cache_dir.exists():
            return 0

        count = 0
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                cache_file.unlink()
                count += 1
            except OSError:
                pass
        return count


# Convenience functions for simple usage
_default_client: SKOSClient | None = None


def get_client(**kwargs) -> SKOSClient:
    """Get or create the default SKOS client."""
    global _default_client
    if _default_client is None or kwargs:
        _default_client = SKOSClient(**kwargs)
    return _default_client


def expand_tag(tag: str, lang: str = "en") -> list[str]:
    """Expand a tag to hierarchical paths using the default client.

    Args:
        tag: The tag to expand.
        lang: Language code.

    Returns:
        List of hierarchical paths.
    """
    return get_client().expand_tag(tag, lang=lang)


def expand_tags(tags: list[str], lang: str = "en") -> dict[str, list[str]]:
    """Expand multiple tags using the default client.

    Args:
        tags: List of tags to expand.
        lang: Language code.

    Returns:
        Dict mapping each tag to its hierarchical paths.
    """
    return get_client().expand_tags(tags, lang=lang)
