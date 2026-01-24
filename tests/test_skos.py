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


class TestSKOSClient:
    """Tests for SKOSClient class."""

    def test_init_defaults(self):
        """Test client initialization with defaults."""
        client = skos.SKOSClient()
        assert client.cache_dir == skos.DEFAULT_CACHE_DIR
        assert "agrovoc" in client.endpoints
        assert "dbpedia" in client.endpoints
        assert client.timeout == 10.0

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
        """Test AGROVOC concept lookup."""
        client = skos.SKOSClient(cache_dir=tmp_path)

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
        client = skos.SKOSClient(cache_dir=tmp_path)
        mock_query.return_value = []

        result = client.lookup_concept("xyznonexistent", lang="en", source="agrovoc")
        assert result is None

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
        """Test handling of network errors."""
        import requests

        client = skos.SKOSClient(cache_dir=tmp_path)
        mock_get.side_effect = requests.RequestException("Network error")

        result = client._sparql_query("http://example.com", "SELECT ?x WHERE {}")
        assert result == []
