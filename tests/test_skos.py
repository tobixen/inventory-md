"""Tests for SKOS module."""

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from inventory_md import skos


class TestCacheFunctions:
    """Tests for cache helper functions."""

    def test_get_cache_path(self, tmp_path):
        """Test cache path generation."""
        path = skos._get_cache_path(tmp_path, "test:key")
        assert path.parent == tmp_path
        assert path.suffix == ".json"
        assert "test_key" in path.name

    def test_get_cache_path_special_chars(self, tmp_path):
        """Test cache path with special characters in key."""
        path = skos._get_cache_path(tmp_path, "concept:agrovoc:en:spätzle")
        assert path.parent == tmp_path
        assert path.suffix == ".json"

    def test_load_from_cache_missing(self, tmp_path):
        """Test loading from non-existent cache file."""
        path = tmp_path / "missing.json"
        assert skos._load_from_cache(path) is None

    def test_load_from_cache_valid(self, tmp_path):
        """Test loading valid cached data."""
        path = tmp_path / "test.json"
        data = {"uri": "http://example.com/concept", "_cached_at": time.time()}
        path.write_text(json.dumps(data))

        result = skos._load_from_cache(path)
        assert result["uri"] == "http://example.com/concept"

    def test_load_from_cache_expired(self, tmp_path):
        """Test that expired cache returns None."""
        path = tmp_path / "test.json"
        data = {"uri": "http://example.com/concept", "_cached_at": time.time() - 100000}
        path.write_text(json.dumps(data))

        # With short TTL, should be expired
        result = skos._load_from_cache(path, ttl=1)
        assert result is None

    def test_save_to_cache(self, tmp_path):
        """Test saving data to cache."""
        path = tmp_path / "subdir" / "test.json"
        data = {"uri": "http://example.com/concept"}

        skos._save_to_cache(path, data)

        assert path.exists()
        loaded = json.loads(path.read_text())
        assert loaded["uri"] == "http://example.com/concept"
        assert "_cached_at" in loaded

    def test_not_found_cache_add_and_check(self, tmp_path):
        """Test adding to and checking the not-found cache."""
        key = "concept:agrovoc:en:nonexistent"

        # Initially not in cache
        assert not skos._is_in_not_found_cache(tmp_path, key)

        # Add to cache
        skos._add_to_not_found_cache(tmp_path, key)

        # Now should be in cache
        assert skos._is_in_not_found_cache(tmp_path, key)

        # Check file structure
        cache_path = skos._get_not_found_cache_path(tmp_path)
        assert cache_path.exists()
        data = json.loads(cache_path.read_text())
        assert key in data["entries"]
        assert "cached_at" in data["entries"][key]

    def test_not_found_cache_multiple_entries(self, tmp_path):
        """Test multiple entries in not-found cache."""
        keys = ["concept:agrovoc:en:a", "concept:agrovoc:en:b", "concept:dbpedia:en:c"]

        for key in keys:
            skos._add_to_not_found_cache(tmp_path, key)

        for key in keys:
            assert skos._is_in_not_found_cache(tmp_path, key)

        # Check only one file exists
        cache_path = skos._get_not_found_cache_path(tmp_path)
        assert cache_path.exists()
        data = json.loads(cache_path.read_text())
        assert len(data["entries"]) == 3

    def test_not_found_cache_expired(self, tmp_path):
        """Test that expired not-found entries are not returned."""
        key = "concept:agrovoc:en:expired"

        # Add with old timestamp
        cache_path = skos._get_not_found_cache_path(tmp_path)
        tmp_path.mkdir(parents=True, exist_ok=True)
        data = {"entries": {key: {"cached_at": time.time() - 100000}}}
        cache_path.write_text(json.dumps(data))

        # Should not be found with short TTL
        assert not skos._is_in_not_found_cache(tmp_path, key, ttl=1)


class TestIrrelevantCategoryFilter:
    """Tests for DBpedia category filtering."""

    def test_filters_year_based_categories(self):
        """Test that year-based categories are filtered."""
        assert skos._is_irrelevant_dbpedia_category("1750 introductions")
        assert skos._is_irrelevant_dbpedia_category("1893 in germany")
        assert skos._is_irrelevant_dbpedia_category("1950s fashion")
        assert skos._is_irrelevant_dbpedia_category("16th-century neologisms")
        assert skos._is_irrelevant_dbpedia_category("21st-century fashion")
        assert skos._is_irrelevant_dbpedia_category("6th-century bc works")
        assert skos._is_irrelevant_dbpedia_category("9th-millennium bc establishments")

    def test_filters_meta_categories(self):
        """Test that Wikipedia meta categories are filtered."""
        assert skos._is_irrelevant_dbpedia_category("Food watchlist articles")
        assert skos._is_irrelevant_dbpedia_category("1931 musical instruments")
        assert skos._is_irrelevant_dbpedia_category("Articles needing cleanup")
        assert skos._is_irrelevant_dbpedia_category("Alcohol-related lists")
        assert skos._is_irrelevant_dbpedia_category("Afrotropical realm flora")
        assert skos._is_irrelevant_dbpedia_category("Age of sail naval ships")

    def test_filters_location_context_categories(self):
        """Test that location/context categories are filtered."""
        assert skos._is_irrelevant_dbpedia_category("1963 in music")
        assert skos._is_irrelevant_dbpedia_category("Products by country")
        assert skos._is_irrelevant_dbpedia_category("Events by year")

    def test_keeps_useful_categories(self):
        """Test that useful product categories are NOT filtered."""
        assert not skos._is_irrelevant_dbpedia_category("Root vegetables")
        assert not skos._is_irrelevant_dbpedia_category("Hand tools")
        assert not skos._is_irrelevant_dbpedia_category("Electronics")
        assert not skos._is_irrelevant_dbpedia_category("Food and drink")
        assert not skos._is_irrelevant_dbpedia_category("Woodworking")
        assert not skos._is_irrelevant_dbpedia_category("Kitchen utensils")


class TestSKOSClient:
    """Tests for SKOSClient class."""

    def test_init_defaults(self):
        """Test client initialization with defaults."""
        client = skos.SKOSClient()
        assert client.cache_dir == skos.DEFAULT_CACHE_DIR
        assert "agrovoc" in client.endpoints
        assert "dbpedia" in client.endpoints
        assert client.timeout == skos.DEFAULT_TIMEOUT
        assert client.use_rest_api is True
        assert "agrovoc" in client.rest_endpoints

    def test_init_custom(self, tmp_path):
        """Test client initialization with custom settings."""
        client = skos.SKOSClient(
            cache_dir=tmp_path,
            endpoints={"custom": "http://example.com/sparql"},
            timeout=5.0,
            enabled_sources=["custom"],
        )
        assert client.cache_dir == tmp_path
        assert client.endpoints == {"custom": "http://example.com/sparql"}
        assert client.timeout == 5.0
        assert client.enabled_sources == ["custom"]

    def test_lookup_concept_uses_cache(self, tmp_path):
        """Test that lookup_concept uses cached data."""
        client = skos.SKOSClient(cache_dir=tmp_path)

        # Pre-populate cache
        cache_key = "concept:agrovoc:en:potatoes"
        cache_path = skos._get_cache_path(tmp_path, cache_key)
        cached_data = {
            "uri": "http://cached.example.com/potatoes",
            "prefLabel": "potatoes",
            "source": "agrovoc",
            "broader": [],
            "_cached_at": time.time(),
        }
        skos._save_to_cache(cache_path, cached_data)

        # Should return cached data without making network request
        result = client.lookup_concept("potatoes", lang="en", source="agrovoc")
        assert result["uri"] == "http://cached.example.com/potatoes"

    @patch("inventory_md.skos.SKOSClient._sparql_query")
    def test_lookup_concept_agrovoc(self, mock_query, tmp_path):
        """Test AGROVOC concept lookup via SPARQL."""
        # Disable REST API and Oxigraph to test SPARQL path
        client = skos.SKOSClient(cache_dir=tmp_path, use_rest_api=False, use_oxigraph=False)

        # Mock SPARQL responses - first call returns concept, second returns broader
        mock_query.side_effect = [
            [
                {
                    "concept": {"value": "http://aims.fao.org/aos/agrovoc/c_1234"},
                    "prefLabel": {"value": "potatoes"},
                }
            ],
            [
                {
                    "broader": {"value": "http://aims.fao.org/aos/agrovoc/c_5678"},
                    "label": {"value": "vegetables"},
                }
            ],
        ]

        result = client.lookup_concept("potatoes", lang="en", source="agrovoc")

        assert result is not None
        assert result["uri"] == "http://aims.fao.org/aos/agrovoc/c_1234"
        assert result["source"] == "agrovoc"
        assert len(result["broader"]) == 1

    @patch("inventory_md.skos.SKOSClient._sparql_query")
    def test_lookup_concept_not_found(self, mock_query, tmp_path):
        """Test handling of concept not found."""
        client = skos.SKOSClient(cache_dir=tmp_path, use_rest_api=False)
        mock_query.return_value = []

        result = client.lookup_concept("xyznonexistent", lang="en", source="agrovoc")
        assert result is None

        # Should be added to not-found cache
        assert skos._is_in_not_found_cache(tmp_path, "concept:agrovoc:en:xyznonexistent")

        # Second lookup should use cache without calling SPARQL again
        mock_query.reset_mock()
        result2 = client.lookup_concept("xyznonexistent", lang="en", source="agrovoc")
        assert result2 is None
        mock_query.assert_not_called()

    def test_get_cache_stats(self, tmp_path):
        """Test cache statistics."""
        client = skos.SKOSClient(cache_dir=tmp_path)

        # Initially empty
        stats = client.get_cache_stats()
        assert stats["found"] == 0
        assert stats["not_found"] == 0

        # Add a found concept
        cache_key = "concept:agrovoc:en:potato"
        cache_path = skos._get_cache_path(tmp_path, cache_key)
        skos._save_to_cache(cache_path, {"uri": "http://example.com/potato"})

        # Add not-found entries
        skos._add_to_not_found_cache(tmp_path, "concept:agrovoc:en:abc")
        skos._add_to_not_found_cache(tmp_path, "concept:agrovoc:en:xyz")

        stats = client.get_cache_stats()
        assert stats["found"] == 1
        assert stats["not_found"] == 2

    def test_get_hierarchy_path_no_broader(self):
        """Test hierarchy path with no broader concepts."""
        client = skos.SKOSClient()
        concept = {"prefLabel": "potatoes", "broader": []}

        paths = client.get_hierarchy_path(concept)
        assert paths == ["potatoes"]

    def test_get_hierarchy_path_with_broader(self):
        """Test hierarchy path with broader concepts."""
        client = skos.SKOSClient()
        concept = {
            "prefLabel": "Potatoes",
            "broader": [
                {"uri": "http://example.com/vegetables", "label": "Vegetables"},
                {"uri": "http://example.com/food", "label": "Food"},
            ],
        }

        paths = client.get_hierarchy_path(concept)
        assert "vegetables/potatoes" in paths
        assert "food/potatoes" in paths

    @patch("inventory_md.skos.SKOSClient.lookup_concept")
    def test_expand_tag_found(self, mock_lookup, tmp_path):
        """Test tag expansion when concept is found."""
        client = skos.SKOSClient(cache_dir=tmp_path, enabled_sources=["agrovoc"])
        mock_lookup.return_value = {
            "uri": "http://example.com/potatoes",
            "prefLabel": "potatoes",
            "broader": [{"uri": "http://example.com/vegetables", "label": "vegetables"}],
        }

        paths = client.expand_tag("potatoes")
        assert "vegetables/potatoes" in paths

    @patch("inventory_md.skos.SKOSClient.lookup_concept")
    def test_expand_tag_not_found(self, mock_lookup, tmp_path):
        """Test tag expansion when concept not found."""
        client = skos.SKOSClient(cache_dir=tmp_path, enabled_sources=["agrovoc"])
        mock_lookup.return_value = None

        paths = client.expand_tag("unknownthing")
        assert paths == ["unknownthing"]

    @patch("inventory_md.skos.SKOSClient.lookup_concept")
    def test_expand_tags_multiple(self, mock_lookup, tmp_path):
        """Test expanding multiple tags."""
        client = skos.SKOSClient(cache_dir=tmp_path, enabled_sources=["agrovoc"])

        def lookup_side_effect(tag, lang, source):
            if tag == "potatoes":
                return {
                    "uri": "http://example.com/potatoes",
                    "prefLabel": "potatoes",
                    "broader": [{"uri": "http://example.com/vegetables", "label": "vegetables"}],
                }
            return None

        mock_lookup.side_effect = lookup_side_effect

        result = client.expand_tags(["potatoes", "hammer"])
        assert "vegetables/potatoes" in result["potatoes"]
        assert result["hammer"] == ["hammer"]

    def test_clear_cache(self, tmp_path):
        """Test clearing the cache."""
        client = skos.SKOSClient(cache_dir=tmp_path)

        # Create some cache files
        (tmp_path / "test1.json").write_text("{}")
        (tmp_path / "test2.json").write_text("{}")

        count = client.clear_cache()
        assert count == 2
        assert not list(tmp_path.glob("*.json"))


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    @patch("inventory_md.skos.SKOSClient.expand_tag")
    def test_expand_tag_function(self, mock_expand):
        """Test the expand_tag convenience function."""
        mock_expand.return_value = ["food/potatoes"]

        # Reset default client
        skos._default_client = None

        result = skos.expand_tag("potatoes")
        assert result == ["food/potatoes"]

    @patch("inventory_md.skos.SKOSClient.expand_tags")
    def test_expand_tags_function(self, mock_expand):
        """Test the expand_tags convenience function."""
        mock_expand.return_value = {"a": ["path/a"], "b": ["path/b"]}

        # Reset default client
        skos._default_client = None

        result = skos.expand_tags(["a", "b"])
        assert result == {"a": ["path/a"], "b": ["path/b"]}


class TestSPARQLQuery:
    """Tests for SPARQL query functionality."""

    def test_sparql_query_missing_requests(self, tmp_path):
        """Test error when requests not installed."""
        client = skos.SKOSClient(cache_dir=tmp_path)

        # Patch the import inside the method
        with patch.dict("sys.modules", {"requests": None}):
            # Patch builtins.__import__ to raise ImportError for requests
            original_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__

            def mock_import(name, *args, **kwargs):
                if name == "requests":
                    raise ImportError("No module named 'requests'")
                return original_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=mock_import):
                with pytest.raises(ImportError, match="requests required"):
                    client._sparql_query("http://example.com", "SELECT * WHERE {}")

    @patch("requests.get")
    def test_sparql_query_success(self, mock_get, tmp_path):
        """Test successful SPARQL query."""
        client = skos.SKOSClient(cache_dir=tmp_path)

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": {"bindings": [{"x": {"value": "test"}}]}
        }
        mock_get.return_value = mock_response

        result = client._sparql_query("http://example.com", "SELECT ?x WHERE {}")
        assert len(result) == 1
        assert result[0]["x"]["value"] == "test"

    @patch("requests.get")
    def test_sparql_query_network_error(self, mock_get, tmp_path):
        """Test handling of network errors - returns None (not cached)."""
        import requests

        client = skos.SKOSClient(cache_dir=tmp_path)
        mock_get.side_effect = requests.RequestException("Network error")

        result = client._sparql_query("http://example.com", "SELECT ?x WHERE {}")
        assert result is None  # None indicates error, won't be cached


class TestRESTAPI:
    """Tests for REST API functionality."""

    @patch("requests.get")
    def test_rest_api_search_success(self, mock_get, tmp_path):
        """Test successful REST API search."""
        client = skos.SKOSClient(cache_dir=tmp_path)

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {
                    "uri": "http://aims.fao.org/aos/agrovoc/c_6219",
                    "prefLabel": "potatoes",
                    "altLabel": ["potato", "spud"],
                }
            ]
        }
        mock_get.return_value = mock_response

        result = client._rest_api_search("https://agrovoc.fao.org/browse/rest/v1", "potatoes", "en")
        assert result is not None
        assert len(result) == 1
        assert result[0]["prefLabel"] == "potatoes"

    @patch("requests.get")
    def test_rest_api_search_timeout(self, mock_get, tmp_path):
        """Test REST API search timeout returns None."""
        import requests

        client = skos.SKOSClient(cache_dir=tmp_path)
        mock_get.side_effect = requests.Timeout("Connection timed out")

        result = client._rest_api_search("https://agrovoc.fao.org/browse/rest/v1", "potatoes", "en")
        assert result is None

    @patch("requests.get")
    def test_rest_api_get_concept_success(self, mock_get, tmp_path):
        """Test successful REST API concept data fetch."""
        client = skos.SKOSClient(cache_dir=tmp_path)

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "graph": [
                {
                    "uri": "http://aims.fao.org/aos/agrovoc/c_6219",
                    "prefLabel": [{"value": "potatoes", "lang": "en"}],
                    "broader": ["http://aims.fao.org/aos/agrovoc/c_8174"],
                }
            ]
        }
        mock_get.return_value = mock_response

        result = client._rest_api_get_concept(
            "https://agrovoc.fao.org/browse/rest/v1",
            "http://aims.fao.org/aos/agrovoc/c_6219"
        )
        assert result is not None
        assert "graph" in result

    @patch("inventory_md.skos.SKOSClient._rest_api_search")
    @patch("inventory_md.skos.SKOSClient._rest_api_get_concept")
    def test_lookup_agrovoc_rest(self, mock_get_concept, mock_search, tmp_path):
        """Test AGROVOC lookup via REST API."""
        client = skos.SKOSClient(cache_dir=tmp_path, use_rest_api=True, use_oxigraph=False)

        # Mock search response
        mock_search.return_value = [
            {
                "uri": "http://aims.fao.org/aos/agrovoc/c_6219",
                "prefLabel": "potatoes",
            }
        ]

        # Mock concept data response
        mock_get_concept.return_value = {
            "graph": [
                {
                    "uri": "http://aims.fao.org/aos/agrovoc/c_6219",
                    "prefLabel": [{"value": "potatoes", "lang": "en"}],
                    "broader": ["http://aims.fao.org/aos/agrovoc/c_8174"],
                },
                {
                    "uri": "http://aims.fao.org/aos/agrovoc/c_8174",
                    "prefLabel": [{"value": "vegetables", "lang": "en"}],
                },
            ]
        }

        result = client.lookup_concept("potatoes", lang="en", source="agrovoc")

        assert result is not None
        assert result["uri"] == "http://aims.fao.org/aos/agrovoc/c_6219"
        assert result["prefLabel"] == "potatoes"
        assert result["source"] == "agrovoc"

    @patch("inventory_md.skos.SKOSClient._rest_api_search")
    @patch("inventory_md.skos.SKOSClient._lookup_agrovoc_sparql")
    def test_lookup_agrovoc_fallback_to_sparql(self, mock_sparql, mock_search, tmp_path):
        """Test fallback to SPARQL when REST API fails."""
        client = skos.SKOSClient(cache_dir=tmp_path, use_rest_api=True, use_oxigraph=False)

        # REST API returns None (failure)
        mock_search.return_value = None

        # SPARQL fallback succeeds
        mock_sparql.return_value = (
            {
                "uri": "http://aims.fao.org/aos/agrovoc/c_6219",
                "prefLabel": "potatoes",
                "source": "agrovoc",
                "broader": [],
            },
            False,
        )

        result = client.lookup_concept("potatoes", lang="en", source="agrovoc")

        assert result is not None
        assert result["uri"] == "http://aims.fao.org/aos/agrovoc/c_6219"
        mock_sparql.assert_called_once()

    def test_lookup_agrovoc_rest_disabled(self, tmp_path):
        """Test that REST API is not used when disabled."""
        client = skos.SKOSClient(cache_dir=tmp_path, use_rest_api=False, use_oxigraph=False)

        with patch.object(client, "_rest_api_search") as mock_rest:
            with patch.object(client, "_lookup_agrovoc_sparql") as mock_sparql:
                mock_sparql.return_value = (None, False)
                client.lookup_concept("potatoes", lang="en", source="agrovoc")

                mock_rest.assert_not_called()
                mock_sparql.assert_called_once()

    @patch("requests.get")
    def test_lookup_dbpedia_rest(self, mock_get, tmp_path):
        """Test DBpedia lookup via REST Lookup API."""
        client = skos.SKOSClient(cache_dir=tmp_path, use_rest_api=True, use_oxigraph=False)

        # Mock DBpedia Lookup API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "docs": [
                {
                    "resource": ["http://dbpedia.org/resource/Potato"],
                    "label": ["<B>Potato</B>"],
                    "redirectlabel": ["Potatoes", "Spud"],
                    "category": [
                        "http://dbpedia.org/resource/Category:Root_vegetables",
                        "http://dbpedia.org/resource/Category:Staple_foods",
                    ],
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = client.lookup_concept("potato", lang="en", source="dbpedia")

        assert result is not None
        assert result["uri"] == "http://dbpedia.org/resource/Potato"
        assert result["prefLabel"] == "Potato"
        assert result["source"] == "dbpedia"
        assert len(result["broader"]) == 2
        assert result["broader"][0]["label"] == "Root vegetables"

    @patch("requests.get")
    def test_lookup_dbpedia_rest_exact_match(self, mock_get, tmp_path):
        """Test DBpedia REST API finds exact match by resource name."""
        client = skos.SKOSClient(cache_dir=tmp_path, use_rest_api=True, use_oxigraph=False)

        # Mock response where first result is not exact match
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "docs": [
                {
                    "resource": ["http://dbpedia.org/resource/Piano"],
                    "label": ["<B>Piano</B>"],
                    "category": [],
                },
                {
                    "resource": ["http://dbpedia.org/resource/Hammer"],
                    "label": ["<B>Hammer</B>"],
                    "category": ["http://dbpedia.org/resource/Category:Tools"],
                },
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = client.lookup_concept("hammer", lang="en", source="dbpedia")

        assert result is not None
        assert result["uri"] == "http://dbpedia.org/resource/Hammer"
        assert result["prefLabel"] == "Hammer"

    @patch("requests.get")
    def test_lookup_dbpedia_rest_filters_excluded_types(self, mock_get, tmp_path):
        """Test DBpedia REST API filters out bands, persons, etc."""
        client = skos.SKOSClient(cache_dir=tmp_path, use_rest_api=True, use_oxigraph=False)

        # Mock response where first result is a band (should be filtered)
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "docs": [
                {
                    "resource": ["http://dbpedia.org/resource/Helmet_(band)"],
                    "label": ["<B>Helmet</B> (band)"],
                    "typeName": ["Band", "Organisation", "Agent"],
                    "category": [],
                },
                {
                    "resource": ["http://dbpedia.org/resource/Helmet"],
                    "label": ["<B>Helmet</B>"],
                    "typeName": [],
                    "category": ["http://dbpedia.org/resource/Category:Headgear"],
                },
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = client.lookup_concept("helmet", lang="en", source="dbpedia")

        assert result is not None
        # Should match the second result (the protective gear, not the band)
        assert result["uri"] == "http://dbpedia.org/resource/Helmet"
        assert "band" not in result["prefLabel"].lower()

    @patch("inventory_md.skos.SKOSClient._lookup_dbpedia_rest")
    @patch("inventory_md.skos.SKOSClient._lookup_dbpedia_sparql")
    def test_lookup_dbpedia_fallback_to_sparql(self, mock_sparql, mock_rest, tmp_path):
        """Test fallback to SPARQL when DBpedia REST API fails."""
        client = skos.SKOSClient(cache_dir=tmp_path, use_rest_api=True, use_oxigraph=False)

        # REST API returns None (failure)
        mock_rest.return_value = None

        # SPARQL fallback succeeds
        mock_sparql.return_value = (
            {
                "uri": "http://dbpedia.org/resource/Potato",
                "prefLabel": "Potato",
                "source": "dbpedia",
                "broader": [],
            },
            False,
        )

        result = client.lookup_concept("potato", lang="en", source="dbpedia")

        assert result is not None
        assert result["uri"] == "http://dbpedia.org/resource/Potato"
        mock_sparql.assert_called_once()


class TestOxigraphStore:
    """Tests for Oxigraph local store functionality."""

    @pytest.fixture
    def sample_ntriples(self, tmp_path):
        """Create a sample N-Triples file with SKOS-XL data (AGROVOC format)."""
        # AGROVOC uses SKOS-XL format with separate label nodes
        nt_content = """
<http://example.org/concept/potato> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/2004/02/skos/core#Concept> .
<http://example.org/concept/potato> <http://www.w3.org/2008/05/skos-xl#prefLabel> <http://example.org/label/potato_en> .
<http://example.org/concept/potato> <http://www.w3.org/2008/05/skos-xl#prefLabel> <http://example.org/label/potato_sv> .
<http://example.org/concept/potato> <http://www.w3.org/2008/05/skos-xl#altLabel> <http://example.org/label/spud_en> .
<http://example.org/concept/potato> <http://www.w3.org/2004/02/skos/core#broader> <http://example.org/concept/vegetable> .
<http://example.org/label/potato_en> <http://www.w3.org/2008/05/skos-xl#literalForm> "potato"@en .
<http://example.org/label/potato_sv> <http://www.w3.org/2008/05/skos-xl#literalForm> "potatis"@sv .
<http://example.org/label/spud_en> <http://www.w3.org/2008/05/skos-xl#literalForm> "spud"@en .
<http://example.org/concept/vegetable> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/2004/02/skos/core#Concept> .
<http://example.org/concept/vegetable> <http://www.w3.org/2008/05/skos-xl#prefLabel> <http://example.org/label/vegetable_en> .
<http://example.org/concept/vegetable> <http://www.w3.org/2004/02/skos/core#broader> <http://example.org/concept/food> .
<http://example.org/label/vegetable_en> <http://www.w3.org/2008/05/skos-xl#literalForm> "vegetable"@en .
<http://example.org/concept/food> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/2004/02/skos/core#Concept> .
<http://example.org/concept/food> <http://www.w3.org/2008/05/skos-xl#prefLabel> <http://example.org/label/food_en> .
<http://example.org/label/food_en> <http://www.w3.org/2008/05/skos-xl#literalForm> "food"@en .
"""
        nt_file = tmp_path / "test.nt"
        nt_file.write_text(nt_content.strip())
        return nt_file

    def test_oxigraph_store_import_error(self):
        """Test that ImportError is raised when pyoxigraph not installed."""
        with patch.dict("sys.modules", {"pyoxigraph": None}):
            original_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__

            def mock_import(name, *args, **kwargs):
                if name == "pyoxigraph":
                    raise ImportError("No module named 'pyoxigraph'")
                return original_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=mock_import):
                with pytest.raises(ImportError, match="pyoxigraph required"):
                    skos.OxigraphStore()

    def test_oxigraph_store_load_and_query(self, sample_ntriples):
        """Test loading N-Triples and querying."""
        pytest.importorskip("pyoxigraph")

        store = skos.OxigraphStore()
        loaded = store.load(sample_ntriples)

        assert loaded > 0
        assert store.is_loaded
        assert len(store) > 0

        # Query for potato concept using SKOS-XL (AGROVOC format)
        results = store.query("""
            PREFIX skosxl: <http://www.w3.org/2008/05/skos-xl#>
            SELECT ?label WHERE {
                <http://example.org/concept/potato> skosxl:prefLabel/skosxl:literalForm ?label .
                FILTER(lang(?label) = "en")
            }
        """)

        assert len(results) == 1
        assert results[0]["label"]["value"] == "potato"

    def test_oxigraph_store_file_not_found(self, tmp_path):
        """Test that FileNotFoundError is raised for missing file."""
        pytest.importorskip("pyoxigraph")

        store = skos.OxigraphStore()
        with pytest.raises(FileNotFoundError):
            store.load(tmp_path / "nonexistent.nt")

    def test_oxigraph_store_no_double_load(self, sample_ntriples):
        """Test that loading the same file twice doesn't duplicate triples."""
        pytest.importorskip("pyoxigraph")

        store = skos.OxigraphStore()
        first_load = store.load(sample_ntriples)
        second_load = store.load(sample_ntriples)

        assert first_load > 0
        assert second_load == 0  # Should skip already loaded file

    def test_skos_client_with_oxigraph(self, sample_ntriples, tmp_path):
        """Test SKOSClient using Oxigraph store."""
        pytest.importorskip("pyoxigraph")

        store = skos.OxigraphStore()
        store.load(sample_ntriples)

        client = skos.SKOSClient(
            cache_dir=tmp_path,
            oxigraph_store=store,
            use_rest_api=False,
        )

        # Look up by prefLabel
        result = client.lookup_concept("potato", lang="en", source="agrovoc")

        assert result is not None
        assert result["uri"] == "http://example.org/concept/potato"
        assert result["prefLabel"] == "potato"
        assert result["source"] == "agrovoc"
        assert len(result["broader"]) >= 1

        # Check broader concepts
        broader_labels = [b["label"] for b in result["broader"]]
        assert "vegetable" in broader_labels or "food" in broader_labels

    def test_skos_client_oxigraph_altlabel(self, sample_ntriples, tmp_path):
        """Test lookup by altLabel via Oxigraph."""
        pytest.importorskip("pyoxigraph")

        store = skos.OxigraphStore()
        store.load(sample_ntriples)

        client = skos.SKOSClient(
            cache_dir=tmp_path,
            oxigraph_store=store,
            use_rest_api=False,
        )

        # Look up by altLabel "spud"
        result = client.lookup_concept("spud", lang="en", source="agrovoc")

        assert result is not None
        assert result["uri"] == "http://example.org/concept/potato"

    def test_skos_client_oxigraph_not_found(self, sample_ntriples, tmp_path):
        """Test that not found in Oxigraph returns None without fallback."""
        pytest.importorskip("pyoxigraph")

        store = skos.OxigraphStore()
        store.load(sample_ntriples)

        client = skos.SKOSClient(
            cache_dir=tmp_path,
            oxigraph_store=store,
            use_rest_api=False,
        )

        # Look up non-existent concept
        result = client.lookup_concept("nonexistent", lang="en", source="agrovoc")

        assert result is None

    def test_skos_client_cache_stats_with_oxigraph(self, sample_ntriples, tmp_path):
        """Test cache stats include Oxigraph info."""
        pytest.importorskip("pyoxigraph")

        store = skos.OxigraphStore()
        store.load(sample_ntriples)

        client = skos.SKOSClient(
            cache_dir=tmp_path,
            oxigraph_store=store,
        )

        stats = client.get_cache_stats()

        assert stats["oxigraph_available"] is True
        assert stats["oxigraph_triples"] > 0
