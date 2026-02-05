"""Tests for Open Food Facts taxonomy client."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from inventory_md.off import OFF_ROOT_MAPPING, OFFTaxonomyClient, _generate_variations


def _make_node(node_id, names=None, synonyms=None, parents=None, children=None):
    """Create a mock TaxonomyNode."""
    node = MagicMock()
    node.id = node_id
    node.names = names or {}
    node.synonyms = synonyms or {}
    node.parents = parents or []
    node.children = children or []
    node.get_localized_name = lambda lang: names.get(lang, node_id) if names else node_id
    return node


def _build_mock_taxonomy():
    """Build a small mock taxonomy for testing.

    Hierarchy:
        plant-based foods and beverages
        ├── condiments
        │   └── soy sauces
        └── sauces
            └── soy sauces (same node, DAG)
    """
    root = _make_node(
        "en:plant-based-foods-and-beverages",
        names={"en": "Plant-based foods and beverages", "de": "Pflanzliche Lebensmittel und Getränke"},
    )
    condiments = _make_node(
        "en:condiments",
        names={"en": "Condiments", "de": "Würzmittel"},
    )
    sauces = _make_node(
        "en:sauces",
        names={"en": "Sauces", "de": "Soßen"},
    )
    soy_sauces = _make_node(
        "en:soy-sauces",
        names={"en": "Soy sauces", "de": "Sojasossen", "fr": "Sauces au soja"},
        synonyms={"en": ["Soy sauces", "Soya sauces", "Shoyu", "Soy sauce"]},
    )
    potatoes = _make_node(
        "en:potatoes",
        names={"en": "Potatoes", "de": "Kartoffeln", "nb": "Poteter"},
        synonyms={"en": ["Potatoes", "Potato"]},
    )
    vegetables = _make_node(
        "en:vegetables",
        names={"en": "Vegetables", "de": "Gemüse"},
    )
    unknown_root = _make_node(
        "en:bulk",
        names={"en": "Bulk"},
    )

    # Wire up hierarchy
    root.parents = []
    root.children = [condiments, sauces]
    condiments.parents = [root]
    condiments.children = [soy_sauces]
    sauces.parents = [root]
    sauces.children = [soy_sauces]
    soy_sauces.parents = [condiments, sauces]  # DAG: two parents
    soy_sauces.children = []

    unknown_root.parents = []
    unknown_root.children = []

    vegetables.parents = [root]
    vegetables.children = [potatoes]
    root.children.append(vegetables)
    potatoes.parents = [vegetables]
    potatoes.children = []

    # Build taxonomy dict
    nodes = {
        "en:plant-based-foods-and-beverages": root,
        "en:condiments": condiments,
        "en:sauces": sauces,
        "en:soy-sauces": soy_sauces,
        "en:potatoes": potatoes,
        "en:vegetables": vegetables,
        "en:bulk": unknown_root,
    }

    taxonomy = MagicMock()
    taxonomy.__contains__ = lambda self, key: key in nodes
    taxonomy.__getitem__ = lambda self, key: nodes[key]
    taxonomy.__iter__ = lambda self: iter(nodes)
    taxonomy.__len__ = lambda self: len(nodes)
    taxonomy.values = lambda: nodes.values()
    taxonomy.iter_nodes = lambda: iter(nodes.values())
    taxonomy.keys = lambda: nodes.keys()

    return taxonomy


@pytest.fixture
def off_client():
    """Create an OFFTaxonomyClient with a mocked taxonomy."""
    client = OFFTaxonomyClient(languages=["en", "de"])
    mock_taxonomy = _build_mock_taxonomy()
    client._taxonomy = mock_taxonomy
    return client


class TestLookupConcept:
    """Tests for OFFTaxonomyClient.lookup_concept."""

    def test_lookup_by_english_name(self, off_client):
        """Test looking up a concept by its English name."""
        result = off_client.lookup_concept("soy sauces", lang="en")
        assert result is not None
        assert result["uri"] == "off:en:soy-sauces"
        assert result["prefLabel"] == "Soy sauces"
        assert result["source"] == "off"
        assert len(result["broader"]) == 2  # condiments + sauces

    def test_lookup_by_synonym(self, off_client):
        """Test looking up a concept by a synonym."""
        result = off_client.lookup_concept("shoyu", lang="en")
        assert result is not None
        assert result["uri"] == "off:en:soy-sauces"

    def test_lookup_singular_plural(self, off_client):
        """Test that 'potato' finds 'en:potatoes' via plural variation."""
        result = off_client.lookup_concept("potato", lang="en")
        assert result is not None
        assert result["node_id"] == "en:potatoes"
        assert result["prefLabel"] == "Potatoes"

    def test_lookup_case_insensitive(self, off_client):
        """Test case-insensitive matching."""
        result = off_client.lookup_concept("SOY SAUCES", lang="en")
        assert result is not None
        assert result["node_id"] == "en:soy-sauces"

    def test_lookup_not_found(self, off_client):
        """Test that non-food terms return None."""
        result = off_client.lookup_concept("xyznonexistent123", lang="en")
        assert result is None

    def test_lookup_returns_broader(self, off_client):
        """Test that broader concepts are included in result."""
        result = off_client.lookup_concept("potatoes", lang="en")
        assert result is not None
        broader_labels = [b["label"] for b in result["broader"]]
        assert "Vegetables" in broader_labels


class TestBuildPathsToRoot:
    """Tests for OFFTaxonomyClient.build_paths_to_root."""

    def test_paths_for_soy_sauces(self, off_client):
        """Test that soy sauces has multiple paths (DAG)."""
        paths, uri_map = off_client.build_paths_to_root("en:soy-sauces", lang="en")
        assert len(paths) >= 2  # At least condiments and sauces paths

        # All paths should start with "food" (mapped from root)
        for path in paths:
            assert path.startswith("food/"), f"Path should start with food/: {path}"

        # All paths should end with soy_sauces
        for path in paths:
            assert path.endswith("soy_sauces"), f"Path should end with soy_sauces: {path}"

    def test_paths_for_potatoes(self, off_client):
        """Test hierarchy paths for potatoes."""
        paths, uri_map = off_client.build_paths_to_root("en:potatoes", lang="en")
        assert len(paths) >= 1
        assert any("vegetables" in p for p in paths)
        assert all(p.startswith("food/") for p in paths)

    def test_uri_map_populated(self, off_client):
        """Test that uri_map contains entries for path components."""
        paths, uri_map = off_client.build_paths_to_root("en:potatoes", lang="en")
        assert len(uri_map) > 0
        # Should have entries with "off:" prefix
        for _concept_id, uri in uri_map.items():
            assert uri.startswith("off:")

    def test_root_node_returns_single_path(self, off_client):
        """Test that a root node without mapping returns itself."""
        paths, uri_map = off_client.build_paths_to_root("en:bulk", lang="en")
        assert len(paths) == 1
        assert paths[0] == "bulk"

    def test_nonexistent_node(self, off_client):
        """Test that nonexistent node returns empty."""
        paths, uri_map = off_client.build_paths_to_root("en:nonexistent", lang="en")
        assert paths == []
        assert uri_map == {}


class TestGetLabels:
    """Tests for OFFTaxonomyClient.get_labels."""

    def test_get_labels_multiple_languages(self, off_client):
        """Test getting labels in multiple languages."""
        labels = off_client.get_labels("en:soy-sauces", ["en", "de", "fr"])
        assert labels["en"] == "Soy sauces"
        assert labels["de"] == "Sojasossen"
        assert labels["fr"] == "Sauces au soja"

    def test_get_labels_missing_language_with_fallback(self, off_client):
        """Test that missing languages get fallback values."""
        labels = off_client.get_labels("en:soy-sauces", ["en", "nb"])
        assert "en" in labels
        # With fallbacks enabled, nb gets the English fallback since no
        # Norwegian or Scandinavian alternatives exist for soy-sauces
        assert "nb" in labels
        assert labels["nb"] == labels["en"]  # Fallback to English

    def test_get_labels_missing_language_no_fallback(self, off_client):
        """Test that missing languages are omitted when fallbacks disabled."""
        labels = off_client.get_labels("en:soy-sauces", ["en", "nb"], use_fallbacks=False)
        assert "en" in labels
        assert "nb" not in labels  # No Norwegian name, no fallback

    def test_get_labels_nonexistent_node(self, off_client):
        """Test that nonexistent node returns empty dict."""
        labels = off_client.get_labels("en:nonexistent", ["en"])
        assert labels == {}

    def test_potatoes_has_norwegian(self, off_client):
        """Test that potatoes has Norwegian translation."""
        labels = off_client.get_labels("en:potatoes", ["en", "de", "nb"])
        assert labels["nb"] == "Poteter"
        assert labels["de"] == "Kartoffeln"


class TestRootMapping:
    """Tests for OFF_ROOT_MAPPING."""

    def test_common_roots_map_to_food(self):
        """Test that common food top-level categories map to 'food'."""
        food_roots = [
            "plant-based foods and beverages",
            "beverages",
            "meats",
            "seafood",
            "dairies",
            "condiments",
        ]
        for root in food_roots:
            assert OFF_ROOT_MAPPING.get(root) == "food", f"'{root}' should map to 'food'"

    def test_mapping_applied_in_paths(self, off_client):
        """Test that root mapping is applied in build_paths_to_root."""
        paths, _ = off_client.build_paths_to_root("en:condiments", lang="en")
        # "Plant-based foods and beverages" should be mapped to "food"
        assert all(p.startswith("food") for p in paths)


class TestGenerateVariations:
    """Tests for _generate_variations helper."""

    def test_singular_to_plural(self):
        """Test generating plural from singular."""
        vars = _generate_variations("potato")
        assert "potatoes" in vars

    def test_plural_to_singular(self):
        """Test generating singular from plural."""
        vars = _generate_variations("potatoes")
        assert "potato" in vars

    def test_ies_plural(self):
        """Test -y/-ies variation."""
        vars = _generate_variations("berry")
        assert "berries" in vars

        vars = _generate_variations("berries")
        assert "berry" in vars

    def test_es_plural(self):
        """Test -es variation for s/x/z/ch/sh endings."""
        vars = _generate_variations("box")
        assert "boxes" in vars

        vars = _generate_variations("boxes")
        assert "box" in vars

    def test_no_double_s(self):
        """Test that words ending in 'ss' don't lose the second s."""
        vars = _generate_variations("glasses")
        # "glasses" -> should produce "glass" (remove es after ss)
        assert "glass" in vars


class TestImportGuard:
    """Tests for graceful handling when openfoodfacts is not installed."""

    def test_missing_openfoodfacts_returns_none(self):
        """Test that lookup returns None if openfoodfacts is not importable."""
        client = OFFTaxonomyClient()
        with patch.dict("sys.modules", {"openfoodfacts": None, "openfoodfacts.taxonomy": None}):
            # Reset cached taxonomy
            client._taxonomy = None
            client._label_index = None
            with patch("inventory_md.off.OFFTaxonomyClient._get_taxonomy", return_value=None):
                result = client.lookup_concept("soy sauce")
                assert result is None
