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

# REST API endpoints (Skosmos for AGROVOC, Lookup for DBpedia)
REST_ENDPOINTS = {
    "agrovoc": "https://agrovoc.fao.org/browse/rest/v1",
    "dbpedia": "https://lookup.dbpedia.org/api",
}

# Cache settings
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "inventory-md" / "skos"
CACHE_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days
DEFAULT_TIMEOUT = 300.0  # SPARQL endpoints can be slow

# Language code fallbacks (e.g., Norwegian Bokmål 'nb' may be stored as 'no')
LANGUAGE_FALLBACKS = {
    "nb": "no",  # Norwegian Bokmål -> Norwegian
    "nn": "no",  # Norwegian Nynorsk -> Norwegian
}

# Default path for local AGROVOC data
DEFAULT_AGROVOC_PATH = DEFAULT_CACHE_DIR / "agrovoc.nt"

# Patterns for filtering irrelevant DBpedia categories
# These are Wikipedia-style meta categories that aren't useful for inventory classification
_IRRELEVANT_CATEGORY_PATTERNS = [
    # Year-based categories
    r"^\d{4}\s",  # "1750 introductions", "1893 in germany"
    r"^\d{4}s\s",  # "1950s fashion", "1930s neologisms"
    r"^\d+[a-z]{2}.century",  # "16th-century neologisms", "21st-century fashion"
    r"^\d+[a-z]{2}.millennium",  # "9th-millennium bc establishments"
    r"century.*works$",  # "6th-century bc works"
    r"century.*establishments$",
    # Meta categories about Wikipedia itself
    r"introductions$",
    r"neologisms$",
    r"establishments\s",
    r"disestablishments",
    r"archaeological\s",
    r"musical\sinstruments$",  # "1931 musical instruments" (year-based)
    r"^articles\s",
    r"watchlist",
    r"stubs$",
    r"wiki",
    r"related\slists$",  # "alcohol-related lists"
    # Location/time context (not product categories)
    r"\sin\s\w+$",  # "1893 in germany", "1963 in music"
    r"by\scountry",
    r"by\syear",
    # Geographic/cultural categories (not product types)
    r"realm\sflora$",  # "afrotropical realm flora"
    r"^age\sof\ssail",  # "age of sail naval ships"
    # More year/time patterns
    r"invented\sin\sthe\s\d",  # "musical instruments invented in the 1950s"
    r"introduced\sin\sthe\s\d",  # "food and drink introduced in the 19th century"
    r"\d{4}s[–-]\d{4}s",  # "1970s-1990s" year ranges
    r"culture\s\d{4}",  # "cassette culture 1970s"
    # Scientific/biological categories (not inventory items)
    r"cellular\sprocesses",
    r"molecular\sgenetics",
    r"dna\srepair",
    r"mutation$",
    r"senescence",
    r"video\sclips",
]

# Compiled regex for efficiency
import re as _re
_IRRELEVANT_CATEGORY_RE = _re.compile(
    "|".join(_IRRELEVANT_CATEGORY_PATTERNS),
    _re.IGNORECASE
)


def _is_irrelevant_dbpedia_category(label: str) -> bool:
    """Check if a DBpedia category label is irrelevant for inventory classification.

    Filters out Wikipedia-style meta categories like:
    - Year-based: "1750 introductions", "1893 in germany"
    - Meta categories: "neologisms", "establishments"
    - Context categories: "by country", "by year"

    Args:
        label: Category label to check.

    Returns:
        True if the category should be filtered out, False otherwise.
    """
    return bool(_IRRELEVANT_CATEGORY_RE.search(label))


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
        self._has_data: bool = False

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
        self._has_data = True
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
        return self._has_data


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

        # Use provided store or lazy-load later
        # Don't load Oxigraph eagerly - it takes ~30s to load 7M triples
        if oxigraph_store is not None:
            self._oxigraph_store = oxigraph_store
            self._oxigraph_loaded = True
        else:
            self._oxigraph_store = None
            self._oxigraph_loaded = False

    def _get_oxigraph_store(self) -> OxigraphStore | None:
        """Lazy-load the Oxigraph store on first use."""
        if self._oxigraph_loaded:
            return self._oxigraph_store
        if not self.use_oxigraph:
            self._oxigraph_loaded = True
            return None
        self._oxigraph_store = get_oxigraph_store(agrovoc_path=self.agrovoc_path)
        self._oxigraph_loaded = True
        return self._oxigraph_store

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

    def get_concept_labels(
        self, uri: str, languages: list[str], source: str = "agrovoc"
    ) -> dict[str, str]:
        """Get labels for a concept in multiple languages.

        Fetches all requested languages in a single SPARQL query and caches
        the results. Subsequent calls for the same URI will use cached data.

        Args:
            uri: The concept URI (e.g., "http://aims.fao.org/aos/agrovoc/c_13551").
            languages: List of language codes to fetch (e.g., ["en", "nb", "de"]).
            source: The source vocabulary ("agrovoc" or "dbpedia").

        Returns:
            Dictionary mapping language codes to labels (e.g., {"en": "potatoes", "nb": "poteter"}).
        """
        if not uri or not languages:
            return {}

        # Create cache key from URI (use hash for long URIs)
        import hashlib
        uri_hash = hashlib.md5(uri.encode()).hexdigest()[:16]
        cache_key = f"labels:{source}:{uri_hash}"
        cache_path = _get_cache_path(self.cache_dir, cache_key)

        # Check cache first
        cached = _load_from_cache(cache_path)
        if cached is not None:
            # Return only the requested languages from cache
            cached_labels = cached.get("labels", {})
            return {lang: cached_labels[lang] for lang in languages if lang in cached_labels}

        # Fetch all languages in one query
        if source == "agrovoc":
            all_labels = self._get_agrovoc_labels(uri, languages)
        elif source == "dbpedia":
            all_labels = self._get_dbpedia_labels(uri, languages)
        else:
            return {}

        # Cache the result (store all fetched labels)
        if all_labels:
            _save_to_cache(cache_path, {"uri": uri, "source": source, "labels": all_labels})

        return all_labels

    def get_batch_labels(
        self, uris: list[tuple[str, str]], languages: list[str]
    ) -> dict[str, dict[str, str]]:
        """Get labels for multiple concepts in batch, using cache where available.

        Args:
            uris: List of (uri, source) tuples.
            languages: List of language codes to fetch.

        Returns:
            Dictionary mapping URIs to their label dictionaries.
        """
        import hashlib

        results: dict[str, dict[str, str]] = {}
        uncached_agrovoc: list[str] = []
        uncached_dbpedia: list[str] = []

        # Check cache for each URI
        for uri, source in uris:
            uri_hash = hashlib.md5(uri.encode()).hexdigest()[:16]
            cache_key = f"labels:{source}:{uri_hash}"
            cache_path = _get_cache_path(self.cache_dir, cache_key)

            cached = _load_from_cache(cache_path)
            if cached is not None:
                cached_labels = cached.get("labels", {})
                results[uri] = {lang: cached_labels[lang] for lang in languages if lang in cached_labels}
            else:
                if source == "agrovoc":
                    uncached_agrovoc.append(uri)
                elif source == "dbpedia":
                    uncached_dbpedia.append(uri)

        # Batch fetch uncached AGROVOC labels
        if uncached_agrovoc:
            batch_results = self._get_agrovoc_labels_batch(uncached_agrovoc, languages)
            for uri, labels in batch_results.items():
                results[uri] = labels
                # Cache each result
                uri_hash = hashlib.md5(uri.encode()).hexdigest()[:16]
                cache_key = f"labels:agrovoc:{uri_hash}"
                cache_path = _get_cache_path(self.cache_dir, cache_key)
                _save_to_cache(cache_path, {"uri": uri, "source": "agrovoc", "labels": labels})

        # Batch fetch uncached DBpedia labels
        if uncached_dbpedia:
            batch_results = self._get_dbpedia_labels_batch(uncached_dbpedia, languages)
            for uri, labels in batch_results.items():
                results[uri] = labels
                # Cache each result
                uri_hash = hashlib.md5(uri.encode()).hexdigest()[:16]
                cache_key = f"labels:dbpedia:{uri_hash}"
                cache_path = _get_cache_path(self.cache_dir, cache_key)
                _save_to_cache(cache_path, {"uri": uri, "source": "dbpedia", "labels": labels})

        return results

    def _get_agrovoc_labels_batch(
        self, uris: list[str], languages: list[str]
    ) -> dict[str, dict[str, str]]:
        """Get labels for multiple AGROVOC URIs in SPARQL queries.

        Uses local Oxigraph store if available (better language coverage),
        otherwise falls back to remote SPARQL endpoint.
        """
        if not uris:
            return {}

        # Expand languages with fallbacks (e.g., 'nb' -> also query 'no')
        query_languages = set(languages)
        for lang in languages:
            if lang in LANGUAGE_FALLBACKS:
                query_languages.add(LANGUAGE_FALLBACKS[lang])

        # Deduplicate URIs
        unique_uris = list(dict.fromkeys(uris))
        labels_by_uri: dict[str, dict[str, str]] = {uri: {} for uri in unique_uris}

        # Try local Oxigraph first (has better language coverage including Norwegian)
        oxigraph_store = self._get_oxigraph_store()
        if oxigraph_store is not None and oxigraph_store.is_loaded:
            labels_by_uri = self._get_agrovoc_labels_batch_oxigraph(
                oxigraph_store, unique_uris, query_languages
            )
        else:
            # Fall back to remote SPARQL endpoint
            endpoint = self.endpoints.get("agrovoc")
            if endpoint:
                labels_by_uri = self._get_agrovoc_labels_batch_sparql(
                    endpoint, unique_uris, query_languages
                )

        # Apply fallbacks: if 'nb' not found but 'no' exists, copy 'no' to 'nb'
        for uri_labels in labels_by_uri.values():
            for requested_lang in languages:
                if requested_lang not in uri_labels:
                    fallback_lang = LANGUAGE_FALLBACKS.get(requested_lang)
                    if fallback_lang and fallback_lang in uri_labels:
                        uri_labels[requested_lang] = uri_labels[fallback_lang]

        return labels_by_uri

    def _get_agrovoc_labels_batch_oxigraph(
        self, store: OxigraphStore, uris: list[str], languages: set[str]
    ) -> dict[str, dict[str, str]]:
        """Get AGROVOC labels from local Oxigraph store."""
        labels_by_uri: dict[str, dict[str, str]] = {uri: {} for uri in uris}
        lang_filter = ", ".join(f'"{lang}"' for lang in languages)

        # Query all URIs in one go (local store can handle large queries)
        for uri in uris:
            query = f"""
            PREFIX skosxl: <http://www.w3.org/2008/05/skos-xl#>

            SELECT ?lang ?label WHERE {{
                <{uri}> skosxl:prefLabel/skosxl:literalForm ?label .
                BIND(lang(?label) AS ?lang)
                FILTER(?lang IN ({lang_filter}))
            }}
            """
            try:
                results = store.query(query)
                for r in results:
                    lang = r.get("lang", {}).get("value", "")
                    label = r.get("label", {}).get("value", "")
                    if lang and label:
                        labels_by_uri[uri][lang] = label
            except Exception as e:
                logger.debug("Oxigraph label query failed for %s: %s", uri, e)

        return labels_by_uri

    def _get_agrovoc_labels_batch_sparql(
        self, endpoint: str, uris: list[str], languages: set[str]
    ) -> dict[str, dict[str, str]]:
        """Get AGROVOC labels from remote SPARQL endpoint."""
        labels_by_uri: dict[str, dict[str, str]] = {uri: {} for uri in uris}

        # Split into chunks to avoid URL length limits
        chunk_size = 50
        lang_filter = ", ".join(f"'{lang}'" for lang in languages)

        for i in range(0, len(uris), chunk_size):
            chunk = uris[i:i + chunk_size]
            uri_values = " ".join(f"<{uri}>" for uri in chunk)

            query = f"""
            PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
            PREFIX skosxl: <http://www.w3.org/2008/05/skos-xl#>

            SELECT ?concept ?lang ?label WHERE {{
                VALUES ?concept {{ {uri_values} }}
                ?concept skosxl:prefLabel/skosxl:literalForm ?label .
                BIND(lang(?label) AS ?lang)
                FILTER(?lang IN ({lang_filter}))
            }}
            """

            results = self._sparql_query(endpoint, query)
            if results is None:
                continue

            for r in results:
                concept_uri = r.get("concept", {}).get("value", "")
                lang = r.get("lang", {}).get("value", "")
                label = r.get("label", {}).get("value", "")
                if concept_uri and lang and label and concept_uri in labels_by_uri:
                    labels_by_uri[concept_uri][lang] = label

        return labels_by_uri

    def _get_dbpedia_labels_batch(
        self, uris: list[str], languages: list[str]
    ) -> dict[str, dict[str, str]]:
        """Get labels for multiple DBpedia URIs in SPARQL queries.

        Splits large batches into chunks to avoid URL length limits (414 errors).
        """
        endpoint = self.endpoints.get("dbpedia")
        if not endpoint or not uris:
            return {}

        # Expand languages with fallbacks (e.g., 'nb' -> also query 'no')
        query_languages = set(languages)
        for lang in languages:
            if lang in LANGUAGE_FALLBACKS:
                query_languages.add(LANGUAGE_FALLBACKS[lang])

        # Deduplicate URIs
        unique_uris = list(dict.fromkeys(uris))

        # Split into chunks to avoid URL length limits (max ~20 URIs per query)
        chunk_size = 20
        labels_by_uri: dict[str, dict[str, str]] = {uri: {} for uri in unique_uris}

        for i in range(0, len(unique_uris), chunk_size):
            chunk = unique_uris[i:i + chunk_size]
            uri_values = " ".join(f"<{uri}>" for uri in chunk)
            lang_filter = ", ".join(f"'{lang}'" for lang in query_languages)

            query = f"""
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

            SELECT ?concept ?lang ?label WHERE {{
                VALUES ?concept {{ {uri_values} }}
                ?concept rdfs:label ?label .
                BIND(lang(?label) AS ?lang)
                FILTER(?lang IN ({lang_filter}))
            }}
            """

            results = self._sparql_query(endpoint, query)
            if results is None:
                continue  # Skip failed chunk, try next

            for r in results:
                concept_uri = r.get("concept", {}).get("value", "")
                lang = r.get("lang", {}).get("value", "")
                label = r.get("label", {}).get("value", "")
                if concept_uri and lang and label:
                    if concept_uri in labels_by_uri:
                        labels_by_uri[concept_uri][lang] = label

        # Apply fallbacks: if 'nb' not found but 'no' exists, copy 'no' to 'nb'
        for uri_labels in labels_by_uri.values():
            for requested_lang in languages:
                if requested_lang not in uri_labels:
                    fallback_lang = LANGUAGE_FALLBACKS.get(requested_lang)
                    if fallback_lang and fallback_lang in uri_labels:
                        uri_labels[requested_lang] = uri_labels[fallback_lang]

        return labels_by_uri

    def _get_agrovoc_labels(self, uri: str, languages: list[str]) -> dict[str, str]:
        """Get labels from AGROVOC in multiple languages using SPARQL."""
        endpoint = self.endpoints.get("agrovoc")
        if not endpoint:
            return {}

        # Expand languages with fallbacks (e.g., 'nb' -> also query 'no')
        query_languages = set(languages)
        for lang in languages:
            if lang in LANGUAGE_FALLBACKS:
                query_languages.add(LANGUAGE_FALLBACKS[lang])

        lang_filter = ", ".join(f"'{lang}'" for lang in query_languages)
        query = f"""
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        PREFIX skosxl: <http://www.w3.org/2008/05/skos-xl#>

        SELECT ?lang ?label WHERE {{
            <{uri}> skosxl:prefLabel/skosxl:literalForm ?label .
            BIND(lang(?label) AS ?lang)
            FILTER(?lang IN ({lang_filter}))
        }}
        """

        results = self._sparql_query(endpoint, query)
        if results is None:
            return {}

        labels = {}
        for r in results:
            lang = r.get("lang", {}).get("value", "")
            label = r.get("label", {}).get("value", "")
            if lang and label:
                labels[lang] = label

        # Apply fallbacks: if 'nb' not found but 'no' exists, copy 'no' to 'nb'
        for requested_lang in languages:
            if requested_lang not in labels:
                fallback_lang = LANGUAGE_FALLBACKS.get(requested_lang)
                if fallback_lang and fallback_lang in labels:
                    labels[requested_lang] = labels[fallback_lang]

        return labels

    def _get_dbpedia_labels(self, uri: str, languages: list[str]) -> dict[str, str]:
        """Get labels from DBpedia in multiple languages.

        DBpedia has language-specific versions, but we can query the main
        endpoint for rdfs:label in different languages.
        """
        endpoint = self.endpoints.get("dbpedia")
        if not endpoint:
            return {}

        # Expand languages with fallbacks (e.g., 'nb' -> also query 'no')
        query_languages = set(languages)
        for lang in languages:
            if lang in LANGUAGE_FALLBACKS:
                query_languages.add(LANGUAGE_FALLBACKS[lang])

        lang_filter = ", ".join(f"'{lang}'" for lang in query_languages)
        query = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT ?lang ?label WHERE {{
            <{uri}> rdfs:label ?label .
            BIND(lang(?label) AS ?lang)
            FILTER(?lang IN ({lang_filter}))
        }}
        """

        results = self._sparql_query(endpoint, query)
        if results is None:
            return {}

        labels = {}
        for r in results:
            lang = r.get("lang", {}).get("value", "")
            label = r.get("label", {}).get("value", "")
            if lang and label:
                labels[lang] = label

        # Apply fallbacks: if 'nb' not found but 'no' exists, copy 'no' to 'nb'
        for requested_lang in languages:
            if requested_lang not in labels:
                fallback_lang = LANGUAGE_FALLBACKS.get(requested_lang)
                if fallback_lang and fallback_lang in labels:
                    labels[requested_lang] = labels[fallback_lang]

        return labels

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

        # Try REST API if enabled (only if Oxigraph not available)
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

        # Build label variations: case + singular/plural
        # AGROVOC often uses plurals (e.g., "potatoes" not "potato")
        base = label.lower()
        variations = [base]

        # Add plural forms
        if base.endswith('y') and len(base) > 2 and base[-2] not in 'aeiou':
            variations.append(base[:-1] + 'ies')  # berry -> berries
        elif base.endswith(('s', 'x', 'z', 'ch', 'sh', 'o')):
            variations.append(base + 'es')  # brush -> brushes, potato -> potatoes
        else:
            variations.append(base + 's')  # tool -> tools

        # Some -o words take just -s, so try both
        if base.endswith('o'):
            variations.append(base + 's')  # photo -> photos

        # Add singular forms (if input looks like plural)
        if base.endswith('ies') and len(base) > 3:
            variations.append(base[:-3] + 'y')  # berries -> berry
        elif base.endswith('oes') and len(base) > 3:
            variations.append(base[:-2])  # potatoes -> potato
        elif base.endswith('es') and len(base) > 2:
            variations.append(base[:-2])  # brushes -> brush
        elif base.endswith('s') and len(base) > 1:
            variations.append(base[:-1])  # tools -> tool

        # Add case variations for each
        label_variations = []
        for v in variations:
            label_variations.append(v)           # carrots
            label_variations.append(v.title())   # Carrots
        # Deduplicate while preserving order
        label_variations = list(dict.fromkeys(label_variations))

        results = None
        for try_label in label_variations:
            # Try prefLabel first
            query = f"""
            PREFIX skosxl: <http://www.w3.org/2008/05/skos-xl#>
            SELECT DISTINCT ?concept ?prefLabel WHERE {{
                ?concept skosxl:prefLabel/skosxl:literalForm "{try_label}"@{lang} .
                ?concept skosxl:prefLabel/skosxl:literalForm ?prefLabel .
                FILTER(lang(?prefLabel) = "{lang}")
            }}
            LIMIT 1
            """
            try:
                results = self._oxigraph_store.query(query)
                if results:
                    break
            except Exception as e:
                logger.debug("Oxigraph prefLabel query failed: %s", e)

            # Try altLabel
            query = f"""
            PREFIX skosxl: <http://www.w3.org/2008/05/skos-xl#>
            SELECT DISTINCT ?concept ?prefLabel WHERE {{
                ?concept skosxl:altLabel/skosxl:literalForm "{try_label}"@{lang} .
                ?concept skosxl:prefLabel/skosxl:literalForm ?prefLabel .
                FILTER(lang(?prefLabel) = "{lang}")
            }}
            LIMIT 1
            """
            try:
                results = self._oxigraph_store.query(query)
                if results:
                    break
            except Exception as e:
                logger.debug("Oxigraph altLabel query failed: %s", e)

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

        # Get direct broader concepts first (fast), limit transitive depth
        # Using skos:broader (not transitive) for speed, then follow chain manually
        query = f"""
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        PREFIX skosxl: <http://www.w3.org/2008/05/skos-xl#>

        SELECT DISTINCT ?broader ?label WHERE {{
            <{concept_uri}> skos:broader ?broader .
            ?broader skosxl:prefLabel/skosxl:literalForm ?label .
            FILTER(lang(?label) = "{lang}")
        }}
        LIMIT 10
        """

        try:
            results = self._oxigraph_store.query(query)
            broader_list = [
                {"uri": r["broader"]["value"], "label": r["label"]["value"]}
                for r in results
            ]

            # Follow one more level up for better hierarchy
            if broader_list:
                first_broader = broader_list[0]["uri"]
                query2 = f"""
                PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
                PREFIX skosxl: <http://www.w3.org/2008/05/skos-xl#>

                SELECT DISTINCT ?broader ?label WHERE {{
                    <{first_broader}> skos:broader ?broader .
                    ?broader skosxl:prefLabel/skosxl:literalForm ?label .
                    FILTER(lang(?label) = "{lang}")
                }}
                LIMIT 5
                """
                results2 = self._oxigraph_store.query(query2)
                broader_list.extend([
                    {"uri": r["broader"]["value"], "label": r["label"]["value"]}
                    for r in results2
                ])

            return broader_list
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

        Priority: REST API (Lookup) > SPARQL (remote).

        Returns:
            Tuple of (concept_dict, query_failed). query_failed is True if
            the query timed out or had a network error.
        """
        # Try REST API first if enabled (faster)
        if self.use_rest_api:
            rest_base = self.rest_endpoints.get("dbpedia")
            if rest_base:
                result = self._lookup_dbpedia_rest(label, lang, rest_base)
                if result is not None:
                    return result
                # REST failed, fall back to SPARQL
                logger.debug("DBpedia REST API failed, falling back to SPARQL for %s", label)

        return self._lookup_dbpedia_sparql(label, lang)

    def _lookup_dbpedia_rest(
        self, label: str, lang: str, rest_base: str
    ) -> tuple[dict | None, bool] | None:
        """Look up concept in DBpedia via REST Lookup API.

        Returns:
            Tuple of (concept_dict, query_failed), or None to fall back to SPARQL.
        """
        try:
            import requests
        except ImportError as e:
            raise ImportError(
                "requests required for SKOS lookups. "
                "Install with: pip install inventory-md[skos]"
            ) from e

        import re

        url = f"{rest_base}/search"
        params = {"query": label, "format": "JSON", "maxResults": 30}

        try:
            response = requests.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
        except requests.Timeout as e:
            logger.warning("DBpedia REST API timed out for %s: %s", label, e)
            return None  # Fall back to SPARQL
        except requests.RequestException as e:
            logger.warning("DBpedia REST API failed for %s: %s", label, e)
            return None  # Fall back to SPARQL

        docs = data.get("docs", [])
        if not docs:
            return None, False  # Not found (but query succeeded)

        # Types to exclude - these are unlikely to be inventory items
        excluded_types = {
            "Person", "Agent", "Band", "Group", "Organisation", "Organization",
            "MusicalArtist", "Artist", "Athlete", "Politician", "Writer",
            "Company", "SportsTeam", "PoliticalParty", "SoccerClub",
            "Settlement", "City", "Country", "Place", "PopulatedPlace",
            "Film", "TelevisionShow", "Album", "Single", "Song",
            "Event", "MilitaryConflict", "Election",
        }

        def is_excluded_type(doc: dict) -> bool:
            """Check if document has excluded types."""
            type_names = doc.get("typeName", [])
            return bool(set(type_names) & excluded_types)

        def is_list_article(doc: dict) -> bool:
            """Check if document is a Wikipedia 'List of...' article."""
            resource_list = doc.get("resource", [])
            if resource_list:
                resource_name = resource_list[0].split("/")[-1]
                if resource_name.startswith("List_of_"):
                    return True
            doc_labels = doc.get("label", [])
            if doc_labels:
                clean_label = re.sub(r"</?B>", "", doc_labels[0])
                if clean_label.startswith("List of "):
                    return True
            return False

        def is_disambiguation_page(doc: dict) -> bool:
            """Check if document is a Wikipedia disambiguation page."""
            # Check resource name for disambiguation suffix
            resource_list = doc.get("resource", [])
            if resource_list:
                resource_name = resource_list[0].split("/")[-1]
                if resource_name.endswith("_(disambiguation)"):
                    return True
            # Check type for disambiguation markers
            type_names = doc.get("typeName", [])
            if any("disambiguation" in t.lower() for t in type_names):
                return True
            # Check comment for disambiguation indicators
            comments = doc.get("comment", [])
            if comments:
                comment = comments[0].lower()
                if "may refer to:" in comment or "disambiguation" in comment:
                    return True
            return False

        # Find best match - require close label match to avoid irrelevant results
        # like "DNA repair" for "repair" or "Cable television" for "cable"
        label_lower = label.lower()
        best_match = None

        def is_exact_match(doc_label: str) -> bool:
            """Check if label is an exact match (case-insensitive)."""
            return doc_label.lower() == label_lower

        def is_plural_match(doc_label: str) -> bool:
            """Check if label is a simple plural of search term."""
            return doc_label.lower() == label_lower + 's'

        # First pass: scan ALL results for exact match (DBpedia puts popular
        # results first, so "Tool" band appears before "Tool" article)
        for doc in docs:
            if is_excluded_type(doc) or is_list_article(doc) or is_disambiguation_page(doc):
                continue

            # Check resource name
            resource_list = doc.get("resource", [])
            if resource_list:
                resource_name = resource_list[0].split("/")[-1].replace("_", " ")
                if is_exact_match(resource_name):
                    best_match = doc
                    break

            # Check label
            doc_labels = doc.get("label", [])
            if doc_labels:
                clean_label = re.sub(r"</?B>", "", doc_labels[0])
                if is_exact_match(clean_label):
                    best_match = doc
                    break

            # Check redirect labels
            redirect_labels = doc.get("redirectlabel", [])
            for redirect in redirect_labels:
                clean_redirect = re.sub(r"</?B>", "", redirect)
                if is_exact_match(clean_redirect):
                    best_match = doc
                    break
            if best_match:
                break

        # Second pass: if no exact match, look for simple plural
        if not best_match:
            for doc in docs:
                if is_excluded_type(doc) or is_list_article(doc) or is_disambiguation_page(doc):
                    continue

                resource_list = doc.get("resource", [])
                if resource_list:
                    resource_name = resource_list[0].split("/")[-1].replace("_", " ")
                    if is_plural_match(resource_name):
                        best_match = doc
                        break

                doc_labels = doc.get("label", [])
                if doc_labels:
                    clean_label = re.sub(r"</?B>", "", doc_labels[0])
                    if is_plural_match(clean_label):
                        best_match = doc
                        break
                if best_match:
                    break

        if not best_match:
            return None, False

        # Extract resource URI (values are in arrays)
        resource_list = best_match.get("resource", [])
        if not resource_list:
            return None, False
        resource_uri = resource_list[0]

        # Extract label (strip HTML tags)
        label_list = best_match.get("label", [label])
        pref_label = re.sub(r"</?B>", "", label_list[0]) if label_list else label

        # Extract categories from the response
        broader = []
        category_list = best_match.get("category", [])
        for cat_uri in category_list[:10]:  # Limit categories
            # Extract label from category URI
            # e.g., "http://dbpedia.org/resource/Category:Root_vegetables" -> "Root vegetables"
            if "/Category:" in cat_uri:
                cat_label = cat_uri.split("/Category:")[-1].replace("_", " ")
                # Filter out irrelevant Wikipedia-style categories
                if not _is_irrelevant_dbpedia_category(cat_label):
                    broader.append({"uri": cat_uri, "label": cat_label})

        # Extract short description (comment) - strip HTML tags
        description = None
        comments = best_match.get("comment", [])
        if comments:
            description = re.sub(r"</?B>", "", comments[0])

        # Generate Wikipedia URL from DBpedia resource URI
        # http://dbpedia.org/resource/Potato -> https://en.wikipedia.org/wiki/Potato
        wikipedia_url = None
        if resource_uri.startswith("http://dbpedia.org/resource/"):
            article_name = resource_uri.split("/resource/")[-1]
            wikipedia_url = f"https://en.wikipedia.org/wiki/{article_name}"

        return {
            "uri": resource_uri,
            "prefLabel": pref_label,
            "source": "dbpedia",
            "broader": broader,
            "description": description,
            "wikipediaUrl": wikipedia_url,
        }, False

    def _lookup_dbpedia_sparql(self, label: str, lang: str) -> tuple[dict | None, bool]:
        """Look up concept in DBpedia via SPARQL.

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
        # Filter out irrelevant Wikipedia-style categories
        return [
            {"uri": r["category"]["value"], "label": r["label"]["value"]}
            for r in results
            if not _is_irrelevant_dbpedia_category(r["label"]["value"])
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
