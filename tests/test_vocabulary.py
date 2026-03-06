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
            altLabels={"en": ["veggies", "greens"]},
            broader=["food"],
            narrower=["food/vegetables/potatoes"],
            source="local",
        )
        assert concept.id == "food/vegetables"
        assert concept.prefLabel == "Vegetables"
        assert concept.altLabels == {"en": ["veggies", "greens"]}

    def test_concept_to_dict(self):
        """Test converting concept to dictionary."""
        concept = vocabulary.Concept(
            id="food/vegetables",
            prefLabel="Vegetables",
            altLabels={"en": ["veggies"]},
            broader=["food"],
            narrower=[],
            source="local",
        )
        d = concept.to_dict()
        assert d["id"] == "food/vegetables"
        assert d["prefLabel"] == "Vegetables"
        assert d["altLabels"] == {"en": ["veggies"]}
        assert d["broader"] == ["food"]
        assert d["source"] == "local"

    def test_concept_from_dict(self):
        """Test creating concept from dictionary."""
        d = {
            "id": "food/vegetables",
            "prefLabel": "Vegetables",
            "altLabels": {"en": ["veggies"]},
            "broader": ["food"],
            "narrower": [],
            "source": "local",
        }
        concept = vocabulary.Concept.from_dict(d)
        assert concept.id == "food/vegetables"
        assert concept.prefLabel == "Vegetables"
        assert concept.altLabels == {"en": ["veggies"]}

    def test_concept_from_dict_backward_compat_list(self):
        """Test creating concept from dictionary with legacy list altLabels."""
        d = {
            "id": "food/vegetables",
            "prefLabel": "Vegetables",
            "altLabels": ["veggies"],
            "broader": ["food"],
        }
        concept = vocabulary.Concept.from_dict(d)
        assert concept.altLabels == {"en": ["veggies"]}

    def test_concept_defaults(self):
        """Test concept with default values."""
        concept = vocabulary.Concept(id="test", prefLabel="Test")
        assert concept.altLabels == {}
        assert concept.broader == []
        assert concept.narrower == []
        assert concept.source == "local"

    def test_get_alt_labels_all(self):
        """Test get_alt_labels returns all labels when lang is None."""
        concept = vocabulary.Concept(
            id="food",
            prefLabel="Food",
            altLabels={"en": ["groceries", "provisions"], "nb": ["mat", "matvarer"]},
        )
        all_alts = concept.get_alt_labels()
        assert all_alts == ["groceries", "provisions", "mat", "matvarer"]

    def test_get_alt_labels_by_language(self):
        """Test get_alt_labels returns only labels for a specific language."""
        concept = vocabulary.Concept(
            id="food",
            prefLabel="Food",
            altLabels={"en": ["groceries"], "nb": ["mat"]},
        )
        assert concept.get_alt_labels("en") == ["groceries"]
        assert concept.get_alt_labels("nb") == ["mat"]
        assert concept.get_alt_labels("de") == []

    def test_get_all_alt_labels_flat_deduplicates(self):
        """Test get_all_alt_labels_flat deduplicates across languages."""
        concept = vocabulary.Concept(
            id="sport",
            prefLabel="Sports",
            altLabels={"en": ["sport", "athletics"], "nb": ["sport", "idrett"]},
        )
        flat = concept.get_all_alt_labels_flat()
        assert flat == ["sport", "athletics", "idrett"]


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
        assert vocab["christmas-decorations"].altLabels == {"en": ["jul", "xmas"]}
        assert vocab["christmas-decorations"].broader == ["seasonal"]

        assert "tools/hand-tools" in vocab
        assert vocab["tools/hand-tools"].prefLabel == "Hand tools"

    def test_load_json_vocabulary(self, tmp_path):
        """Test loading vocabulary from JSON file."""
        vocab_file = tmp_path / "local-vocabulary.json"
        vocab_file.write_text(
            json.dumps(
                {
                    "concepts": {
                        "boat-equipment": {
                            "prefLabel": "Boat equipment",
                            "narrower": ["boat-equipment/safety"],
                        }
                    }
                }
            )
        )
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
        assert vocab["potatoes"].altLabels == {"en": ["spuds"]}

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

    def test_load_with_language_tagged_altlabels(self, tmp_path):
        """Test loading vocabulary with language-tagged dict altLabels."""
        pytest.importorskip("yaml")
        vocab_file = tmp_path / "vocab.yaml"
        vocab_file.write_text("""
concepts:
  food:
    prefLabel: "Food"
    altLabel:
      en: ["groceries", "provisions"]
      nb: ["mat", "matvarer"]
""")
        vocab = vocabulary.load_local_vocabulary(vocab_file)
        assert vocab["food"].altLabels == {"en": ["groceries", "provisions"], "nb": ["mat", "matvarer"]}

    def test_load_backward_compat_flat_altlabels(self, tmp_path):
        """Test that flat list altLabels are wrapped as en."""
        pytest.importorskip("yaml")
        vocab_file = tmp_path / "vocab.yaml"
        vocab_file.write_text("""
concepts:
  tools:
    prefLabel: "Tools"
    altLabel: ["equipment", "implements"]
""")
        vocab = vocabulary.load_local_vocabulary(vocab_file)
        assert vocab["tools"].altLabels == {"en": ["equipment", "implements"]}

    def test_load_dict_altlabel_string_values(self, tmp_path):
        """Test that dict altLabels with string values are wrapped in lists."""
        pytest.importorskip("yaml")
        vocab_file = tmp_path / "vocab.yaml"
        vocab_file.write_text("""
concepts:
  food:
    prefLabel: "Food"
    altLabel:
      en: "groceries"
      nb: "mat"
""")
        vocab = vocabulary.load_local_vocabulary(vocab_file)
        assert vocab["food"].altLabels == {"en": ["groceries"], "nb": ["mat"]}


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
                altLabels={"en": ["veggies", "greens"]},
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

    def test_description_and_wikipedia_preserved(self):
        """build_category_tree must preserve description and wikipediaUrl."""
        vocab = {
            "tools": vocabulary.Concept(id="tools", prefLabel="Tools"),
            "tools/hammer": vocabulary.Concept(
                id="tools/hammer",
                prefLabel="Hammer",
                broader=["tools"],
                source="local",
                uri="http://dbpedia.org/resource/Hammer",
                description="A tool for driving nails.",
                wikipediaUrl="https://en.wikipedia.org/wiki/Hammer",
            ),
        }
        tree = vocabulary.build_category_tree(vocab)
        hammer = tree.concepts["tools/hammer"]
        assert hammer.description == "A tool for driving nails."
        assert hammer.wikipediaUrl == "https://en.wikipedia.org/wiki/Hammer"

    def test_infer_hierarchy_from_paths(self):
        """Test inferring hierarchy from path separators."""
        vocab = {
            "food": vocabulary.Concept(id="food", prefLabel="Food"),
            "food/vegetables": vocabulary.Concept(id="food/vegetables", prefLabel="Vegetables"),
            "food/vegetables/potatoes": vocabulary.Concept(id="food/vegetables/potatoes", prefLabel="Potatoes"),
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
                altLabels={"en": ["veggies"]},
            ),
        }
        tree = vocabulary.build_category_tree(vocab)

        assert tree.label_index.get("vegetables") == "food/vegetables"
        assert tree.label_index.get("veggies") == "food/vegetables"
        assert tree.label_index.get("food/vegetables") == "food/vegetables"

    def test_virtual_root_defines_roots(self):
        """Test that _root.narrower is a whitelist: only listed concepts are roots."""
        vocab = {
            "_root": vocabulary.Concept(id="_root", prefLabel="Root", narrower=["food", "tools"]),
            "food": vocabulary.Concept(id="food", prefLabel="Food"),
            "tools": vocabulary.Concept(id="tools", prefLabel="Tools"),
            "environmental_design": vocabulary.Concept(id="environmental_design", prefLabel="Environmental design"),
        }
        tree = vocabulary.build_category_tree(vocab)

        # Only the curated roots; external orphan not promoted
        assert tree.roots == ["food", "tools"]
        assert "environmental_design" in tree.concepts  # still in vocabulary, just not a root

    def test_virtual_root_excluded_from_tree(self):
        """Test that _root is removed from concepts after root detection."""
        vocab = {
            "_root": vocabulary.Concept(id="_root", prefLabel="Root", narrower=["food"]),
            "food": vocabulary.Concept(id="food", prefLabel="Food"),
        }
        tree = vocabulary.build_category_tree(vocab)

        assert "_root" not in tree.concepts
        assert "_root" not in tree.roots

    def test_virtual_root_excluded_from_label_index(self):
        """Test that _root does not appear in the label index."""
        vocab = {
            "_root": vocabulary.Concept(id="_root", prefLabel="Root", narrower=["food"]),
            "food": vocabulary.Concept(id="food", prefLabel="Food"),
        }
        tree = vocabulary.build_category_tree(vocab)

        assert "_root" not in tree.label_index
        assert "root" not in tree.label_index

    def test_fallback_without_virtual_root(self):
        """Test backward-compatible behavior when _root is absent."""
        vocab = {
            "tools": vocabulary.Concept(id="tools", prefLabel="Tools"),
            "food": vocabulary.Concept(id="food", prefLabel="Food"),
        }
        tree = vocabulary.build_category_tree(vocab)

        # Should be sorted alphabetically by prefLabel
        assert tree.roots == ["food", "tools"]

    def test_virtual_root_skips_missing_children(self):
        """Test that nonexistent narrower entries are ignored."""
        vocab = {
            "_root": vocabulary.Concept(
                id="_root",
                prefLabel="Root",
                narrower=["food", "nonexistent", "tools"],
            ),
            "food": vocabulary.Concept(id="food", prefLabel="Food"),
            "tools": vocabulary.Concept(id="tools", prefLabel="Tools"),
        }
        tree = vocabulary.build_category_tree(vocab)

        assert tree.roots == ["food", "tools"]

    def test_virtual_root_excludes_orphans(self):
        """_root whitelist: orphaned concepts must NOT be added to roots."""
        vocab = {
            "_root": vocabulary.Concept(id="_root", prefLabel="Root", narrower=["food"]),
            "food": vocabulary.Concept(id="food", prefLabel="Food"),
            "verktøy": vocabulary.Concept(id="verktøy", prefLabel="Verktøy"),
            "leker": vocabulary.Concept(id="leker", prefLabel="Leker"),
        }
        tree = vocabulary.build_category_tree(vocab)

        # Only the curated root appears; orphaned external concepts are excluded
        assert tree.roots == ["food"]
        # Concepts are still in the vocabulary (accessible by search), just not roots
        assert "verktøy" in tree.concepts
        assert "leker" in tree.concepts

    def test_virtual_root_whitelist_exact(self):
        """_root.narrower is an exact whitelist — non-listed orphans are excluded."""
        vocab = {
            "_root": vocabulary.Concept(id="_root", prefLabel="Root", narrower=["tools", "food"]),
            "food": vocabulary.Concept(id="food", prefLabel="Food"),
            "tools": vocabulary.Concept(id="tools", prefLabel="Tools"),
            "zebra": vocabulary.Concept(id="zebra", prefLabel="Zebra"),
            "alpha": vocabulary.Concept(id="alpha", prefLabel="Alpha"),
        }
        tree = vocabulary.build_category_tree(vocab)

        # Only curated roots in their declared order; no orphan promotion
        assert tree.roots == ["tools", "food"]

    def test_reachable_children_not_promoted_to_roots(self):
        """Test that concepts reachable via narrower chains are not orphan roots."""
        vocab = {
            "_root": vocabulary.Concept(id="_root", prefLabel="Root", narrower=["food"]),
            "food": vocabulary.Concept(id="food", prefLabel="Food", narrower=["fruit"]),
            "fruit": vocabulary.Concept(id="fruit", prefLabel="Fruit", broader=["food"]),
            "orphan": vocabulary.Concept(id="orphan", prefLabel="Orphan"),
        }
        tree = vocabulary.build_category_tree(vocab)

        # Only the curated root; neither reachable children nor orphans are promoted
        assert tree.roots == ["food"]
        assert "fruit" in tree.concepts

    def test_virtual_root_preserves_narrower_order(self):
        """Test that roots appear in _root.narrower order, not alphabetical."""
        vocab = {
            "_root": vocabulary.Concept(
                id="_root",
                prefLabel="Root",
                narrower=["tools", "food", "electronics"],
            ),
            "food": vocabulary.Concept(id="food", prefLabel="Food"),
            "tools": vocabulary.Concept(id="tools", prefLabel="Tools"),
            "electronics": vocabulary.Concept(id="electronics", prefLabel="Electronics"),
        }
        tree = vocabulary.build_category_tree(vocab)

        # Order matches _root.narrower, NOT alphabetical
        assert tree.roots == ["tools", "food", "electronics"]

    def test_source_uris_preserved(self):
        """build_category_tree must preserve source_uris on concepts."""
        vocab = {
            "food": vocabulary.Concept(id="food", prefLabel="Food"),
            "food/potatoes": vocabulary.Concept(
                id="food/potatoes",
                prefLabel="Potatoes",
                broader=["food"],
                source="dbpedia",
                uri="http://dbpedia.org/resource/Potato",
                source_uris={
                    "off": "off:en:potatoes",
                    "dbpedia": "http://dbpedia.org/resource/Potato",
                    "wikidata": "http://www.wikidata.org/entity/Q16587531",
                },
            ),
        }
        tree = vocabulary.build_category_tree(vocab)
        potatoes = tree.concepts["food/potatoes"]
        assert potatoes.source_uris == {
            "off": "off:en:potatoes",
            "dbpedia": "http://dbpedia.org/resource/Potato",
            "wikidata": "http://www.wikidata.org/entity/Q16587531",
        }

    def test_source_uris_in_json_output(self, tmp_path):
        """source_uris must appear in vocabulary.json via save_vocabulary_json."""
        vocab = {
            "tools": vocabulary.Concept(id="tools", prefLabel="Tools"),
            "tools/hammer": vocabulary.Concept(
                id="tools/hammer",
                prefLabel="Hammer",
                broader=["tools"],
                source="dbpedia",
                source_uris={
                    "dbpedia": "http://dbpedia.org/resource/Hammer",
                    "wikidata": "http://www.wikidata.org/entity/Q169470",
                },
            ),
        }
        output_path = tmp_path / "vocabulary.json"
        vocabulary.save_vocabulary_json(vocab, output_path)

        with open(output_path, encoding="utf-8") as f:
            data = json.load(f)

        hammer = data["concepts"]["tools/hammer"]
        assert hammer["source_uris"] == {
            "dbpedia": "http://dbpedia.org/resource/Hammer",
            "wikidata": "http://www.wikidata.org/entity/Q169470",
        }


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
                altLabels={"nb": ["mat"]},
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
        assert vocab["food"].altLabels == {"nb": ["mat"]}
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


class TestSaveVocabularyJson:
    """Tests for save_vocabulary_json function."""

    def test_save_and_load(self, tmp_path):
        """Test saving vocabulary as JSON."""
        vocab = {
            "food": vocabulary.Concept(id="food", prefLabel="Food"),
            "food/vegetables": vocabulary.Concept(
                id="food/vegetables",
                prefLabel="Vegetables",
                altLabels={"en": ["veggies"]},
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
        assert data["concepts"]["food/vegetables"]["altLabels"] == {"en": ["veggies"]}

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


class TestExpandLanguagesWithAliases:
    """Tests for language code alias expansion."""

    def test_nb_expands_to_no(self):
        assert vocabulary.expand_languages_with_aliases(["en", "nb"]) == ["en", "nb", "no"]

    def test_no_expands_to_nb(self):
        assert vocabulary.expand_languages_with_aliases(["en", "no"]) == ["en", "no", "nb"]

    def test_no_duplicates_when_both_present(self):
        result = vocabulary.expand_languages_with_aliases(["en", "nb", "no"])
        assert result == ["en", "nb", "no"]

    def test_unaliased_language_unchanged(self):
        assert vocabulary.expand_languages_with_aliases(["en", "fr"]) == ["en", "fr"]

    def test_empty_list(self):
        assert vocabulary.expand_languages_with_aliases([]) == []


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
    altLabel:
      en: ["equipment"]
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


class TestPackageSourceAttribution:
    """Tests for distinguishing package vocabulary from user-local vocabulary."""

    def test_load_local_vocabulary_defaults_to_source_local(self, tmp_path):
        """load_local_vocabulary() without default_source uses 'local'."""
        vocab_file = tmp_path / "vocabulary.yaml"
        vocab_file.write_text("""
concepts:
  clothing:
    prefLabel: "Clothing"
""")
        vocab = vocabulary.load_local_vocabulary(vocab_file)
        assert vocab["clothing"].source == "local"

    def test_load_local_vocabulary_with_package_source(self, tmp_path):
        """load_local_vocabulary(default_source='package') sets source='package'."""
        vocab_file = tmp_path / "vocabulary.yaml"
        vocab_file.write_text("""
concepts:
  clothing:
    prefLabel: "Clothing"
  food:
    prefLabel: "Food"
""")
        vocab = vocabulary.load_local_vocabulary(vocab_file, default_source="package")
        assert vocab["clothing"].source == "package"
        assert vocab["food"].source == "package"

    def test_explicit_source_overrides_default(self, tmp_path):
        """Explicit source in YAML overrides default_source param."""
        vocab_file = tmp_path / "vocabulary.yaml"
        vocab_file.write_text("""
concepts:
  tools:
    prefLabel: "Tools"
    source: "custom"
""")
        vocab = vocabulary.load_local_vocabulary(vocab_file, default_source="package")
        assert vocab["tools"].source == "custom"

    def test_local_files_use_local_source(self, tmp_path):
        """load_global_vocabulary() uses source='local' for all non-tingbok vocab files."""
        user_dir = tmp_path / "user"
        user_dir.mkdir()
        user_vocab = user_dir / "vocabulary.yaml"
        user_vocab.write_text("""
concepts:
  my_thing:
    prefLabel: "My Thing"
""")

        with patch.object(vocabulary, "find_vocabulary_files", return_value=[user_vocab]):
            merged = vocabulary.load_global_vocabulary()

        assert merged["my_thing"].source == "local"

    def test_package_source_round_trip(self):
        """Concept with source='package' survives to_dict/from_dict round-trip."""
        concept = vocabulary.Concept(
            id="clothing",
            prefLabel="Clothing",
            source="package",
        )
        data = concept.to_dict()
        assert data["source"] == "package"

        restored = vocabulary.Concept.from_dict(data)
        assert restored.source == "package"


class TestConceptSourceUris:
    """Tests for source_uris field on Concept."""

    def test_source_uris_defaults_to_empty_dict(self):
        """source_uris defaults to empty dict."""
        concept = vocabulary.Concept(id="test", prefLabel="Test")
        assert concept.source_uris == {}

    def test_to_dict_includes_source_uris_when_nonempty(self):
        """to_dict() includes source_uris when non-empty."""
        concept = vocabulary.Concept(
            id="food/potatoes",
            prefLabel="Potatoes",
            source_uris={"off": "off:en:potatoes", "dbpedia": "http://dbpedia.org/resource/Potato"},
        )
        d = concept.to_dict()
        assert "source_uris" in d
        assert d["source_uris"]["off"] == "off:en:potatoes"
        assert d["source_uris"]["dbpedia"] == "http://dbpedia.org/resource/Potato"

    def test_to_dict_omits_source_uris_when_empty(self):
        """to_dict() omits source_uris when empty."""
        concept = vocabulary.Concept(id="test", prefLabel="Test")
        d = concept.to_dict()
        assert "source_uris" not in d

    def test_from_dict_round_trip(self):
        """from_dict() round-trip preserves source_uris."""
        original = vocabulary.Concept(
            id="food/potatoes",
            prefLabel="Potatoes",
            source_uris={
                "off": "off:en:potatoes",
                "agrovoc": "http://aims.fao.org/aos/agrovoc/c_6139",
                "dbpedia": "http://dbpedia.org/resource/Potato",
            },
        )
        d = original.to_dict()
        restored = vocabulary.Concept.from_dict(d)
        assert restored.source_uris == original.source_uris

    def test_from_dict_missing_source_uris(self):
        """from_dict() handles missing source_uris (backward compat)."""
        d = {"id": "test", "prefLabel": "Test"}
        concept = vocabulary.Concept.from_dict(d)
        assert concept.source_uris == {}


class TestUriToSource:
    """Tests for _uri_to_source() helper."""

    def test_off_uri(self):
        assert vocabulary._uri_to_source("off:en:potatoes") == "off"

    def test_agrovoc_uri(self):
        assert vocabulary._uri_to_source("http://aims.fao.org/aos/agrovoc/c_6139") == "agrovoc"

    def test_dbpedia_uri(self):
        assert vocabulary._uri_to_source("http://dbpedia.org/resource/Potato") == "dbpedia"

    def test_wikidata_uri(self):
        assert vocabulary._uri_to_source("http://www.wikidata.org/entity/Q10998") == "wikidata"

    def test_unknown_uri(self):
        assert vocabulary._uri_to_source("https://example.com/foo") is None

    def test_tingbok_uri(self):
        assert vocabulary._uri_to_source("https://tingbok.plann.no/api/vocabulary/food") == "tingbok"

    def test_tingbok_uri_base(self):
        assert vocabulary._uri_to_source("https://tingbok.plann.no/") == "tingbok"

    def test_dbpedia_https_uri(self):
        assert vocabulary._uri_to_source("https://dbpedia.org/resource/Potato") == "dbpedia"

    def test_wikidata_https_uri(self):
        assert vocabulary._uri_to_source("https://www.wikidata.org/entity/Q10998") == "wikidata"


class TestFetchVocabularyFromTingbok:
    """Tests for fetch_vocabulary_from_tingbok()."""

    TINGBOK_URL = "https://tingbok.plann.no"

    VOCAB_RESPONSE = {
        "food": {
            "id": "food",
            "prefLabel": "Food",
            "altLabel": {"en": ["groceries"], "nb": ["mat"]},
            "broader": [],
            "narrower": ["food/vegetables"],
            "uri": "http://dbpedia.org/resource/Food",
            "labels": {"en": "Food", "nb": "Mat"},
            "description": None,
            "wikipediaUrl": None,
        },
        "food/vegetables": {
            "id": "food/vegetables",
            "prefLabel": "Vegetables",
            "altLabel": {},
            "broader": ["food"],
            "narrower": [],
            "uri": None,
            "labels": {},
            "description": None,
            "wikipediaUrl": None,
        },
    }

    def test_returns_concepts_on_success(self):
        """Successful fetch converts JSON to Concept objects with source='package'."""

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.VOCAB_RESPONSE

        with patch("niquests.get", return_value=mock_response):
            result = vocabulary.fetch_vocabulary_from_tingbok(self.TINGBOK_URL)

        assert "food" in result
        assert "food/vegetables" in result
        assert result["food"].prefLabel == "Food"
        assert result["food"].source == "tingbok"
        assert result["food"].altLabels == {"en": ["groceries"], "nb": ["mat"]}
        assert result["food"].labels == {"en": "Food", "nb": "Mat"}
        assert result["food"].uri == "http://dbpedia.org/resource/Food"
        assert result["food/vegetables"].broader == ["food"]

    def test_strips_trailing_slash_from_url(self):
        """URL with trailing slash is handled correctly."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.VOCAB_RESPONSE

        with patch("niquests.get", return_value=mock_response) as mock_get:
            vocabulary.fetch_vocabulary_from_tingbok("https://tingbok.plann.no/")

        called_url = mock_get.call_args[0][0]
        assert called_url == "https://tingbok.plann.no/api/vocabulary"

    def test_raises_on_http_error(self):
        """Non-200 response raises TingbokUnavailableError."""
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.raise_for_status.side_effect = Exception("Service Unavailable")

        with patch("niquests.get", return_value=mock_response):
            with pytest.raises(vocabulary.TingbokUnavailableError):
                vocabulary.fetch_vocabulary_from_tingbok(self.TINGBOK_URL)

    def test_raises_on_connection_error(self):
        """Network error raises TingbokUnavailableError."""
        import niquests

        with patch("niquests.get", side_effect=niquests.ConnectionError("refused")):
            with pytest.raises(vocabulary.TingbokUnavailableError):
                vocabulary.fetch_vocabulary_from_tingbok(self.TINGBOK_URL)

    def test_raises_on_timeout(self):
        """Timeout raises TingbokUnavailableError."""
        import niquests

        with patch("niquests.get", side_effect=niquests.Timeout("timed out")):
            with pytest.raises(vocabulary.TingbokUnavailableError):
                vocabulary.fetch_vocabulary_from_tingbok(self.TINGBOK_URL)

    def test_error_message_contains_url(self):
        """TingbokUnavailableError message includes the endpoint URL."""
        import niquests

        with patch("niquests.get", side_effect=niquests.ConnectionError("refused")):
            with pytest.raises(vocabulary.TingbokUnavailableError, match=self.TINGBOK_URL):
                vocabulary.fetch_vocabulary_from_tingbok(self.TINGBOK_URL)

    def test_source_uris_list_converted_to_dict(self):
        """source_uris list from tingbok JSON is converted to source->URI dict."""
        response_data = {
            "food": {
                "id": "food",
                "prefLabel": "Food",
                "altLabel": {},
                "broader": [],
                "narrower": [],
                "uri": "http://dbpedia.org/resource/Food",
                "labels": {},
                "description": None,
                "wikipediaUrl": None,
                "source_uris": [
                    "https://tingbok.plann.no/api/vocabulary/food",
                    "http://dbpedia.org/resource/Food",
                    "http://aims.fao.org/aos/agrovoc/c_3490",
                ],
                "excluded_sources": [],
            }
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = response_data

        with patch("niquests.get", return_value=mock_response):
            result = vocabulary.fetch_vocabulary_from_tingbok(self.TINGBOK_URL)

        food = result["food"]
        assert isinstance(food.source_uris, dict)
        assert food.source_uris.get("tingbok") == "https://tingbok.plann.no/api/vocabulary/food"
        assert food.source_uris.get("dbpedia") == "http://dbpedia.org/resource/Food"
        assert food.source_uris.get("agrovoc") == "http://aims.fao.org/aos/agrovoc/c_3490"

    def test_excluded_sources_passed_through(self):
        """excluded_sources from tingbok JSON is stored on Concept."""
        response_data = {
            "household/bedding": {
                "id": "household/bedding",
                "prefLabel": "Bedding",
                "altLabel": {},
                "broader": ["household"],
                "narrower": [],
                "uri": "http://dbpedia.org/resource/Bedding",
                "labels": {},
                "description": None,
                "wikipediaUrl": None,
                "source_uris": [
                    "https://tingbok.plann.no/api/vocabulary/household/bedding",
                    "http://dbpedia.org/resource/Bedding",
                ],
                "excluded_sources": ["agrovoc"],
            }
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = response_data

        with patch("niquests.get", return_value=mock_response):
            result = vocabulary.fetch_vocabulary_from_tingbok(self.TINGBOK_URL)

        bedding = result["household/bedding"]
        assert bedding.excluded_sources == ["agrovoc"]


class TestLoadGlobalVocabularyTingbok:
    """Tests for load_global_vocabulary() with tingbok_url and skip_cwd."""

    VOCAB_RESPONSE = {
        "food": {
            "id": "food",
            "prefLabel": "Food",
            "altLabel": {},
            "broader": [],
            "narrower": [],
            "uri": None,
            "labels": {},
            "description": None,
            "wikipediaUrl": None,
        }
    }

    def test_uses_tingbok_when_url_configured(self):
        """load_global_vocabulary(tingbok_url=...) fetches from tingbok."""
        with (
            patch.object(
                vocabulary,
                "fetch_vocabulary_from_tingbok",
                return_value={
                    "food": vocabulary.Concept(id="food", prefLabel="Food", source="tingbok"),
                },
            ) as mock_fetch,
            patch.object(vocabulary, "find_vocabulary_files", return_value=[]),
        ):
            result = vocabulary.load_global_vocabulary(tingbok_url="https://tingbok.plann.no")

        mock_fetch.assert_called_once_with("https://tingbok.plann.no")
        assert "food" in result
        assert result["food"].source == "tingbok"

    def test_raises_when_tingbok_fails(self):
        """TingbokUnavailableError from fetch propagates out of load_global_vocabulary."""
        with (
            patch.object(
                vocabulary,
                "fetch_vocabulary_from_tingbok",
                side_effect=vocabulary.TingbokUnavailableError("tingbok down"),
            ),
            patch.object(vocabulary, "find_vocabulary_files", return_value=[]),
        ):
            with pytest.raises(vocabulary.TingbokUnavailableError):
                vocabulary.load_global_vocabulary(tingbok_url="https://tingbok.plann.no")

    def test_skip_cwd_excludes_cwd_files(self, tmp_path, monkeypatch):
        """skip_cwd=True does not load vocabulary files found in cwd."""
        monkeypatch.chdir(tmp_path)
        cwd_vocab = tmp_path / "vocabulary.yaml"
        cwd_vocab.write_text("concepts:\n  local_thing:\n    prefLabel: 'Local'\n")

        with (
            patch.object(vocabulary, "fetch_vocabulary_from_tingbok", return_value={}),
            patch.object(vocabulary, "find_vocabulary_files", return_value=[cwd_vocab]),
        ):
            result = vocabulary.load_global_vocabulary(skip_cwd=True)

        assert "local_thing" not in result

    def test_without_tingbok_url_loads_from_local_files(self, tmp_path):
        """Without tingbok_url, loads from local files only."""
        vocab_file = tmp_path / "vocabulary.yaml"
        vocab_file.write_text("concepts:\n  food:\n    prefLabel: 'Food'\n")

        with patch.object(vocabulary, "find_vocabulary_files", return_value=[vocab_file]):
            result = vocabulary.load_global_vocabulary()

        assert "food" in result


class TestResolveCategoriesViaTingbok:
    """Tests for resolve_categories_via_tingbok()."""

    TINGBOK_URL = "https://tingbok.plann.no"

    def _mock_response(self, data: dict, status_code: int = 200) -> MagicMock:
        r = MagicMock()
        r.status_code = status_code
        r.json.return_value = data
        r.raise_for_status = MagicMock()
        if status_code >= 400:
            import niquests

            r.raise_for_status.side_effect = niquests.HTTPError()
        return r

    def test_found_concept_creates_hierarchy_concepts(self):
        """A resolved concept should add all path segments to new_concepts."""
        hierarchy_response = {
            "label": "cumin",
            "found": True,
            "paths": ["food/spices/cumin"],
            "source": "agrovoc",
            "uri_map": {"food/spices/cumin": "http://aims.fao.org/aos/agrovoc/c_1"},
        }
        with patch("niquests.get", return_value=self._mock_response(hierarchy_response)):
            new_concepts, mappings = vocabulary.resolve_categories_via_tingbok(["cumin"], self.TINGBOK_URL)

        assert "food" in new_concepts
        assert "food/spices" in new_concepts
        assert "food/spices/cumin" in new_concepts
        assert mappings["cumin"] == ["food/spices/cumin"]

    def test_not_found_returns_empty(self):
        """When the hierarchy endpoint returns found=False, nothing is added."""
        hierarchy_response = {
            "label": "xyzzy",
            "found": False,
            "paths": [],
            "source": "agrovoc",
            "uri_map": {},
        }
        with patch("niquests.get", return_value=self._mock_response(hierarchy_response)):
            new_concepts, mappings = vocabulary.resolve_categories_via_tingbok(["xyzzy"], self.TINGBOK_URL)

        assert new_concepts == {}
        assert mappings == {}

    def test_network_error_is_ignored(self):
        """Network errors are caught and the label is skipped silently."""
        import niquests

        with patch("niquests.get", side_effect=niquests.ConnectionError("refused")):
            new_concepts, mappings = vocabulary.resolve_categories_via_tingbok(["cumin"], self.TINGBOK_URL)

        assert new_concepts == {}
        assert mappings == {}

    def test_empty_labels_returns_empty(self):
        """Passing an empty label list returns empty results."""
        new_concepts, mappings = vocabulary.resolve_categories_via_tingbok([], self.TINGBOK_URL)
        assert new_concepts == {}
        assert mappings == {}

    def test_stops_after_first_source_finds_concept(self):
        """Once a concept is found in one source, other sources are not queried."""
        found_response = {
            "label": "cumin",
            "found": True,
            "paths": ["food/spices/cumin"],
            "source": "agrovoc",
            "uri_map": {},
        }
        call_count = 0

        def fake_get(url: str, **kwargs: object) -> MagicMock:
            nonlocal call_count
            call_count += 1
            return self._mock_response(found_response)

        with patch("niquests.get", side_effect=fake_get):
            vocabulary.resolve_categories_via_tingbok(
                ["cumin"], self.TINGBOK_URL, sources=["agrovoc", "dbpedia", "wikidata"]
            )

        assert call_count == 1, "Should stop after first source finds the concept"


class TestFindVocabularyFiles:
    """Tests for find_vocabulary_files — file discovery and exclusion rules."""

    def test_generated_vocabulary_json_not_picked_up_from_cwd(self, tmp_path) -> None:
        """vocabulary.json in CWD (generated parse output) must not be used as input."""
        import os
        from pathlib import Path

        # Create a vocabulary.json that looks like generated output
        generated = tmp_path / "vocabulary.json"
        generated.write_text(
            '{"concepts": {}, "roots": [], "labelIndex": {}, "categoryMappings": {}}',
            encoding="utf-8",
        )

        orig_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            files = vocabulary.find_vocabulary_files()
        finally:
            os.chdir(orig_cwd)

        local_files = [f for f in files if f.parent == tmp_path]
        assert local_files == [], (
            f"find_vocabulary_files() must not return generated vocabulary.json from CWD; got: {local_files}"
        )

    def test_local_vocabulary_json_is_accepted(self, tmp_path) -> None:
        """local-vocabulary.json in CWD should still be accepted as input."""
        import os
        from pathlib import Path

        local_vocab = tmp_path / "local-vocabulary.json"
        local_vocab.write_text('{"concepts": {}}', encoding="utf-8")

        orig_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            files = vocabulary.find_vocabulary_files()
        finally:
            os.chdir(orig_cwd)

        local_files = [f for f in files if f.parent == tmp_path]
        assert local_vocab in local_files

    def test_vocabulary_yaml_in_cwd_is_accepted(self, tmp_path) -> None:
        """vocabulary.yaml in CWD should still be accepted (hand-crafted local vocab)."""
        import os
        from pathlib import Path

        vocab_yaml = tmp_path / "vocabulary.yaml"
        vocab_yaml.write_text("concepts: {}", encoding="utf-8")

        orig_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            files = vocabulary.find_vocabulary_files()
        finally:
            os.chdir(orig_cwd)

        local_files = [f for f in files if f.parent == tmp_path]
        assert vocab_yaml in local_files
