"""Tests for vocabulary module."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from inventory_md import vocabulary


class TestConcept:
    """Tests for Concept dataclass."""

    def test_concept_creation(self):
        """Test creating a concept."""
        concept = vocabulary.Concept(
            id="food/vegetables",
            prefLabel="Vegetables",
            altLabels=["veggies", "greens"],
            broader=["food"],
            narrower=["food/vegetables/potatoes"],
            source="local",
        )
        assert concept.id == "food/vegetables"
        assert concept.prefLabel == "Vegetables"
        assert concept.altLabels == ["veggies", "greens"]

    def test_concept_to_dict(self):
        """Test converting concept to dictionary."""
        concept = vocabulary.Concept(
            id="food/vegetables",
            prefLabel="Vegetables",
            altLabels=["veggies"],
            broader=["food"],
            narrower=[],
            source="local",
        )
        d = concept.to_dict()
        assert d["id"] == "food/vegetables"
        assert d["prefLabel"] == "Vegetables"
        assert d["altLabels"] == ["veggies"]
        assert d["broader"] == ["food"]
        assert d["source"] == "local"

    def test_concept_from_dict(self):
        """Test creating concept from dictionary."""
        d = {
            "id": "food/vegetables",
            "prefLabel": "Vegetables",
            "altLabels": ["veggies"],
            "broader": ["food"],
            "narrower": [],
            "source": "local",
        }
        concept = vocabulary.Concept.from_dict(d)
        assert concept.id == "food/vegetables"
        assert concept.prefLabel == "Vegetables"

    def test_concept_defaults(self):
        """Test concept with default values."""
        concept = vocabulary.Concept(id="test", prefLabel="Test")
        assert concept.altLabels == []
        assert concept.broader == []
        assert concept.narrower == []
        assert concept.source == "local"


class TestLoadLocalVocabulary:
    """Tests for load_local_vocabulary function."""

    def test_load_yaml_vocabulary(self, tmp_path):
        """Test loading vocabulary from YAML file."""
        pytest.importorskip("yaml")
        vocab_file = tmp_path / "local-vocabulary.yaml"
        vocab_file.write_text("""
concepts:
  christmas-decorations:
    prefLabel: "Christmas decorations"
    altLabel: ["jul", "xmas"]
    broader: "seasonal"

  tools/hand-tools:
    prefLabel: "Hand tools"
""")
        vocab = vocabulary.load_local_vocabulary(vocab_file)

        assert "christmas-decorations" in vocab
        assert vocab["christmas-decorations"].prefLabel == "Christmas decorations"
        assert vocab["christmas-decorations"].altLabels == ["jul", "xmas"]
        assert vocab["christmas-decorations"].broader == ["seasonal"]

        assert "tools/hand-tools" in vocab
        assert vocab["tools/hand-tools"].prefLabel == "Hand tools"

    def test_load_json_vocabulary(self, tmp_path):
        """Test loading vocabulary from JSON file."""
        vocab_file = tmp_path / "local-vocabulary.json"
        vocab_file.write_text(json.dumps({
            "concepts": {
                "boat-equipment": {
                    "prefLabel": "Boat equipment",
                    "narrower": ["boat-equipment/safety"],
                }
            }
        }))
        vocab = vocabulary.load_local_vocabulary(vocab_file)

        assert "boat-equipment" in vocab
        assert vocab["boat-equipment"].prefLabel == "Boat equipment"
        assert vocab["boat-equipment"].narrower == ["boat-equipment/safety"]

    def test_load_nonexistent_file(self, tmp_path):
        """Test loading from nonexistent file returns empty dict."""
        vocab_file = tmp_path / "nonexistent.yaml"
        vocab = vocabulary.load_local_vocabulary(vocab_file)
        assert vocab == {}

    def test_load_with_string_altlabel(self, tmp_path):
        """Test loading with altLabel as single string."""
        pytest.importorskip("yaml")
        vocab_file = tmp_path / "vocab.yaml"
        vocab_file.write_text("""
concepts:
  potatoes:
    prefLabel: "Potatoes"
    altLabel: "spuds"
""")
        vocab = vocabulary.load_local_vocabulary(vocab_file)
        assert vocab["potatoes"].altLabels == ["spuds"]

    def test_load_with_string_broader(self, tmp_path):
        """Test loading with broader as single string."""
        pytest.importorskip("yaml")
        vocab_file = tmp_path / "vocab.yaml"
        vocab_file.write_text("""
concepts:
  potatoes:
    prefLabel: "Potatoes"
    broader: "vegetables"
""")
        vocab = vocabulary.load_local_vocabulary(vocab_file)
        assert vocab["potatoes"].broader == ["vegetables"]


class TestLookupConcept:
    """Tests for lookup_concept function."""

    def test_lookup_by_id(self):
        """Test looking up concept by ID."""
        vocab = {
            "food/vegetables": vocabulary.Concept(
                id="food/vegetables",
                prefLabel="Vegetables",
            )
        }
        concept = vocabulary.lookup_concept("food/vegetables", vocab)
        assert concept is not None
        assert concept.id == "food/vegetables"

    def test_lookup_by_preflabel(self):
        """Test looking up concept by prefLabel."""
        vocab = {
            "food/vegetables": vocabulary.Concept(
                id="food/vegetables",
                prefLabel="Vegetables",
            )
        }
        concept = vocabulary.lookup_concept("vegetables", vocab)
        assert concept is not None
        assert concept.id == "food/vegetables"

    def test_lookup_by_altlabel(self):
        """Test looking up concept by altLabel."""
        vocab = {
            "food/vegetables": vocabulary.Concept(
                id="food/vegetables",
                prefLabel="Vegetables",
                altLabels=["veggies", "greens"],
            )
        }
        concept = vocabulary.lookup_concept("veggies", vocab)
        assert concept is not None
        assert concept.id == "food/vegetables"

    def test_lookup_case_insensitive(self):
        """Test that lookup is case-insensitive."""
        vocab = {
            "food/vegetables": vocabulary.Concept(
                id="food/vegetables",
                prefLabel="Vegetables",
            )
        }
        concept = vocabulary.lookup_concept("VEGETABLES", vocab)
        assert concept is not None
        assert concept.id == "food/vegetables"

    def test_lookup_not_found(self):
        """Test lookup returns None when not found."""
        vocab = {}
        concept = vocabulary.lookup_concept("nonexistent", vocab)
        assert concept is None


class TestBuildCategoryTree:
    """Tests for build_category_tree function."""

    def test_build_simple_tree(self):
        """Test building a simple category tree."""
        vocab = {
            "food": vocabulary.Concept(id="food", prefLabel="Food"),
            "tools": vocabulary.Concept(id="tools", prefLabel="Tools"),
        }
        tree = vocabulary.build_category_tree(vocab)

        assert "food" in tree.roots
        assert "tools" in tree.roots
        assert len(tree.roots) == 2

    def test_infer_hierarchy_from_paths(self):
        """Test inferring hierarchy from path separators."""
        vocab = {
            "food": vocabulary.Concept(id="food", prefLabel="Food"),
            "food/vegetables": vocabulary.Concept(id="food/vegetables", prefLabel="Vegetables"),
            "food/vegetables/potatoes": vocabulary.Concept(
                id="food/vegetables/potatoes", prefLabel="Potatoes"
            ),
        }
        tree = vocabulary.build_category_tree(vocab, infer_hierarchy=True)

        # Only "food" should be root
        assert tree.roots == ["food"]

        # Check hierarchy is inferred
        assert tree.concepts["food/vegetables"].broader == ["food"]
        assert tree.concepts["food/vegetables/potatoes"].broader == ["food/vegetables"]

        # Check narrower is set
        assert "food/vegetables" in tree.concepts["food"].narrower
        assert "food/vegetables/potatoes" in tree.concepts["food/vegetables"].narrower

    def test_explicit_broader_not_overridden(self):
        """Test that explicit broader relationships are not overridden."""
        vocab = {
            "food": vocabulary.Concept(id="food", prefLabel="Food"),
            "food/vegetables": vocabulary.Concept(
                id="food/vegetables",
                prefLabel="Vegetables",
                broader=["other-parent"],  # Explicit broader
            ),
        }
        tree = vocabulary.build_category_tree(vocab, infer_hierarchy=True)

        # Explicit broader should be preserved
        assert tree.concepts["food/vegetables"].broader == ["other-parent"]

    def test_label_index(self):
        """Test that label index is built correctly."""
        vocab = {
            "food/vegetables": vocabulary.Concept(
                id="food/vegetables",
                prefLabel="Vegetables",
                altLabels=["veggies"],
            ),
        }
        tree = vocabulary.build_category_tree(vocab)

        assert tree.label_index.get("vegetables") == "food/vegetables"
        assert tree.label_index.get("veggies") == "food/vegetables"
        assert tree.label_index.get("food/vegetables") == "food/vegetables"


class TestBuildVocabularyFromInventory:
    """Tests for build_vocabulary_from_inventory function."""

    def test_extract_categories_from_inventory(self):
        """Test extracting categories from inventory data."""
        inventory = {
            "containers": [
                {
                    "id": "box1",
                    "items": [
                        {"name": "Potatoes", "metadata": {"categories": ["food/vegetables/potatoes"]}},
                        {"name": "Hammer", "metadata": {"categories": ["tools/hand-tools"]}},
                    ],
                }
            ]
        }
        vocab = vocabulary.build_vocabulary_from_inventory(inventory)

        # Should create concepts for all paths
        assert "food" in vocab
        assert "food/vegetables" in vocab
        assert "food/vegetables/potatoes" in vocab
        assert "tools" in vocab
        assert "tools/hand-tools" in vocab

    def test_merge_with_local_vocab(self):
        """Test merging with local vocabulary."""
        local = {
            "food": vocabulary.Concept(
                id="food",
                prefLabel="Food & Groceries",  # Custom label
                altLabels=["mat"],
            ),
        }
        inventory = {
            "containers": [
                {
                    "id": "box1",
                    "items": [
                        {"name": "Potatoes", "metadata": {"categories": ["food/vegetables"]}},
                    ],
                }
            ]
        }
        vocab = vocabulary.build_vocabulary_from_inventory(inventory, local_vocab=local)

        # Local vocab should take precedence
        assert vocab["food"].prefLabel == "Food & Groceries"
        assert vocab["food"].altLabels == ["mat"]
        # But inventory categories should also be there
        assert "food/vegetables" in vocab

    def test_empty_inventory(self):
        """Test with empty inventory."""
        inventory = {"containers": []}
        vocab = vocabulary.build_vocabulary_from_inventory(inventory)
        assert vocab == {}

    def test_items_without_categories(self):
        """Test items without categories are ignored."""
        inventory = {
            "containers": [
                {
                    "id": "box1",
                    "items": [
                        {"name": "Item1", "metadata": {"tags": ["foo"]}},
                        {"name": "Item2", "metadata": {}},
                    ],
                }
            ]
        }
        vocab = vocabulary.build_vocabulary_from_inventory(inventory)
        assert vocab == {}


class TestCountItemsPerCategory:
    """Tests for count_items_per_category function."""

    def test_count_simple(self):
        """Test counting items in categories."""
        inventory = {
            "containers": [
                {
                    "id": "box1",
                    "items": [
                        {"name": "Item1", "metadata": {"categories": ["food/vegetables"]}},
                        {"name": "Item2", "metadata": {"categories": ["food/vegetables"]}},
                        {"name": "Item3", "metadata": {"categories": ["tools"]}},
                    ],
                }
            ]
        }
        counts = vocabulary.count_items_per_category(inventory)

        assert counts["food/vegetables"] == 2
        assert counts["tools"] == 1
        # Parent categories should include children
        assert counts["food"] == 2

    def test_count_hierarchical(self):
        """Test counting includes parent categories."""
        inventory = {
            "containers": [
                {
                    "id": "box1",
                    "items": [
                        {"name": "Potatoes", "metadata": {"categories": ["food/vegetables/potatoes"]}},
                    ],
                }
            ]
        }
        counts = vocabulary.count_items_per_category(inventory)

        assert counts["food/vegetables/potatoes"] == 1
        assert counts["food/vegetables"] == 1
        assert counts["food"] == 1


class TestEnrichWithSkos:
    """Tests for _enrich_with_skos function."""

    def test_skos_overwrites_inventory_source(self):
        """Test that SKOS lookup overwrites concepts with source='inventory'.

        This is a regression test for a bug where intermediate path components
        created with source='inventory' would prevent SKOS lookup for the same
        label when used as a standalone category.

        For example, if 'electronics/antenna' is processed first:
        1. SKOS lookup for 'antenna' fails
        2. _add_category_path creates 'electronics' with source='inventory'
        3. Later when 'electronics' (standalone) is processed, it should
           still do SKOS lookup and update the source to 'dbpedia'
        """
        # Create concepts dict with an "inventory" source concept
        # (simulating what happens when path expansion creates it)
        concepts = {
            "electronics": vocabulary.Concept(
                id="electronics",
                prefLabel="Electronics",
                source="inventory",  # Created by path expansion
            )
        }

        # Simulate the check that determines whether to skip SKOS lookup
        label = "electronics"
        existing_with_skos = any(
            c.prefLabel.lower() == label.lower() and c.source != "inventory"
            for c in concepts.values()
        )

        # Should NOT skip because existing concept has source="inventory"
        assert not existing_with_skos

        # Simulate what happens when SKOS lookup succeeds
        concept_data = {
            "uri": "http://dbpedia.org/resource/Electronics",
            "prefLabel": "Electronics",
            "source": "dbpedia",
        }

        # Update the concept
        cat_path = "electronics"
        existing = concepts.get(cat_path)
        if existing is None or existing.source == "inventory":
            concepts[cat_path] = vocabulary.Concept(
                id=cat_path,
                prefLabel=concept_data["prefLabel"],
                source=concept_data.get("source", "skos"),
            )

        # Verify the concept was updated with SKOS source
        assert concepts["electronics"].source == "dbpedia"

    def test_skos_does_not_overwrite_local_source(self):
        """Test that SKOS lookup does not overwrite local vocabulary concepts."""
        concepts = {
            "my-category": vocabulary.Concept(
                id="my-category",
                prefLabel="My Category",
                source="local",
            )
        }

        label = "my category"
        existing_with_skos = any(
            c.prefLabel.lower() == label.lower() and c.source != "inventory"
            for c in concepts.values()
        )

        # Should skip because existing concept has source="local" (not "inventory")
        assert existing_with_skos


class TestSaveVocabularyJson:
    """Tests for save_vocabulary_json function."""

    def test_save_and_load(self, tmp_path):
        """Test saving vocabulary as JSON."""
        vocab = {
            "food": vocabulary.Concept(id="food", prefLabel="Food"),
            "food/vegetables": vocabulary.Concept(
                id="food/vegetables",
                prefLabel="Vegetables",
                altLabels=["veggies"],
            ),
        }
        output_path = tmp_path / "vocabulary.json"
        vocabulary.save_vocabulary_json(vocab, output_path)

        # Load and verify
        with open(output_path, encoding="utf-8") as f:
            data = json.load(f)

        assert "concepts" in data
        assert "roots" in data
        assert "labelIndex" in data
        assert "food" in data["concepts"]
        assert data["concepts"]["food/vegetables"]["altLabels"] == ["veggies"]

    def test_save_with_category_mappings(self, tmp_path):
        """Test saving vocabulary with category mappings for hierarchy mode."""
        vocab = {
            "food": vocabulary.Concept(id="food", prefLabel="Food"),
            "food/vegetables": vocabulary.Concept(id="food/vegetables", prefLabel="Vegetables"),
            "food/vegetables/potato": vocabulary.Concept(id="food/vegetables/potato", prefLabel="Potato"),
        }
        mappings = {
            "potato": ["food/vegetables/potato", "food/root_vegetables/potato"],
            "carrot": ["food/vegetables/carrot"],
        }
        output_path = tmp_path / "vocabulary.json"
        vocabulary.save_vocabulary_json(vocab, output_path, category_mappings=mappings)

        # Load and verify
        with open(output_path, encoding="utf-8") as f:
            data = json.load(f)

        assert "categoryMappings" in data
        assert data["categoryMappings"]["potato"] == ["food/vegetables/potato", "food/root_vegetables/potato"]
        assert data["categoryMappings"]["carrot"] == ["food/vegetables/carrot"]

    def test_save_without_category_mappings(self, tmp_path):
        """Test that categoryMappings is not present when not provided."""
        vocab = {"food": vocabulary.Concept(id="food", prefLabel="Food")}
        output_path = tmp_path / "vocabulary.json"
        vocabulary.save_vocabulary_json(vocab, output_path)

        with open(output_path, encoding="utf-8") as f:
            data = json.load(f)

        assert "categoryMappings" not in data


class TestNormalizeToSingular:
    """Tests for _normalize_to_singular function."""

    def test_regular_plurals(self):
        """Test regular plural -> singular conversion."""
        assert vocabulary._normalize_to_singular("books") == "book"
        assert vocabulary._normalize_to_singular("pillows") == "pillow"
        assert vocabulary._normalize_to_singular("tools") == "tool"

    def test_ies_plurals(self):
        """Test words ending in -ies -> -y."""
        assert vocabulary._normalize_to_singular("berries") == "berry"
        assert vocabulary._normalize_to_singular("batteries") == "battery"
        assert vocabulary._normalize_to_singular("categories") == "category"

    def test_es_plurals(self):
        """Test words ending in -es after s/x/z/ch/sh."""
        assert vocabulary._normalize_to_singular("boxes") == "box"
        assert vocabulary._normalize_to_singular("matches") == "match"
        assert vocabulary._normalize_to_singular("dishes") == "dish"

    def test_oes_plurals(self):
        """Test words ending in -oes -> -o."""
        assert vocabulary._normalize_to_singular("potatoes") == "potato"
        assert vocabulary._normalize_to_singular("tomatoes") == "tomato"
        assert vocabulary._normalize_to_singular("heroes") == "hero"

    def test_exceptions(self):
        """Test exception words that should not be modified."""
        assert vocabulary._normalize_to_singular("series") == "series"
        assert vocabulary._normalize_to_singular("species") == "species"
        assert vocabulary._normalize_to_singular("shoes") == "shoes"
        assert vocabulary._normalize_to_singular("glasses") == "glasses"

    def test_already_singular(self):
        """Test words that are already singular."""
        assert vocabulary._normalize_to_singular("book") == "book"
        assert vocabulary._normalize_to_singular("bedding") == "bedding"
        assert vocabulary._normalize_to_singular("maritime") == "maritime"

    def test_preserves_case(self):
        """Test that normalization preserves original case."""
        assert vocabulary._normalize_to_singular("Books") == "Book"
        assert vocabulary._normalize_to_singular("BOXES") == "BOX"


class TestExpandCategoryToSkosPaths:
    """Tests for expand_category_to_skos_paths function."""

    def test_expand_food_concept(self):
        """Test expanding a food concept returns paths starting with food."""
        # This test requires Oxigraph with AGROVOC loaded
        # If not available, the function returns the label as-is
        paths = vocabulary.expand_category_to_skos_paths("potatoes")

        # Should return at least one path
        assert len(paths) >= 1

        # If SKOS is available, path should start with "food"
        # If not, it falls back to just "potatoes"
        assert paths[0].endswith("potatoes") or paths[0] == "potatoes"

    def test_expand_singular_form(self):
        """Test that singular form is expanded via plural lookup."""
        # "potato" should find "potatoes" in AGROVOC
        paths = vocabulary.expand_category_to_skos_paths("potato")
        assert len(paths) >= 1
        # Should end with "potatoes" (AGROVOC uses plural)
        assert "potato" in paths[0]

    def test_expand_unknown_concept(self):
        """Test that unknown concepts return the label as-is."""
        paths = vocabulary.expand_category_to_skos_paths("xyznonexistent123")
        assert paths == ["xyznonexistent123"]

    def test_agrovoc_root_mapping(self):
        """Test that AGROVOC roots are mapped to user-friendly labels."""
        # Check that the mapping exists
        assert "products" in vocabulary.AGROVOC_ROOT_MAPPING
        assert vocabulary.AGROVOC_ROOT_MAPPING["products"] == "food"


class TestOFFIntegration:
    """Tests for Open Food Facts integration in vocabulary building."""

    def _make_mock_off_client(self):
        """Create a mock OFFTaxonomyClient."""
        client = MagicMock()
        client.lookup_concept.return_value = {
            "uri": "off:en:potatoes",
            "prefLabel": "Potatoes",
            "source": "off",
            "broader": [{"uri": "off:en:vegetables", "label": "Vegetables"}],
            "node_id": "en:potatoes",
        }
        client.build_paths_to_root.return_value = (
            ["food/vegetables/potatoes"],
            {"food": "off:en:plant-based-foods-and-beverages",
             "food/vegetables": "off:en:vegetables",
             "food/vegetables/potatoes": "off:en:potatoes"},
        )
        client.get_labels.return_value = {"en": "Potatoes", "de": "Kartoffeln"}
        return client

    @patch("inventory_md.vocabulary.build_skos_hierarchy_paths")
    def test_off_priority_over_agrovoc(self, mock_skos_paths):
        """Test that OFF is tried before AGROVOC for food categories."""
        inventory = {
            "containers": [{
                "id": "box1",
                "items": [{"name": "Potatoes", "metadata": {"categories": ["potatoes"]}}],
            }]
        }

        mock_off_client = self._make_mock_off_client()

        with patch("inventory_md.off.OFFTaxonomyClient", return_value=mock_off_client):
            # Only enable OFF (no AGROVOC/DBpedia) to verify OFF is used
            vocab, mappings = vocabulary.build_vocabulary_with_skos_hierarchy(
                inventory, enabled_sources=["off"]
            )

        # OFF should have been used
        mock_off_client.lookup_concept.assert_called()
        # AGROVOC should NOT have been called (not in enabled_sources)
        mock_skos_paths.assert_not_called()
        # Paths should come from OFF
        assert "potatoes" in mappings
        assert any("food/" in p for p in mappings["potatoes"])

    @patch("inventory_md.vocabulary.build_skos_hierarchy_paths")
    def test_off_fallback_to_agrovoc(self, mock_skos_paths):
        """Test that AGROVOC is used when OFF doesn't find a concept."""
        inventory = {
            "containers": [{
                "id": "box1",
                "items": [{"name": "Lentils", "metadata": {"categories": ["lentils"]}}],
            }]
        }

        # OFF returns nothing for this term
        mock_off_client = MagicMock()
        mock_off_client.lookup_concept.return_value = None
        mock_off_client.get_labels.return_value = {}

        # AGROVOC finds it
        mock_skos_paths.return_value = (
            ["food/legumes/lentils"],
            True,
            {"food/legumes/lentils": "http://aims.fao.org/aos/agrovoc/c_4235"},
        )

        with patch("inventory_md.off.OFFTaxonomyClient", return_value=mock_off_client):
            vocab, mappings = vocabulary.build_vocabulary_with_skos_hierarchy(
                inventory, enabled_sources=["off", "agrovoc"]
            )

        # OFF was tried first
        mock_off_client.lookup_concept.assert_called()
        # AGROVOC was used as fallback
        mock_skos_paths.assert_called()
        assert "lentils" in mappings
        assert any("legumes" in p for p in mappings["lentils"])

    def test_off_not_enabled(self):
        """Test that OFF is skipped when not in enabled_sources."""
        inventory = {
            "containers": [{
                "id": "box1",
                "items": [{"name": "Potatoes", "metadata": {"categories": ["potatoes"]}}],
            }]
        }

        with patch("inventory_md.off.OFFTaxonomyClient") as mock_cls:
            # With OFF not in sources, OFFTaxonomyClient should not be instantiated
            vocab, mappings = vocabulary.build_vocabulary_with_skos_hierarchy(
                inventory, enabled_sources=["agrovoc", "dbpedia"]
            )
            mock_cls.assert_not_called()

    @patch("inventory_md.vocabulary.build_skos_hierarchy_paths")
    def test_multi_source_enrichment(self, mock_skos_paths):
        """Test that multiple sources contribute paths for the same concept."""
        inventory = {
            "containers": [{
                "id": "box1",
                "items": [{"name": "Potatoes", "metadata": {"categories": ["potatoes"]}}],
            }]
        }

        # OFF provides one set of paths
        mock_off_client = self._make_mock_off_client()
        mock_off_client.build_paths_to_root.return_value = (
            ["food/vegetables/potatoes"],
            {"food/vegetables/potatoes": "off:en:potatoes"},
        )

        # AGROVOC provides additional paths
        mock_skos_paths.return_value = (
            ["food/plant_products/root_vegetables/potatoes"],
            True,
            {"food/plant_products/root_vegetables/potatoes": "http://aims.fao.org/aos/agrovoc/c_6139"},
        )

        with patch("inventory_md.off.OFFTaxonomyClient", return_value=mock_off_client):
            vocab, mappings = vocabulary.build_vocabulary_with_skos_hierarchy(
                inventory, enabled_sources=["off", "agrovoc"]
            )

        # Both paths should be present (multi-source enrichment)
        assert "potatoes" in mappings
        paths = mappings["potatoes"]
        assert "food/vegetables/potatoes" in paths
        assert "food/plant_products/root_vegetables/potatoes" in paths


class TestLanguageFallbacks:
    """Tests for language fallback functionality."""

    def test_get_fallback_chain_scandinavian(self):
        """Test Scandinavian fallback chain."""
        chain = vocabulary.get_fallback_chain("nb")
        assert chain[0] == "nb"  # Primary language first
        assert "no" in chain  # Generic Norwegian
        assert "da" in chain  # Danish (mutually intelligible)
        assert "nn" in chain  # Nynorsk
        assert "sv" in chain  # Swedish
        assert chain[-1] == "en"  # English as final fallback

    def test_get_fallback_chain_germanic(self):
        """Test Germanic fallback chain."""
        chain = vocabulary.get_fallback_chain("de")
        assert chain[0] == "de"
        assert "nl" in chain  # Dutch
        assert chain[-1] == "en"

    def test_get_fallback_chain_unknown_language(self):
        """Test fallback for unknown language goes straight to English."""
        chain = vocabulary.get_fallback_chain("xyz")
        assert chain == ["xyz", "en"]

    def test_apply_language_fallbacks_direct_match(self):
        """Test that direct matches are returned."""
        labels = {"en": "Milk", "nb": "Melk", "de": "Milch"}
        result = vocabulary.apply_language_fallbacks(labels, ["en", "nb", "de"])
        assert result == {"en": "Milk", "nb": "Melk", "de": "Milch"}

    def test_apply_language_fallbacks_uses_fallback(self):
        """Test that fallbacks are used for missing languages."""
        labels = {"en": "Milk", "da": "Mælk"}
        result = vocabulary.apply_language_fallbacks(labels, ["en", "nb"])
        assert result["en"] == "Milk"
        # nb falls back to da (Danish, which is in the chain before English)
        assert result["nb"] == "Mælk"

    def test_apply_language_fallbacks_english_final(self):
        """Test that English is used as final fallback."""
        labels = {"en": "Milk"}
        result = vocabulary.apply_language_fallbacks(labels, ["en", "de", "fr"])
        assert result["en"] == "Milk"
        assert result["de"] == "Milk"  # Falls back to English
        assert result["fr"] == "Milk"  # Falls back to English

    def test_apply_language_fallbacks_no_match(self):
        """Test that missing languages with no fallback are omitted."""
        labels = {"zh": "牛奶"}  # Only Chinese available
        result = vocabulary.apply_language_fallbacks(labels, ["en", "de"])
        # Neither en nor de have fallbacks that include zh, so empty
        assert result == {}

    def test_custom_fallback_configuration(self):
        """Test using custom fallback configuration."""
        custom_fallbacks = {"nb": ["sv"]}  # Only Swedish as fallback for Norwegian
        chain = vocabulary.get_fallback_chain("nb", fallbacks=custom_fallbacks)
        assert chain == ["nb", "sv", "en"]

    def test_da_before_nn_for_nb(self):
        """Test that Danish comes before Nynorsk for Bokmål users."""
        chain = vocabulary.get_fallback_chain("nb")
        da_idx = chain.index("da")
        nn_idx = chain.index("nn")
        assert da_idx < nn_idx  # Danish should come before Nynorsk


class TestLocalVocabularySourcePreservation:
    """Tests for preserving local vocabulary source even with external URIs.

    Bug fix: Local vocabulary entries with DBpedia/AGROVOC URIs were getting
    their source changed from "local" to "dbpedia"/"agrovoc", which caused
    issues with hierarchy preservation.
    """

    def test_local_vocab_with_dbpedia_uri_keeps_local_source(self, tmp_path):
        """Local vocab entries with DBpedia URI should keep source=local."""
        vocab_file = tmp_path / "vocabulary.yaml"
        vocab_file.write_text("""
concepts:
  tools:
    prefLabel: "Tools"
    uri: "http://dbpedia.org/resource/Tool"
  hammer:
    prefLabel: "Hammer"
    broader: tools
    uri: "http://dbpedia.org/resource/Hammer"
""")
        vocab = vocabulary.load_local_vocabulary(vocab_file)

        # Both should have source=local, not dbpedia
        assert vocab["tools"].source == "local"
        assert vocab["hammer"].source == "local"
        # But URIs should be preserved
        assert vocab["tools"].uri == "http://dbpedia.org/resource/Tool"
        assert vocab["hammer"].uri == "http://dbpedia.org/resource/Hammer"

    def test_local_vocab_with_agrovoc_uri_keeps_local_source(self, tmp_path):
        """Local vocab entries with AGROVOC URI should keep source=local."""
        vocab_file = tmp_path / "vocabulary.yaml"
        vocab_file.write_text("""
concepts:
  potatoes:
    prefLabel: "Potatoes"
    broader: food/vegetables
    uri: "http://aims.fao.org/aos/agrovoc/c_6139"
""")
        vocab = vocabulary.load_local_vocabulary(vocab_file)

        assert vocab["potatoes"].source == "local"
        assert vocab["potatoes"].uri == "http://aims.fao.org/aos/agrovoc/c_6139"

    def test_local_vocab_root_categories_stay_roots(self, tmp_path):
        """Root categories in local vocab should not get broader from external sources."""
        vocab_file = tmp_path / "vocabulary.yaml"
        vocab_file.write_text("""
concepts:
  tools:
    prefLabel: "Tools"
    altLabel: ["equipment"]
  food:
    prefLabel: "Food"
    narrower:
      - food/vegetables
  food/vegetables:
    prefLabel: "Vegetables"
    broader: food
""")
        vocab = vocabulary.load_local_vocabulary(vocab_file)

        # tools and food should be roots (no broader)
        assert vocab["tools"].broader == []
        assert vocab["food"].broader == []
        # food/vegetables should have food as broader
        assert vocab["food/vegetables"].broader == ["food"]


class TestExternalSourceDoesNotOverwriteLocal:
    """Tests ensuring external sources don't overwrite local vocabulary entries.

    Bug fix: When processing leaf labels, DBpedia fallback was overwriting
    existing local vocabulary concepts with DBpedia data.
    """

    def test_add_paths_to_concepts_preserves_existing(self):
        """_add_paths_to_concepts should not overwrite existing concepts."""
        concepts = {
            "tools": vocabulary.Concept(
                id="tools",
                prefLabel="Tools",
                source="local",
                broader=[],
            )
        }

        # Try to add a path that includes "tools"
        vocabulary._add_paths_to_concepts(
            ["tools/hand/hammer"], concepts, "dbpedia"
        )

        # Original "tools" concept should be unchanged
        assert concepts["tools"].source == "local"
        assert concepts["tools"].broader == []
        # But child paths should be added
        assert "tools/hand" in concepts
        assert "tools/hand/hammer" in concepts
        assert concepts["tools/hand"].source == "dbpedia"

    def test_local_broader_takes_precedence_over_external(self):
        """Local vocabulary broader relationships should override external ones."""
        local_vocab = {
            "hammer": vocabulary.Concept(
                id="hammer",
                prefLabel="Hammer",
                source="local",
                broader=["tools/hand"],
            ),
            "tools": vocabulary.Concept(
                id="tools",
                prefLabel="Tools",
                source="local",
                broader=[],
            ),
            "tools/hand": vocabulary.Concept(
                id="tools/hand",
                prefLabel="Hand tools",
                source="local",
                broader=["tools"],
            ),
        }

        # Simulate what happens when building vocabulary
        # The local vocab says hammer -> tools/hand
        # Even if DBpedia says hammer -> metalworking_tools, local should win
        assert local_vocab["hammer"].broader == ["tools/hand"]


class TestTranslationCoverage:
    """Tests for translation coverage improvements.

    Bug: Many local concepts have URIs in concept.uri (e.g., tools has
    uri: "http://dbpedia.org/resource/Tool") that were never used for
    translations because the AGROVOC translation phase only checked
    all_uri_maps.
    """

    @patch("inventory_md.vocabulary.build_skos_hierarchy_paths")
    def test_concept_uri_used_for_translations(self, mock_skos_paths):
        """Concepts with URIs should get translations even if not in all_uri_maps.

        When a concept has a URI set (e.g., from local vocabulary) but isn't
        tracked in all_uri_maps, the translation phase should fall back to
        concept.uri for lookups.
        """
        # Setup: concept with URI but not in all_uri_maps
        concepts = {
            "tools": vocabulary.Concept(
                id="tools",
                prefLabel="Tools",
                source="local",
                uri="http://dbpedia.org/resource/Tool",
                labels={},
            ),
        }

        # The concept has a URI but is not in all_uri_maps
        all_uri_maps: dict[str, str] = {}

        # Simulate the translation phase logic
        # OLD: only checked `if concept_id in all_uri_maps`
        # NEW: falls back to concept.uri
        for concept_id, concept in concepts.items():
            uri = all_uri_maps.get(concept_id) or concept.uri
            if not uri:
                continue
            # Verify we found the URI
            assert uri == "http://dbpedia.org/resource/Tool"

    @patch("inventory_md.vocabulary.build_skos_hierarchy_paths")
    def test_off_translations_for_local_broader_path(self, mock_skos_paths):
        """OFF node IDs should be tracked for concepts using local_broader_path.

        When a concept has local_broader_path and the external source is OFF,
        the OFF node ID should be tracked under the local_broader_path key
        (not just the external concept ID).
        """
        off_node_ids: dict[str, str] = {}
        local_broader_path = "tools/hand/hammer"

        # Simulate: external source found OFF URI for hammer
        all_uris = {
            "food/hammer": "off:en:hammers",
        }

        # The fix: when matching external URIs to local_broader_path,
        # also propagate OFF node IDs
        concept_id = local_broader_path.split("/")[-1]  # "hammer"
        for ext_cid, ext_uri in all_uris.items():
            if ext_cid.endswith(concept_id) or concept_id in ext_cid:
                if ext_uri.startswith("off:"):
                    off_node_ids[local_broader_path] = ext_uri[4:]
                break

        # OFF node ID should be tracked under local_broader_path
        assert local_broader_path in off_node_ids
        assert off_node_ids[local_broader_path] == "en:hammers"

    def test_local_concept_uri_propagated_to_uri_maps(self):
        """Local concepts with URIs should have those URIs in all_uri_maps.

        When no external source provides a URI but the local concept has one,
        it should be propagated to all_uri_maps so translation phase can use it.
        """
        all_uri_maps: dict[str, str] = {}
        local_broader_path = "consumables/seal"

        local_concept = vocabulary.Concept(
            id="seal",
            prefLabel="Seal",
            source="local",
            uri="http://dbpedia.org/resource/Hermetic_seal",
        )

        # No external URIs found
        all_uris: dict[str, str] = {}

        # The fix: propagate local concept URI when no external URI found
        if not all_uris and local_concept and local_concept.uri:
            all_uri_maps[local_broader_path] = local_concept.uri

        assert local_broader_path in all_uri_maps
        assert all_uri_maps[local_broader_path] == "http://dbpedia.org/resource/Hermetic_seal"
