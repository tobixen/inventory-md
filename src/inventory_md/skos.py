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

# REST API endpoints (Skosmos)
REST_ENDPOINTS = {
    "agrovoc": "https://agrovoc.fao.org/browse/rest/v1",
}

# Cache settings
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "inventory-md" / "skos"
CACHE_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days
DEFAULT_TIMEOUT = 300.0  # SPARQL endpoints can be slow

# Default path for local AGROVOC data
DEFAULT_AGROVOC_PATH = DEFAULT_CACHE_DIR / "agrovoc.nt"


class OxigraphStore:
    """Local SKOS store using Oxigraph (pyoxigraph).

    Loads RDF data from N-Triples files and provides SPARQL query access.
    Much faster than remote SPARQL endpoints for local lookups.

    Example:
        >>> store = OxigraphStore()
        >>> store.load("/path/to/agrovoc.nt")
        >>> results = store.query("SELECT ?s WHERE { ?s a skos:Concept } LIMIT 10")
    """

    def __init__(self, persistent_path: Path | None = None):
        """Initialize Oxigraph store.

        Args:
            persistent_path: If provided, use persistent storage at this path.
                            Otherwise, use in-memory storage.
        """
        try:
            import pyoxigraph
        except ImportError as e:
            raise ImportError(
                "pyoxigraph required for local SKOS store. "
                "Install with: pip install pyoxigraph"
            ) from e

        self._pyoxigraph = pyoxigraph
        if persistent_path:
            persistent_path.parent.mkdir(parents=True, exist_ok=True)
            self._store = pyoxigraph.Store(str(persistent_path))
        else:
            self._store = pyoxigraph.Store()

        self._loaded_files: set[str] = set()

    def load(self, path: Path | str, format: str | None = None) -> int:
        """Load RDF data from a file.

        Args:
            path: Path to RDF file (N-Triples, Turtle, RDF/XML, etc.)
            format: RDF format. Auto-detected from extension if not provided.
                   Supported: "nt" (N-Triples), "ttl" (Turtle), "rdf" (RDF/XML)

        Returns:
            Number of triples loaded.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"RDF file not found: {path}")

        # Track loaded files to avoid reloading
        path_str = str(path.resolve())
        if path_str in self._loaded_files:
            logger.debug("File already loaded: %s", path)
            return 0

        # Auto-detect format from extension
        if format is None:
            suffix = path.suffix.lower()
            format_map = {
                ".nt": self._pyoxigraph.RdfFormat.N_TRIPLES,
                ".ntriples": self._pyoxigraph.RdfFormat.N_TRIPLES,
                ".ttl": self._pyoxigraph.RdfFormat.TURTLE,
                ".turtle": self._pyoxigraph.RdfFormat.TURTLE,
                ".rdf": self._pyoxigraph.RdfFormat.RDF_XML,
                ".xml": self._pyoxigraph.RdfFormat.RDF_XML,
                ".nq": self._pyoxigraph.RdfFormat.N_QUADS,
            }
            rdf_format = format_map.get(suffix, self._pyoxigraph.RdfFormat.N_TRIPLES)
        else:
            format_map = {
                "nt": self._pyoxigraph.RdfFormat.N_TRIPLES,
                "ttl": self._pyoxigraph.RdfFormat.TURTLE,
                "rdf": self._pyoxigraph.RdfFormat.RDF_XML,
                "nq": self._pyoxigraph.RdfFormat.N_QUADS,
            }
            rdf_format = format_map.get(format, self._pyoxigraph.RdfFormat.N_TRIPLES)

        logger.info("Loading RDF data from %s (format: %s)...", path, rdf_format)
        initial_count = len(self._store)

        with open(path, "rb") as f:
            self._store.load(f, rdf_format)

        loaded = len(self._store) - initial_count
        self._loaded_files.add(path_str)
        logger.info("Loaded %d triples from %s (total: %d)", loaded, path, len(self._store))
        return loaded

    def query(self, sparql: str) -> list[dict]:
        """Execute a SPARQL SELECT query.

        Args:
            sparql: SPARQL SELECT query string.

        Returns:
            List of result bindings (dicts mapping variable names to values).
        """
        query_results = self._store.query(sparql)
        variables = query_results.variables

        results = []
        for solution in query_results:
            row = {}
            for var in variables:
                value = solution[var]
                if value is not None:
                    # Convert pyoxigraph types to simple dict format
                    var_name = var.value
                    if hasattr(value, "value"):
                        row[var_name] = {"value": value.value}
                        if hasattr(value, "language") and value.language:
                            row[var_name]["lang"] = value.language
                    else:
                        row[var_name] = {"value": str(value)}
            results.append(row)
        return results

    def __len__(self) -> int:
        """Return number of triples in store."""
        return len(self._store)

    @property
    def is_loaded(self) -> bool:
        """Check if any data has been loaded."""
        return len(self._store) > 0


# Global Oxigraph store instance (lazy-loaded)
_oxigraph_store: OxigraphStore | None = None


def get_oxigraph_store(
    agrovoc_path: Path | None = None,
    persistent_path: Path | None = None,
) -> OxigraphStore | None:
    """Get or create the global Oxigraph store with AGROVOC data.

    Args:
        agrovoc_path: Path to AGROVOC N-Triples file. Default: ~/.cache/inventory-md/skos/agrovoc.nt
        persistent_path: Path for persistent Oxigraph storage. Default: in-memory.

    Returns:
        OxigraphStore instance, or None if pyoxigraph not available or data file missing.
    """
    global _oxigraph_store

    if _oxigraph_store is not None:
        return _oxigraph_store

    agrovoc_path = agrovoc_path or DEFAULT_AGROVOC_PATH
    if not agrovoc_path.exists():
        logger.debug("AGROVOC data file not found: %s", agrovoc_path)
        return None

    try:
        _oxigraph_store = OxigraphStore(persistent_path=persistent_path)
        _oxigraph_store.load(agrovoc_path)
        return _oxigraph_store
    except ImportError:
        logger.debug("pyoxigraph not available")
        return None
    except Exception as e:
        logger.warning("Failed to load Oxigraph store: %s", e)
        return None


def _get_cache_path(cache_dir: Path, key: str) -> Path:
    """Get cache file path for a lookup key."""
    # Use hash to avoid filesystem issues with special characters
    key_hash = hashlib.sha256(key.encode()).hexdigest()[:16]
    safe_key = "".join(c if c.isalnum() else "_" for c in key[:50])
    return cache_dir / f"{safe_key}_{key_hash}.json"


def _get_not_found_cache_path(cache_dir: Path) -> Path:
    """Get path to consolidated not-found cache file."""
    return cache_dir / "_not_found.json"


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


def _is_in_not_found_cache(cache_dir: Path, key: str, ttl: int = CACHE_TTL_SECONDS) -> bool:
    """Check if a key is in the not-found cache."""
    cache_path = _get_not_found_cache_path(cache_dir)
    if not cache_path.exists():
        return False
    try:
        with open(cache_path, encoding="utf-8") as f:
            data = json.load(f)
        entry = data.get("entries", {}).get(key)
        if entry is None:
            return False
        # Check TTL for this entry
        if time.time() - entry.get("cached_at", 0) > ttl:
            return False
        return True
    except (json.JSONDecodeError, OSError) as e:
        logger.debug("Not-found cache read failed: %s", e)
        return False


def _add_to_not_found_cache(cache_dir: Path, key: str) -> None:
    """Add a key to the consolidated not-found cache."""
    cache_path = _get_not_found_cache_path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Load existing data
    data = {"entries": {}}
    if cache_path.exists():
        try:
            with open(cache_path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            data = {"entries": {}}

    # Add new entry
    if "entries" not in data:
        data["entries"] = {}
    data["entries"][key] = {"cached_at": time.time()}

    # Save
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError as e:
        logger.warning("Not-found cache write failed: %s", e)


class SKOSClient:
    """Client for querying SKOS vocabularies with caching."""

    def __init__(
        self,
        cache_dir: Path | None = None,
        endpoints: dict[str, str] | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        enabled_sources: list[str] | None = None,
        use_rest_api: bool = True,
        rest_endpoints: dict[str, str] | None = None,
        oxigraph_store: OxigraphStore | None = None,
        use_oxigraph: bool = True,
        agrovoc_path: Path | None = None,
    ):
        """Initialize SKOS client.

        Args:
            cache_dir: Directory for cached lookups. Default: ~/.cache/inventory-md/skos/
            endpoints: Custom SPARQL endpoints. Default: AGROVOC and DBpedia.
            timeout: Request timeout in seconds.
            enabled_sources: List of sources to query. Default: ["agrovoc", "dbpedia"]
            use_rest_api: If True, prefer REST API over SPARQL for AGROVOC (faster).
            rest_endpoints: Custom REST API endpoints. Default: AGROVOC Skosmos.
            oxigraph_store: Optional pre-loaded OxigraphStore for local AGROVOC lookups.
            use_oxigraph: If True, try to use local Oxigraph store for AGROVOC (fastest).
            agrovoc_path: Path to AGROVOC N-Triples file for Oxigraph. Default: auto-detect.
        """
        self.cache_dir = cache_dir or DEFAULT_CACHE_DIR
        self.endpoints = endpoints or ENDPOINTS.copy()
        self.timeout = timeout
        self.enabled_sources = enabled_sources or ["agrovoc", "dbpedia"]
        self.use_rest_api = use_rest_api
        self.rest_endpoints = rest_endpoints or REST_ENDPOINTS.copy()
        self.use_oxigraph = use_oxigraph
        self.agrovoc_path = agrovoc_path

        # Use provided store or try to get global store
        if oxigraph_store is not None:
            self._oxigraph_store = oxigraph_store
        elif use_oxigraph:
            self._oxigraph_store = get_oxigraph_store(agrovoc_path=agrovoc_path)
        else:
            self._oxigraph_store = None

    def _rest_api_search(
        self, base_url: str, query: str, lang: str = "en"
    ) -> list[dict] | None:
        """Search for concepts via Skosmos REST API.

        Args:
            base_url: REST API base URL (e.g., https://agrovoc.fao.org/browse/rest/v1)
            query: Search term.
            lang: Language code.

        Returns:
            List of search results, or None if request failed.
        """
        try:
            import requests
        except ImportError as e:
            raise ImportError(
                "requests required for SKOS lookups. "
                "Install with: pip install inventory-md[skos]"
            ) from e

        # Use exact match search (no wildcard for precision)
        url = f"{base_url}/search/"
        params = {"query": query, "lang": lang}

        try:
            response = requests.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            return data.get("results", [])
        except requests.Timeout as e:
            logger.warning("REST API search timed out for %s: %s", base_url, e)
            return None
        except requests.RequestException as e:
            logger.warning("REST API search failed for %s: %s", base_url, e)
            return None

    def _rest_api_get_concept(self, base_url: str, uri: str) -> dict | None:
        """Get concept data via Skosmos REST API.

        Args:
            base_url: REST API base URL.
            uri: Concept URI.

        Returns:
            Concept data dict, or None if request failed.
        """
        try:
            import requests
        except ImportError as e:
            raise ImportError(
                "requests required for SKOS lookups. "
                "Install with: pip install inventory-md[skos]"
            ) from e

        url = f"{base_url}/data/"
        params = {"uri": uri}

        try:
            response = requests.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.Timeout as e:
            logger.warning("REST API data fetch timed out for %s: %s", uri, e)
            return None
        except requests.RequestException as e:
            logger.warning("REST API data fetch failed for %s: %s", uri, e)
            return None

    def _sparql_query(self, endpoint: str, query: str) -> list[dict] | None:
        """Execute a SPARQL query and return results.

        Args:
            endpoint: SPARQL endpoint URL.
            query: SPARQL query string.

        Returns:
            List of result bindings (dicts with variable names as keys),
            or None if query failed due to timeout/network error.
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
        except requests.Timeout as e:
            logger.warning("SPARQL query timed out for %s: %s", endpoint, e)
            return None  # None = error, don't cache
        except requests.RequestException as e:
            logger.warning("SPARQL query failed for %s: %s", endpoint, e)
            return None  # None = error, don't cache

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
            or None if not found or query failed.
        """
        cache_key = f"concept:{source}:{lang}:{label.lower()}"
        cache_path = _get_cache_path(self.cache_dir, cache_key)

        # Check positive cache (found concepts)
        cached = _load_from_cache(cache_path)
        if cached is not None:
            return cached if cached.get("uri") else None

        # Check not-found cache (consolidated file for 404s)
        if _is_in_not_found_cache(self.cache_dir, cache_key):
            return None

        # Query the appropriate endpoint
        if source == "agrovoc":
            concept, query_failed = self._lookup_agrovoc(label, lang)
        elif source == "dbpedia":
            concept, query_failed = self._lookup_dbpedia(label, lang)
        else:
            logger.warning("Unknown source: %s", source)
            return None

        # Only cache if query succeeded (don't cache timeouts/errors)
        if not query_failed:
            if concept:
                # Found: save to individual cache file
                _save_to_cache(cache_path, concept)
            else:
                # Not found: add to consolidated not-found cache
                _add_to_not_found_cache(self.cache_dir, cache_key)

        return concept

    def _lookup_agrovoc(self, label: str, lang: str) -> tuple[dict | None, bool]:
        """Look up concept in AGROVOC.

        Priority: Oxigraph (local) > REST API > SPARQL (remote).

        Returns:
            Tuple of (concept_dict, query_failed). query_failed is True if
            the query timed out or had a network error.
        """
        # Try Oxigraph first if available (fastest - local)
        if self._oxigraph_store is not None and self._oxigraph_store.is_loaded:
            result = self._lookup_agrovoc_oxigraph(label, lang)
            if result is not None:
                return result
            # Oxigraph returned not found - this is authoritative, don't fall back
            logger.debug("Concept not found in local Oxigraph: %s", label)
            return None, False

        # Try REST API if enabled
        if self.use_rest_api:
            rest_base = self.rest_endpoints.get("agrovoc")
            if rest_base:
                result = self._lookup_agrovoc_rest(label, lang, rest_base)
                if result is not None:
                    return result
                # REST failed, fall back to SPARQL
                logger.debug("REST API failed, falling back to SPARQL for %s", label)

        return self._lookup_agrovoc_sparql(label, lang)

    def _lookup_agrovoc_oxigraph(self, label: str, lang: str) -> tuple[dict | None, bool] | None:
        """Look up concept in AGROVOC via local Oxigraph store.

        Returns:
            Tuple of (concept_dict, query_failed), or None if store not available.
        """
        if self._oxigraph_store is None:
            return None

        label_lower = label.lower()

        # Query for concept by prefLabel or altLabel (case-insensitive)
        # AGROVOC Core uses standard SKOS predicates
        query = f"""
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

        SELECT DISTINCT ?concept ?prefLabel WHERE {{
            {{
                ?concept skos:prefLabel ?label .
                FILTER(lcase(str(?label)) = "{label_lower}")
            }} UNION {{
                ?concept skos:altLabel ?label .
                FILTER(lcase(str(?label)) = "{label_lower}")
            }}
            ?concept skos:prefLabel ?prefLabel .
            FILTER(lang(?prefLabel) = "{lang}" || lang(?prefLabel) = "")
        }}
        LIMIT 1
        """

        try:
            results = self._oxigraph_store.query(query)
        except Exception as e:
            logger.warning("Oxigraph query failed: %s", e)
            return None  # Fall back to other methods

        if not results:
            return None, False  # Not found (but query succeeded)

        concept_uri = results[0]["concept"]["value"]
        pref_label = results[0].get("prefLabel", {}).get("value", label)

        # Get broader concepts
        broader = self._get_broader_agrovoc_oxigraph(concept_uri, lang)

        return {
            "uri": concept_uri,
            "prefLabel": pref_label,
            "source": "agrovoc",
            "broader": broader,
        }, False

    def _get_broader_agrovoc_oxigraph(self, concept_uri: str, lang: str) -> list[dict]:
        """Get broader concepts from local Oxigraph store."""
        if self._oxigraph_store is None:
            return []

        # Get transitive broader concepts
        query = f"""
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

        SELECT DISTINCT ?broader ?label WHERE {{
            <{concept_uri}> skos:broader+ ?broader .
            ?broader skos:prefLabel ?label .
            FILTER(lang(?label) = "{lang}" || lang(?label) = "")
        }}
        LIMIT 20
        """

        try:
            results = self._oxigraph_store.query(query)
            return [
                {"uri": r["broader"]["value"], "label": r["label"]["value"]}
                for r in results
            ]
        except Exception as e:
            logger.warning("Oxigraph broader query failed: %s", e)
            return []

    def _lookup_agrovoc_rest(
        self, label: str, lang: str, rest_base: str
    ) -> tuple[dict | None, bool] | None:
        """Look up concept in AGROVOC via REST API.

        Returns:
            Tuple of (concept_dict, query_failed), or None to fall back to SPARQL.
        """
        # Search for the concept
        results = self._rest_api_search(rest_base, label, lang)
        if results is None:
            return None  # Fall back to SPARQL

        if not results:
            return None, False  # Not found (but query succeeded)

        # Find best match (exact match preferred)
        label_lower = label.lower()
        best_match = None
        for result in results:
            match_label = result.get("prefLabel", "").lower()
            alt_labels = [a.lower() for a in result.get("altLabel", [])] if isinstance(
                result.get("altLabel"), list
            ) else []

            if match_label == label_lower or label_lower in alt_labels:
                best_match = result
                break

        if not best_match and results:
            # Use first result if no exact match
            best_match = results[0]

        if not best_match:
            return None, False

        concept_uri = best_match.get("uri")
        if not concept_uri:
            return None, False

        pref_label = best_match.get("prefLabel", label)

        # Get broader concepts via REST API
        broader = self._get_broader_agrovoc_rest(concept_uri, rest_base, lang)

        return {
            "uri": concept_uri,
            "prefLabel": pref_label,
            "source": "agrovoc",
            "broader": broader,
        }, False

    def _get_broader_agrovoc_rest(
        self, concept_uri: str, rest_base: str, lang: str
    ) -> list[dict]:
        """Get broader concepts via REST API."""
        concept_data = self._rest_api_get_concept(rest_base, concept_uri)
        if not concept_data:
            return []

        broader = []
        # The REST API returns concept data in JSON-LD format
        # Look for skos:broader in the graph
        graph = concept_data.get("graph", [])
        for item in graph:
            if item.get("uri") == concept_uri:
                broader_uris = item.get("broader", [])
                if isinstance(broader_uris, str):
                    broader_uris = [broader_uris]
                elif isinstance(broader_uris, list):
                    broader_uris = [
                        b.get("uri") if isinstance(b, dict) else b
                        for b in broader_uris
                    ]

                # Get labels for broader concepts
                for broader_uri in broader_uris:
                    if broader_uri:
                        # Find the label in the graph
                        for node in graph:
                            if node.get("uri") == broader_uri:
                                # Get prefLabel for the requested language
                                pref_labels = node.get("prefLabel", [])
                                if isinstance(pref_labels, str):
                                    broader.append({"uri": broader_uri, "label": pref_labels})
                                elif isinstance(pref_labels, list):
                                    for pl in pref_labels:
                                        if isinstance(pl, dict):
                                            if pl.get("lang") == lang or not pl.get("lang"):
                                                broader.append({
                                                    "uri": broader_uri,
                                                    "label": pl.get("value", "")
                                                })
                                                break
                                        elif isinstance(pl, str):
                                            broader.append({"uri": broader_uri, "label": pl})
                                            break
                                break
                break

        return broader

    def _lookup_agrovoc_sparql(self, label: str, lang: str) -> tuple[dict | None, bool]:
        """Look up concept in AGROVOC via SPARQL.

        Returns:
            Tuple of (concept_dict, query_failed). query_failed is True if
            the query timed out or had a network error.
        """
        endpoint = self.endpoints.get("agrovoc")
        if not endpoint:
            return None, False

        # First, find the concept URI by label (case-insensitive)
        label_lower = label.lower()
        query = f"""
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        PREFIX skosxl: <http://www.w3.org/2008/05/skos-xl#>

        SELECT DISTINCT ?concept ?prefLabel WHERE {{
            {{
                ?concept skosxl:prefLabel/skosxl:literalForm ?label .
                FILTER(lcase(str(?label)) = "{label_lower}")
            }} UNION {{
                ?concept skosxl:altLabel/skosxl:literalForm ?label .
                FILTER(lcase(str(?label)) = "{label_lower}")
            }}
            ?concept skosxl:prefLabel/skosxl:literalForm ?prefLabel .
            FILTER(lang(?prefLabel) = "{lang}" || lang(?prefLabel) = "")
        }}
        LIMIT 1
        """

        results = self._sparql_query(endpoint, query)
        if results is None:
            return None, True  # Query failed (timeout/error)
        if not results:
            return None, False  # Not found (but query succeeded)

        concept_uri = results[0]["concept"]["value"]
        pref_label = results[0].get("prefLabel", {}).get("value", label)

        # Get broader concepts (hierarchy)
        broader = self._get_broader_agrovoc(concept_uri, lang)

        return {
            "uri": concept_uri,
            "prefLabel": pref_label,
            "source": "agrovoc",
            "broader": broader,
        }, False

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
        if results is None:
            return []  # Query failed, return empty
        return [
            {"uri": r["broader"]["value"], "label": r["label"]["value"]}
            for r in results
        ]

    def _lookup_dbpedia(self, label: str, lang: str) -> tuple[dict | None, bool]:
        """Look up concept in DBpedia.

        Returns:
            Tuple of (concept_dict, query_failed). query_failed is True if
            the query timed out or had a network error.
        """
        endpoint = self.endpoints.get("dbpedia")
        if not endpoint:
            return None, False

        # DBpedia uses Wikipedia article names (Title Case)
        # Use exact match for performance - case-insensitive search is too slow
        label_title = label.title()  # "potato" -> "Potato"
        query = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX dct: <http://purl.org/dc/terms/>

        SELECT DISTINCT ?resource ?label ?category WHERE {{
            ?resource rdfs:label "{label_title}"@{lang} .
            ?resource rdfs:label ?label .
            FILTER(lang(?label) = "{lang}")
            OPTIONAL {{ ?resource dct:subject ?category }}
        }}
        LIMIT 1
        """

        results = self._sparql_query(endpoint, query)
        if results is None:
            return None, True  # Query failed (timeout/error)
        if not results:
            return None, False  # Not found (but query succeeded)

        resource_uri = results[0]["resource"]["value"]
        pref_label = results[0].get("label", {}).get("value", label)

        # Get category hierarchy
        broader = self._get_broader_dbpedia(resource_uri, lang)

        return {
            "uri": resource_uri,
            "prefLabel": pref_label,
            "source": "dbpedia",
            "broader": broader,
        }, False

    def _get_broader_dbpedia(self, resource_uri: str, lang: str) -> list[dict]:
        """Get direct categories from DBpedia (not broader hierarchy)."""
        endpoint = self.endpoints.get("dbpedia")
        if not endpoint:
            return []

        # Get direct categories only - traversing broader* is too slow and returns
        # very generic categories. Direct categories are more useful.
        query = f"""
        PREFIX dct: <http://purl.org/dc/terms/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT DISTINCT ?category ?label WHERE {{
            <{resource_uri}> dct:subject ?category .
            ?category rdfs:label ?label .
            FILTER(lang(?label) = "{lang}")
        }}
        LIMIT 10
        """

        results = self._sparql_query(endpoint, query)
        if results is None:
            return []  # Query failed, return empty
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

    def get_cache_stats(self) -> dict[str, Any]:
        """Get statistics about the cache and Oxigraph store.

        Returns:
            Dict with 'found', 'not_found' counts, and 'oxigraph_triples' if available.
        """
        stats: dict[str, Any] = {"found": 0, "not_found": 0}

        if self.cache_dir.exists():
            # Count individual concept files (excluding _not_found.json)
            stats["found"] = len([
                f for f in self.cache_dir.glob("*.json")
                if f.name != "_not_found.json"
            ])

            # Count entries in not-found cache
            not_found_path = _get_not_found_cache_path(self.cache_dir)
            if not_found_path.exists():
                try:
                    with open(not_found_path, encoding="utf-8") as f:
                        data = json.load(f)
                    stats["not_found"] = len(data.get("entries", {}))
                except (json.JSONDecodeError, OSError):
                    pass

        # Include Oxigraph stats if available
        if self._oxigraph_store is not None:
            stats["oxigraph_triples"] = len(self._oxigraph_store)
            stats["oxigraph_available"] = self._oxigraph_store.is_loaded
        else:
            stats["oxigraph_available"] = False

        return stats


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
