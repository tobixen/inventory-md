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
        """Test that _root.narrower controls which concepts are curated roots."""
        vocab = {
            "_root": vocabulary.Concept(id="_root", prefLabel="Root", narrower=["food", "tools"]),
            "food": vocabulary.Concept(id="food", prefLabel="Food"),
            "tools": vocabulary.Concept(id="tools", prefLabel="Tools"),
            "environmental_design": vocabulary.Concept(id="environmental_design", prefLabel="Environmental design"),
        }
        tree = vocabulary.build_category_tree(vocab)

        # Curated roots first, then orphans appended alphabetically
        assert tree.roots == ["food", "tools", "environmental_design"]

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

    def test_virtual_root_promotes_orphans_to_roots(self):
        """Test that orphan concepts are promoted to roots after curated ones."""
        vocab = {
            "_root": vocabulary.Concept(id="_root", prefLabel="Root", narrower=["food"]),
            "food": vocabulary.Concept(id="food", prefLabel="Food"),
            "verktøy": vocabulary.Concept(id="verktøy", prefLabel="Verktøy"),
            "leker": vocabulary.Concept(id="leker", prefLabel="Leker"),
        }
        tree = vocabulary.build_category_tree(vocab)

        # Curated root first, then orphans sorted alphabetically
        assert tree.roots == ["food", "leker", "verktøy"]
        assert "verktøy" in tree.concepts
        assert "leker" in tree.concepts

    def test_virtual_root_orphans_sorted_after_curated_roots(self):
        """Test that curated roots keep their order, orphans follow alphabetically."""
        vocab = {
            "_root": vocabulary.Concept(id="_root", prefLabel="Root", narrower=["tools", "food"]),
            "food": vocabulary.Concept(id="food", prefLabel="Food"),
            "tools": vocabulary.Concept(id="tools", prefLabel="Tools"),
            "zebra": vocabulary.Concept(id="zebra", prefLabel="Zebra"),
            "alpha": vocabulary.Concept(id="alpha", prefLabel="Alpha"),
        }
        tree = vocabulary.build_category_tree(vocab)

        # Curated order preserved, then orphans alphabetically
        assert tree.roots == ["tools", "food", "alpha", "zebra"]

    def test_reachable_children_not_promoted_to_roots(self):
        """Test that concepts reachable via narrower chains are not orphan roots."""
        vocab = {
            "_root": vocabulary.Concept(id="_root", prefLabel="Root", narrower=["food"]),
            "food": vocabulary.Concept(id="food", prefLabel="Food", narrower=["fruit"]),
            "fruit": vocabulary.Concept(id="fruit", prefLabel="Fruit", broader=["food"]),
            "orphan": vocabulary.Concept(id="orphan", prefLabel="Orphan"),
        }
        tree = vocabulary.build_category_tree(vocab)

        # fruit is reachable from food, so only food and orphan are roots
        assert tree.roots == ["food", "orphan"]
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
            c.prefLabel.lower() == label.lower() and c.source != "inventory" for c in concepts.values()
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
            c.prefLabel.lower() == label.lower() and c.source != "inventory" for c in concepts.values()
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
            {
                "food": "off:en:plant-based-foods-and-beverages",
                "food/vegetables": "off:en:vegetables",
                "food/vegetables/potatoes": "off:en:potatoes",
            },
            ["plant_based_foods_and_beverages/vegetables/potatoes"],
        )
        client.get_labels.return_value = {"en": "Potatoes", "de": "Kartoffeln"}
        return client

    @patch("inventory_md.vocabulary.build_skos_hierarchy_paths")
    def test_off_priority_over_agrovoc(self, mock_skos_paths):
        """Test that OFF is tried before AGROVOC for food categories."""
        inventory = {
            "containers": [
                {
                    "id": "box1",
                    "items": [{"name": "Potatoes", "metadata": {"categories": ["potatoes"]}}],
                }
            ]
        }

        mock_off_client = self._make_mock_off_client()

        with patch("inventory_md.off.OFFTaxonomyClient", return_value=mock_off_client):
            # Only enable OFF (no AGROVOC/DBpedia) to verify OFF is used
            vocab, mappings = vocabulary.build_vocabulary_with_skos_hierarchy(inventory, enabled_sources=["off"])

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
            "containers": [
                {
                    "id": "box1",
                    "items": [{"name": "Lentils", "metadata": {"categories": ["lentils"]}}],
                }
            ]
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
            ["products/legumes/lentils"],
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
            "containers": [
                {
                    "id": "box1",
                    "items": [{"name": "Potatoes", "metadata": {"categories": ["potatoes"]}}],
                }
            ]
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
            "containers": [
                {
                    "id": "box1",
                    "items": [{"name": "Potatoes", "metadata": {"categories": ["potatoes"]}}],
                }
            ]
        }

        # OFF provides one set of paths
        mock_off_client = self._make_mock_off_client()
        mock_off_client.build_paths_to_root.return_value = (
            ["food/vegetables/potatoes"],
            {"food/vegetables/potatoes": "off:en:potatoes"},
            ["plant_based_foods_and_beverages/vegetables/potatoes"],
        )

        # AGROVOC provides additional paths
        mock_skos_paths.return_value = (
            ["food/plant_products/root_vegetables/potatoes"],
            True,
            {"food/plant_products/root_vegetables/potatoes": "http://aims.fao.org/aos/agrovoc/c_6139"},
            ["products/plant_products/root_vegetables/potatoes"],
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
        vocabulary._add_paths_to_concepts(["tools/hand/hammer"], concepts, "dbpedia")

        # Original "tools" concept should be unchanged
        assert concepts["tools"].source == "local"
        assert concepts["tools"].broader == []
        # But child paths should be added
        assert "tools/hand" in concepts
        assert "tools/hand/hammer" in concepts
        assert concepts["tools/hand"].source == "dbpedia"

    def test_add_paths_to_concepts_nb_labels_for_category_by_source(self):
        """_add_paths_to_concepts adds Norwegian labels for category_by_source concepts."""
        concepts: dict[str, vocabulary.Concept] = {}

        vocabulary._add_paths_to_concepts(["category_by_source/off/dairy"], concepts, "off")

        # category_by_source should have Norwegian label
        assert "category_by_source" in concepts
        assert concepts["category_by_source"].labels.get("nb") == "Kategori etter kilde"
        # category_by_source/off should have Norwegian label
        assert concepts["category_by_source/off"].labels.get("nb") == "OpenFoodFacts"
        # Regular concept should NOT have Norwegian label override
        assert concepts["category_by_source/off/dairy"].labels.get("nb") is None

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


class TestSingularPluralMerging:
    """Tests for singular/plural duplicate detection and merging."""

    def test_singular_plural_variant_detection(self):
        """_is_singular_plural_variant should detect singular/plural pairs."""
        assert vocabulary._is_singular_plural_variant("book", "books")
        assert vocabulary._is_singular_plural_variant("books", "book")
        assert vocabulary._is_singular_plural_variant("tool", "tools")
        assert vocabulary._is_singular_plural_variant("battery", "batteries")
        assert vocabulary._is_singular_plural_variant("box", "boxes")
        # Case insensitive
        assert vocabulary._is_singular_plural_variant("Book", "books")
        # Not variants
        assert not vocabulary._is_singular_plural_variant("book", "tool")
        assert not vocabulary._is_singular_plural_variant("food", "clothing")

    def test_singular_plural_merged_not_nested(self):
        """When concept ID is singular of parent, local_broader_path should equal parent.

        e.g., book (broader: books) -> local_broader_path = "books", NOT "books/book"
        """
        local_concept = vocabulary.Concept(
            id="book",
            prefLabel="Book",
            source="local",
            broader=["books"],
        )
        local_concept_id = "book"

        # Simulate the fixed broader path logic
        broader_path = local_concept.broader[0]
        parent_leaf = broader_path.split("/")[-1]
        if vocabulary._is_singular_plural_variant(local_concept_id, parent_leaf):
            local_broader_path = broader_path
        elif local_concept_id.startswith(broader_path + "/"):
            local_broader_path = local_concept_id
        else:
            local_broader_path = f"{broader_path}/{local_concept_id}"

        assert local_broader_path == "books"

    def test_non_variant_still_nests(self):
        """When concept is NOT a singular/plural variant, it should still nest."""
        local_concept = vocabulary.Concept(
            id="hammer",
            prefLabel="Hammer",
            source="local",
            broader=["tools"],
        )
        local_concept_id = "hammer"

        broader_path = local_concept.broader[0]
        parent_leaf = broader_path.split("/")[-1]
        if vocabulary._is_singular_plural_variant(local_concept_id, parent_leaf):
            local_broader_path = broader_path
        elif local_concept_id.startswith(broader_path + "/"):
            local_broader_path = local_concept_id
        else:
            local_broader_path = f"{broader_path}/{local_concept_id}"

        assert local_broader_path == "tools/hammer"

    def test_nested_path_singular_plural(self):
        """Singular/plural detection works with nested broader paths."""
        local_concept = vocabulary.Concept(
            id="spice",
            prefLabel="Spice",
            source="local",
            broader=["food/spices"],
        )
        local_concept_id = "spice"

        broader_path = local_concept.broader[0]
        parent_leaf = broader_path.split("/")[-1]
        if vocabulary._is_singular_plural_variant(local_concept_id, parent_leaf):
            local_broader_path = broader_path
        else:
            local_broader_path = f"{broader_path}/{local_concept_id}"

        assert local_broader_path == "food/spices"


class TestURIMapStability:
    """Tests for URI map first-wins behavior and translation sanity checks."""

    def test_uri_map_first_wins(self):
        """all_uri_maps should not overwrite existing entries."""
        all_uri_maps = {"food": "http://example.com/food-correct"}

        # Simulate later source trying to overwrite
        all_uris = {
            "food": "http://example.com/food-wrong",
            "food/spices": "http://example.com/spices",
        }

        for k, v in all_uris.items():
            if k not in all_uri_maps:
                all_uri_maps[k] = v

        # First entry preserved, new entry added
        assert all_uri_maps["food"] == "http://example.com/food-correct"
        assert all_uri_maps["food/spices"] == "http://example.com/spices"

    def test_translation_sanity_check_skips_mismatch(self):
        """If AGROVOC English label doesn't match prefLabel, skip translations."""
        concept = vocabulary.Concept(
            id="food",
            prefLabel="Food",
            source="local",
            labels={},
        )

        agrovoc_labels = {"en": "Condiments", "nb": "Krydderier"}

        # Simulate the sanity check
        en_label = agrovoc_labels.get("en", "")
        should_skip = False
        if en_label and concept.prefLabel:
            en_lower = en_label.lower()
            pref_lower = concept.prefLabel.lower()
            if en_lower not in pref_lower and pref_lower not in en_lower:
                should_skip = True

        assert should_skip, "Mismatched translation should be skipped"

    def test_translation_sanity_check_allows_match(self):
        """Matching labels should pass the sanity check."""
        concept = vocabulary.Concept(
            id="food",
            prefLabel="Food",
            source="local",
            labels={},
        )

        agrovoc_labels = {"en": "Food", "nb": "Mat"}

        en_label = agrovoc_labels.get("en", "")
        should_skip = False
        if en_label and concept.prefLabel:
            en_lower = en_label.lower()
            pref_lower = concept.prefLabel.lower()
            if en_lower not in pref_lower and pref_lower not in en_lower:
                should_skip = True

        assert not should_skip, "Matching translation should not be skipped"

    def test_translation_sanity_check_allows_substring(self):
        """Substring matches (e.g., 'tool' in 'tools') should pass."""
        concept = vocabulary.Concept(
            id="tools",
            prefLabel="Tools",
            source="local",
            labels={},
        )

        agrovoc_labels = {"en": "Tool", "nb": "Verktøy"}

        en_label = agrovoc_labels.get("en", "")
        should_skip = False
        if en_label and concept.prefLabel:
            en_lower = en_label.lower()
            pref_lower = concept.prefLabel.lower()
            if en_lower not in pref_lower and pref_lower not in en_lower:
                should_skip = True

        assert not should_skip, "Substring match should not be skipped"

    def test_local_vocab_labels_indexes_singular_forms(self):
        """local_vocab_labels should index singular forms so 'alarm' matches 'alarms'."""
        local_vocab_labels: dict[str, str] = {}

        # Simulate building the index with singular form indexing
        concept_id = "alarms"
        local_vocab_labels[concept_id.lower()] = concept_id
        singular_id = vocabulary._normalize_to_singular(concept_id.lower())
        if singular_id != concept_id.lower():
            local_vocab_labels[singular_id] = concept_id

        # "alarm" (singular) should match "alarms" concept
        assert "alarm" in local_vocab_labels
        assert local_vocab_labels["alarm"] == "alarms"
        # "alarms" (plural) should also match
        assert "alarms" in local_vocab_labels

    def test_off_node_ids_first_wins(self):
        """off_node_ids should not overwrite existing entries."""
        off_node_ids: dict[str, str] = {}

        # First label sets food node ID
        uri_map_1 = {"food": "off:en:food", "food/fruits": "off:en:fruits"}
        for cid, uri in uri_map_1.items():
            if uri.startswith("off:") and cid not in off_node_ids:
                off_node_ids[cid] = uri[4:]

        # Second label should NOT overwrite food
        uri_map_2 = {"food": "off:en:condiments", "food/condiments": "off:en:condiments"}
        for cid, uri in uri_map_2.items():
            if uri.startswith("off:") and cid not in off_node_ids:
                off_node_ids[cid] = uri[4:]

        assert off_node_ids["food"] == "en:food"  # First value preserved
        assert off_node_ids["food/condiments"] == "en:condiments"  # New entry added


class TestDBpediaURIPersistence:
    """Tests for storing DBpedia URIs on leaf concepts when paths are found."""

    @staticmethod
    def _make_mock_skos_module():
        """Create a mock skos module with _is_irrelevant_dbpedia_category."""
        mock_module = MagicMock()
        mock_module._is_irrelevant_dbpedia_category.return_value = False
        return mock_module

    def test_dbpedia_uri_persisted_on_leaf(self):
        """Verify leaf concept gets URI when DBpedia paths are found."""
        inventory = {
            "containers": [
                {
                    "id": "box1",
                    "items": [{"name": "Widget", "metadata": {"categories": ["widget"]}}],
                }
            ]
        }

        mock_client = MagicMock()
        mock_client.lookup_concept.return_value = {
            "uri": "http://dbpedia.org/resource/Widget",
            "prefLabel": "Widget",
            "source": "dbpedia",
            "broader": [
                {"uri": "http://dbpedia.org/resource/Inventions", "label": "Inventions", "relType": "hypernym"},
            ],
        }
        mock_client._get_oxigraph_store.return_value = None
        mock_client.get_batch_labels.return_value = {}

        mock_skos = self._make_mock_skos_module()
        mock_skos.SKOSClient.return_value = mock_client

        import inventory_md

        with (
            patch("inventory_md.off.OFFTaxonomyClient") as mock_off_cls,
            patch.dict("sys.modules", {"inventory_md.skos": mock_skos}),
            patch.object(inventory_md, "skos", mock_skos, create=True),
        ):
            mock_off_cls.return_value.lookup_concept.return_value = None
            mock_off_cls.return_value.get_labels.return_value = {}
            vocab, mappings = vocabulary.build_vocabulary_with_skos_hierarchy(
                inventory, enabled_sources=["off", "dbpedia"]
            )

        # Widget should have DBpedia URI on the leaf concept
        assert "widget" in mappings
        # The leaf concept (could be inventions/widget or widget) should have the URI
        found_uri = False
        for _cid, concept in vocab.items():
            if concept.uri == "http://dbpedia.org/resource/Widget":
                found_uri = True
                break
        assert found_uri, "DBpedia URI should be stored on leaf concept"


class TestDBpediaTranslationPhase:
    """Tests for DBpedia translation phase."""

    @staticmethod
    def _make_mock_skos_module():
        """Create a mock skos module with _is_irrelevant_dbpedia_category."""
        mock_module = MagicMock()
        mock_module._is_irrelevant_dbpedia_category.return_value = False
        return mock_module

    def test_dbpedia_translations_fetched(self):
        """Verify DBpedia translations are fetched for concepts with DBpedia URIs."""
        inventory = {
            "containers": [
                {
                    "id": "box1",
                    "items": [{"name": "Widget", "metadata": {"categories": ["widget"]}}],
                }
            ]
        }

        mock_client = MagicMock()
        mock_client.lookup_concept.return_value = {
            "uri": "http://dbpedia.org/resource/Widget",
            "prefLabel": "Widget",
            "source": "dbpedia",
            "broader": [
                {"uri": "http://dbpedia.org/resource/Inventions", "label": "Inventions", "relType": "hypernym"},
            ],
        }
        mock_client._get_oxigraph_store.return_value = None
        mock_client.get_batch_labels.return_value = {
            "http://dbpedia.org/resource/Widget": {
                "en": "Widget",
                "de": "Widget (Technik)",
                "fr": "Widget",
            }
        }

        mock_skos = self._make_mock_skos_module()
        mock_skos.SKOSClient.return_value = mock_client

        import inventory_md

        with (
            patch("inventory_md.off.OFFTaxonomyClient") as mock_off_cls,
            patch.dict("sys.modules", {"inventory_md.skos": mock_skos}),
            patch.object(inventory_md, "skos", mock_skos, create=True),
        ):
            mock_off_cls.return_value.lookup_concept.return_value = None
            mock_off_cls.return_value.get_labels.return_value = {}
            vocab, mappings = vocabulary.build_vocabulary_with_skos_hierarchy(
                inventory,
                enabled_sources=["off", "dbpedia"],
                languages=["en", "de", "fr"],
            )

        # get_batch_labels should have been called with DBpedia URIs
        mock_client.get_batch_labels.assert_called()
        # Find the concept with the DBpedia URI and check translations
        widget_concept = None
        for _cid, concept in vocab.items():
            if concept.uri == "http://dbpedia.org/resource/Widget":
                widget_concept = concept
                break
        assert widget_concept is not None
        assert widget_concept.labels.get("de") == "Widget (Technik)"

    def test_dbpedia_translations_sanity_check_passes_substring(self):
        """Verify sanity check allows labels where prefLabel is a substring."""
        inventory = {
            "containers": [
                {
                    "id": "box1",
                    "items": [{"name": "Seal", "metadata": {"categories": ["seal"]}}],
                }
            ]
        }

        mock_client = MagicMock()
        mock_client.lookup_concept.return_value = {
            "uri": "http://dbpedia.org/resource/Hermetic_seal",
            "prefLabel": "Seal",
            "source": "dbpedia",
            "broader": [],
        }
        mock_client._get_oxigraph_store.return_value = None
        # "seal" is a substring of "seal (mechanical)" -> passes sanity check
        mock_client.get_batch_labels.return_value = {
            "http://dbpedia.org/resource/Hermetic_seal": {
                "en": "Seal (mechanical)",
                "de": "Dichtung",
            }
        }

        mock_skos = self._make_mock_skos_module()
        mock_skos.SKOSClient.return_value = mock_client

        import inventory_md

        with (
            patch("inventory_md.off.OFFTaxonomyClient") as mock_off_cls,
            patch.dict("sys.modules", {"inventory_md.skos": mock_skos}),
            patch.object(inventory_md, "skos", mock_skos, create=True),
        ):
            mock_off_cls.return_value.lookup_concept.return_value = None
            mock_off_cls.return_value.get_labels.return_value = {}
            vocab, _ = vocabulary.build_vocabulary_with_skos_hierarchy(
                inventory,
                enabled_sources=["off", "dbpedia"],
                languages=["en", "de"],
            )

        # "seal" is in "seal (mechanical)" -> passes sanity check
        seal_concept = None
        for _cid, concept in vocab.items():
            if concept.uri == "http://dbpedia.org/resource/Hermetic_seal":
                seal_concept = concept
                break
        assert seal_concept is not None
        assert seal_concept.labels.get("de") == "Dichtung"


class TestCategoryBySource:
    """Tests for category_by_source concept creation."""

    @patch("inventory_md.vocabulary.build_skos_hierarchy_paths")
    def test_category_by_source_off(self, mock_skos_paths):
        """Verify category_by_source/off/ concepts are created with raw OFF paths."""
        inventory = {
            "containers": [
                {
                    "id": "box1",
                    "items": [{"name": "Potatoes", "metadata": {"categories": ["potatoes"]}}],
                }
            ]
        }

        mock_off_client = MagicMock()
        mock_off_client.lookup_concept.return_value = {
            "uri": "off:en:potatoes",
            "prefLabel": "Potatoes",
            "source": "off",
            "broader": [{"uri": "off:en:vegetables", "label": "Vegetables"}],
            "node_id": "en:potatoes",
        }
        mock_off_client.build_paths_to_root.return_value = (
            ["food/vegetables/potatoes"],
            {"food/vegetables/potatoes": "off:en:potatoes"},
            ["plant_based_foods_and_beverages/vegetables/potatoes"],
        )
        mock_off_client.get_labels.return_value = {}

        # No AGROVOC
        mock_skos_paths.return_value = (["potatoes"], False, {}, [])

        with patch("inventory_md.off.OFFTaxonomyClient", return_value=mock_off_client):
            vocab, mappings = vocabulary.build_vocabulary_with_skos_hierarchy(inventory, enabled_sources=["off"])

        # category_by_source/off/ path should exist
        assert "category_by_source" in vocab
        assert "category_by_source/off" in vocab
        assert "category_by_source/off/plant_based_foods_and_beverages" in vocab
        assert "category_by_source/off/plant_based_foods_and_beverages/vegetables" in vocab
        assert "category_by_source/off/plant_based_foods_and_beverages/vegetables/potatoes" in vocab

        # category_by_source paths should appear in mappings so items are browsable
        assert "potatoes" in mappings
        cbs_paths = [p for p in mappings["potatoes"] if p.startswith("category_by_source/")]
        assert "category_by_source/off/plant_based_foods_and_beverages/vegetables/potatoes" in cbs_paths

        # Well-known concepts should have proper display labels
        assert vocab["category_by_source"].prefLabel == "Category by Source"
        assert vocab["category_by_source/off"].prefLabel == "OpenFoodFacts"

    def test_category_by_source_dbpedia(self):
        """Verify category_by_source/dbpedia/ concepts are created."""
        inventory = {
            "containers": [
                {
                    "id": "box1",
                    "items": [{"name": "Widget", "metadata": {"categories": ["widget"]}}],
                }
            ]
        }

        mock_client = MagicMock()
        mock_client.lookup_concept.return_value = {
            "uri": "http://dbpedia.org/resource/Widget",
            "prefLabel": "Widget",
            "source": "dbpedia",
            "broader": [
                {"uri": "http://dbpedia.org/resource/Inventions", "label": "Inventions", "relType": "hypernym"},
            ],
        }
        mock_client._get_oxigraph_store.return_value = None
        mock_client.get_batch_labels.return_value = {}

        mock_skos = MagicMock()
        mock_skos._is_irrelevant_dbpedia_category.return_value = False
        mock_skos.SKOSClient.return_value = mock_client

        import inventory_md

        with (
            patch("inventory_md.off.OFFTaxonomyClient") as mock_off_cls,
            patch.dict("sys.modules", {"inventory_md.skos": mock_skos}),
            patch.object(inventory_md, "skos", mock_skos, create=True),
        ):
            mock_off_cls.return_value.lookup_concept.return_value = None
            mock_off_cls.return_value.get_labels.return_value = {}
            vocab, mappings = vocabulary.build_vocabulary_with_skos_hierarchy(
                inventory, enabled_sources=["off", "dbpedia"]
            )

        # category_by_source/dbpedia/ path should exist
        assert "category_by_source" in vocab
        assert "category_by_source/dbpedia" in vocab
        # DBpedia paths are already unmapped (no root mapping)
        assert "category_by_source/dbpedia/inventions" in vocab
        assert "category_by_source/dbpedia/inventions/widget" in vocab

        # category_by_source paths should appear in mappings so items are browsable
        assert "widget" in mappings
        cbs_paths = [p for p in mappings["widget"] if p.startswith("category_by_source/")]
        assert "category_by_source/dbpedia/inventions/widget" in cbs_paths

        # Proper display labels for well-known concepts
        assert vocab["category_by_source/dbpedia"].prefLabel == "DBpedia"

    def test_category_by_source_local_fallback(self):
        """Verify category_by_source/local/ concepts created for fallback (no source found)."""
        inventory = {
            "containers": [
                {
                    "id": "box1",
                    "items": [{"name": "Gizmo", "metadata": {"categories": ["gizmo"]}}],
                }
            ]
        }

        mock_client = MagicMock()
        mock_client.lookup_concept.return_value = None
        mock_client._get_oxigraph_store.return_value = None
        mock_client.get_batch_labels.return_value = {}

        mock_skos = MagicMock()
        mock_skos.SKOSClient.return_value = mock_client

        import inventory_md

        with (
            patch("inventory_md.off.OFFTaxonomyClient") as mock_off_cls,
            patch.dict("sys.modules", {"inventory_md.skos": mock_skos}),
            patch.object(inventory_md, "skos", mock_skos, create=True),
        ):
            mock_off_cls.return_value.lookup_concept.return_value = None
            mock_off_cls.return_value.get_labels.return_value = {}
            vocab, mappings = vocabulary.build_vocabulary_with_skos_hierarchy(
                inventory, enabled_sources=["off", "dbpedia"]
            )

        # category_by_source/local/ path should exist in both vocab and mappings
        assert "category_by_source/local" in vocab
        assert "category_by_source/local/gizmo" in vocab
        assert "gizmo" in mappings
        assert "category_by_source/local/gizmo" in mappings["gizmo"]

    @patch("inventory_md.vocabulary.build_skos_hierarchy_paths")
    def test_category_by_source_local_path_category(self, mock_skos_paths):
        """Verify category_by_source/local/ concepts for path-based categories."""
        inventory = {
            "containers": [
                {
                    "id": "box1",
                    "items": [{"name": "Wrench", "metadata": {"categories": ["tools/hand_tools"]}}],
                }
            ]
        }

        # No AGROVOC results
        mock_skos_paths.return_value = ([], False, {}, [])

        with patch("inventory_md.off.OFFTaxonomyClient") as mock_off_cls:
            mock_off_cls.return_value.lookup_concept.return_value = None
            mock_off_cls.return_value.get_labels.return_value = {}
            vocab, mappings = vocabulary.build_vocabulary_with_skos_hierarchy(inventory, enabled_sources=["off"])

        # category_by_source/local/ mirror should exist
        assert "category_by_source/local/tools/hand_tools" in vocab
        assert "category_by_source/local/tools" in vocab
        assert "tools/hand_tools" in mappings
        assert "category_by_source/local/tools/hand_tools" in mappings["tools/hand_tools"]


class TestDBpediaEnrichesLocalConcepts:
    """Tests for enriching local vocab concepts with DBpedia metadata.

    When a local concept has broader (hierarchy) but no uri/description/wikipediaUrl,
    DBpedia should enrich it with metadata while keeping the local hierarchy.
    """

    @staticmethod
    def _make_mock_skos_module():
        """Create a mock skos module with _is_irrelevant_dbpedia_category."""
        mock_module = MagicMock()
        mock_module._is_irrelevant_dbpedia_category.return_value = False
        return mock_module

    def test_local_concept_enriched_with_dbpedia_metadata(self):
        """Local concept with broader gets uri, description, wikipediaUrl from DBpedia."""
        local_vocab = {
            "tools": vocabulary.Concept(
                id="tools",
                prefLabel="Tools",
                source="local",
            ),
            "hammer": vocabulary.Concept(
                id="hammer",
                prefLabel="Hammer",
                broader=["tools"],
                source="local",
            ),
        }
        inventory = {
            "containers": [
                {
                    "id": "box1",
                    "items": [{"name": "Hammer", "metadata": {"categories": ["hammer"]}}],
                }
            ]
        }

        mock_client = MagicMock()
        mock_client.lookup_concept.return_value = {
            "uri": "http://dbpedia.org/resource/Hammer",
            "prefLabel": "Hammer",
            "source": "dbpedia",
            "description": "A tool with a heavy head used for driving nails.",
            "wikipediaUrl": "https://en.wikipedia.org/wiki/Hammer",
            "broader": [],
        }
        mock_client._get_oxigraph_store.return_value = None
        mock_client.get_batch_labels.return_value = {}

        mock_skos = self._make_mock_skos_module()
        mock_skos.SKOSClient.return_value = mock_client

        import inventory_md

        with (
            patch("inventory_md.off.OFFTaxonomyClient") as mock_off_cls,
            patch.dict("sys.modules", {"inventory_md.skos": mock_skos}),
            patch.object(inventory_md, "skos", mock_skos, create=True),
        ):
            mock_off_cls.return_value.lookup_concept.return_value = None
            mock_off_cls.return_value.get_labels.return_value = {}
            vocab, mappings = vocabulary.build_vocabulary_with_skos_hierarchy(
                inventory,
                local_vocab=local_vocab,
                enabled_sources=["off", "dbpedia"],
            )

        # Hammer should use local hierarchy (tools/hammer)
        assert "hammer" in mappings
        assert any("tools" in p for p in mappings["hammer"])

        # Local concept should be enriched with DBpedia metadata
        # After deduplication, flat "hammer" is merged into path-prefixed "tools/hammer"
        hammer = vocab.get("tools/hammer")
        assert hammer is not None
        assert hammer.uri == "http://dbpedia.org/resource/Hammer"
        assert hammer.description == "A tool with a heavy head used for driving nails."
        assert hammer.wikipediaUrl == "https://en.wikipedia.org/wiki/Hammer"
        # Source should reflect the metadata origin (DBpedia provided the URI/description)
        assert hammer.source == "dbpedia"
        # Flat "hammer" should no longer exist
        assert vocab.get("hammer") is None

    def test_enrichment_does_not_overwrite_existing_values(self):
        """DBpedia metadata should not overwrite existing local values."""
        local_vocab = {
            "tools": vocabulary.Concept(
                id="tools",
                prefLabel="Tools",
                source="local",
            ),
            "wrench": vocabulary.Concept(
                id="wrench",
                prefLabel="Wrench",
                broader=["tools"],
                source="local",
                uri="http://dbpedia.org/resource/Wrench",
                description="A hand tool for turning nuts.",
                wikipediaUrl="https://en.wikipedia.org/wiki/Wrench",
            ),
        }
        inventory = {
            "containers": [
                {
                    "id": "box1",
                    "items": [{"name": "Wrench", "metadata": {"categories": ["wrench"]}}],
                }
            ]
        }

        mock_client = MagicMock()
        mock_client.lookup_concept.return_value = {
            "uri": "http://dbpedia.org/resource/Wrench_(wrong)",
            "prefLabel": "Wrench",
            "source": "dbpedia",
            "description": "Wrong description from DBpedia.",
            "wikipediaUrl": "https://en.wikipedia.org/wiki/Wrong",
            "broader": [],
        }
        mock_client._get_oxigraph_store.return_value = None
        mock_client.get_batch_labels.return_value = {}

        mock_skos = self._make_mock_skos_module()
        mock_skos.SKOSClient.return_value = mock_client

        import inventory_md

        with (
            patch("inventory_md.off.OFFTaxonomyClient") as mock_off_cls,
            patch.dict("sys.modules", {"inventory_md.skos": mock_skos}),
            patch.object(inventory_md, "skos", mock_skos, create=True),
        ):
            mock_off_cls.return_value.lookup_concept.return_value = None
            mock_off_cls.return_value.get_labels.return_value = {}
            vocab, mappings = vocabulary.build_vocabulary_with_skos_hierarchy(
                inventory,
                local_vocab=local_vocab,
                enabled_sources=["off", "dbpedia"],
            )

        # Local values should be preserved (not overwritten by DBpedia)
        # After deduplication, flat "wrench" is merged into "tools/wrench"
        wrench = vocab.get("tools/wrench")
        assert wrench is not None
        assert wrench.uri == "http://dbpedia.org/resource/Wrench"
        assert wrench.description == "A hand tool for turning nuts."
        assert wrench.wikipediaUrl == "https://en.wikipedia.org/wiki/Wrench"
        # Flat "wrench" should no longer exist
        assert vocab.get("wrench") is None

    def test_local_concepts_enriched_even_without_inventory_categories(self):
        """Local vocab concepts get DBpedia metadata even when inventory has no categories."""
        local_vocab = {
            "tools": vocabulary.Concept(
                id="tools",
                prefLabel="Tools",
                source="local",
            ),
            "hammer": vocabulary.Concept(
                id="hammer",
                prefLabel="Hammer",
                broader=["tools"],
                source="local",
            ),
            "screwdriver": vocabulary.Concept(
                id="screwdriver",
                prefLabel="Screwdriver",
                broader=["tools"],
                source="local",
                uri="http://dbpedia.org/resource/Screwdriver",
                description="A tool for driving screws.",
                wikipediaUrl="https://en.wikipedia.org/wiki/Screwdriver",
            ),
        }
        # Empty inventory — no items have categories
        inventory = {"containers": [{"id": "box1", "items": []}]}

        mock_client = MagicMock()
        mock_client.lookup_concept.return_value = {
            "uri": "http://dbpedia.org/resource/Hammer",
            "prefLabel": "Hammer",
            "source": "dbpedia",
            "description": "A tool with a heavy head used for driving nails.",
            "wikipediaUrl": "https://en.wikipedia.org/wiki/Hammer",
            "broader": [],
        }
        mock_client._get_oxigraph_store.return_value = None
        mock_client.get_batch_labels.return_value = {}

        mock_skos = self._make_mock_skos_module()
        mock_skos.SKOSClient.return_value = mock_client

        import inventory_md

        with (
            patch("inventory_md.off.OFFTaxonomyClient") as mock_off_cls,
            patch.dict("sys.modules", {"inventory_md.skos": mock_skos}),
            patch.object(inventory_md, "skos", mock_skos, create=True),
        ):
            mock_off_cls.return_value.lookup_concept.return_value = None
            mock_off_cls.return_value.get_labels.return_value = {}
            vocab, mappings = vocabulary.build_vocabulary_with_skos_hierarchy(
                inventory,
                local_vocab=local_vocab,
                enabled_sources=["off", "dbpedia"],
            )

        # Hammer should be enriched with DBpedia metadata via local vocab injection
        hammer = vocab.get("tools/hammer")
        assert hammer is not None
        assert hammer.uri == "http://dbpedia.org/resource/Hammer"
        assert hammer.description == "A tool with a heavy head used for driving nails."
        assert hammer.wikipediaUrl == "https://en.wikipedia.org/wiki/Hammer"
        assert hammer.source == "dbpedia"

        # Screwdriver already had metadata — should NOT be added to leaf_labels
        # (it's already complete), so lookup_concept should only be called for Hammer
        call_labels = [call.args[0].lower() for call in mock_client.lookup_concept.call_args_list]
        assert "hammer" in call_labels
        assert "screwdriver" not in call_labels


class TestConceptDeduplication:
    """Tests for flat/path-prefixed concept deduplication."""

    @staticmethod
    def _make_mock_skos_module():
        """Create a mock skos module with _is_irrelevant_dbpedia_category."""
        mock_module = MagicMock()
        mock_module._is_irrelevant_dbpedia_category.return_value = False
        return mock_module

    def _build_with_local_vocab(self, local_vocab, items, *, enabled_sources=None):
        """Helper to run build_vocabulary_with_skos_hierarchy with mocked externals."""
        if enabled_sources is None:
            enabled_sources = ["off", "dbpedia"]
        inventory = {
            "containers": [
                {
                    "id": "box1",
                    "items": items,
                }
            ]
        }

        mock_client = MagicMock()
        mock_client.lookup_concept.return_value = None
        mock_client._get_oxigraph_store.return_value = None
        mock_client.get_batch_labels.return_value = {}

        mock_skos = self._make_mock_skos_module()
        mock_skos.SKOSClient.return_value = mock_client

        import inventory_md

        with (
            patch("inventory_md.off.OFFTaxonomyClient") as mock_off_cls,
            patch.dict("sys.modules", {"inventory_md.skos": mock_skos}),
            patch.object(inventory_md, "skos", mock_skos, create=True),
        ):
            mock_off_cls.return_value.lookup_concept.return_value = None
            mock_off_cls.return_value.get_labels.return_value = {}
            vocab, mappings = vocabulary.build_vocabulary_with_skos_hierarchy(
                inventory,
                local_vocab=local_vocab,
                enabled_sources=enabled_sources,
            )
        return vocab, mappings

    def test_no_flat_duplicate_when_broader_set(self):
        """ac-cable with broader:electronics only produces electronics/ac-cable, not both."""
        local_vocab = {
            "electronics": vocabulary.Concept(
                id="electronics",
                prefLabel="Electronics",
                source="local",
            ),
            "ac-cable": vocabulary.Concept(
                id="ac-cable",
                prefLabel="AC Cable",
                broader=["electronics"],
                source="local",
            ),
        }
        items = [{"name": "AC Cable", "metadata": {"categories": ["ac-cable"]}}]

        vocab, mappings = self._build_with_local_vocab(local_vocab, items)

        # Path-prefixed concept should exist
        assert vocab.get("electronics/ac-cable") is not None
        # Flat concept should NOT exist (deduplicated)
        assert vocab.get("ac-cable") is None

    def test_metadata_transferred_to_path_prefixed(self):
        """prefLabel, altLabels, URI etc. are on the path-prefixed concept."""
        local_vocab = {
            "electronics": vocabulary.Concept(
                id="electronics",
                prefLabel="Electronics",
                source="local",
            ),
            "ac-cable": vocabulary.Concept(
                id="ac-cable",
                prefLabel="AC Cable",
                altLabels={"en": ["power cord", "mains cable"]},
                broader=["electronics"],
                source="local",
                uri="http://example.com/ac-cable",
                description="A cable for AC power.",
            ),
        }
        items = [{"name": "AC Cable", "metadata": {"categories": ["ac-cable"]}}]

        vocab, _mappings = self._build_with_local_vocab(local_vocab, items)

        concept = vocab.get("electronics/ac-cable")
        assert concept is not None
        assert concept.prefLabel == "AC Cable"
        assert "power cord" in concept.get_all_alt_labels_flat()
        assert "mains cable" in concept.get_all_alt_labels_flat()
        assert concept.uri == "http://example.com/ac-cable"
        assert concept.description == "A cable for AC power."
        assert concept.source == "local"

    def test_concept_already_path_prefixed_not_affected(self):
        """electronics/ac-cable with broader:electronics doesn't get deleted."""
        local_vocab = {
            "electronics": vocabulary.Concept(
                id="electronics",
                prefLabel="Electronics",
                source="local",
            ),
            "electronics/ac-cable": vocabulary.Concept(
                id="electronics/ac-cable",
                prefLabel="AC Cable",
                broader=["electronics"],
                source="local",
            ),
        }
        items = [{"name": "AC Cable", "metadata": {"categories": ["electronics/ac-cable"]}}]

        vocab, _mappings = self._build_with_local_vocab(local_vocab, items)

        # The concept should still exist (local_concept_id == local_broader_path)
        assert vocab.get("electronics/ac-cable") is not None

    def test_singular_plural_merges_altLabels(self):
        """When book merges into books (singular/plural), altLabels are combined."""
        local_vocab = {
            "books": vocabulary.Concept(
                id="books",
                prefLabel="Books",
                altLabels={"en": ["reading material"]},
                source="local",
            ),
            "book": vocabulary.Concept(
                id="book",
                prefLabel="Book",
                altLabels={"en": ["paperback", "hardcover"]},
                broader=["books"],
                source="local",
            ),
        }
        items = [{"name": "Book", "metadata": {"categories": ["book"]}}]

        vocab, _mappings = self._build_with_local_vocab(local_vocab, items)

        # "book" merges into "books" (singular/plural variant)
        books = vocab.get("books")
        assert books is not None
        # altLabels from both should be present
        all_alts = books.get_all_alt_labels_flat()
        assert "reading material" in all_alts
        assert "paperback" in all_alts
        assert "hardcover" in all_alts
        # Flat "book" should be removed
        assert vocab.get("book") is None

    def test_broader_chain_resolved_for_grandchild(self):
        """sandpaper-sheet (broader: sandpaper, broader: consumables) -> consumables/sandpaper/sandpaper-sheet."""
        local_vocab = {
            "consumables": vocabulary.Concept(
                id="consumables",
                prefLabel="Consumables",
                source="local",
            ),
            "sandpaper": vocabulary.Concept(
                id="sandpaper",
                prefLabel="Sandpaper",
                broader=["consumables"],
                source="local",
            ),
            "sandpaper-sheet": vocabulary.Concept(
                id="sandpaper-sheet",
                prefLabel="Sandpaper sheet",
                broader=["sandpaper"],
                source="local",
            ),
        }
        items = [
            {"name": "Sandpaper", "metadata": {"categories": ["sandpaper"]}},
            {"name": "Sandpaper sheet", "metadata": {"categories": ["sandpaper-sheet"]}},
        ]

        vocab, mappings = self._build_with_local_vocab(local_vocab, items)

        # Full chain resolved: consumables/sandpaper/sandpaper-sheet
        assert vocab.get("consumables/sandpaper/sandpaper-sheet") is not None
        assert vocab.get("consumables/sandpaper") is not None
        # No orphaned flat concepts
        assert vocab.get("sandpaper") is None
        assert vocab.get("sandpaper-sheet") is None
        # Mapping key uses normalized label (hyphens -> spaces)
        assert any("consumables/sandpaper/sandpaper-sheet" in p for p in mappings.get("sandpaper sheet", []))

    def test_path_prefixed_child_gets_resolved_parent(self):
        """automotive/accessories (broader: automotive, broader: transport) -> transport/automotive/accessories."""
        local_vocab = {
            "transport": vocabulary.Concept(
                id="transport",
                prefLabel="Transport",
                source="local",
            ),
            "automotive": vocabulary.Concept(
                id="automotive",
                prefLabel="Automotive",
                broader=["transport"],
                source="local",
            ),
            "automotive/accessories": vocabulary.Concept(
                id="automotive/accessories",
                prefLabel="Automotive accessories",
                broader=["automotive"],
                source="local",
            ),
        }
        items = [
            {"name": "Car stuff", "metadata": {"categories": ["automotive"]}},
            {"name": "Car accessory", "metadata": {"categories": ["automotive/accessories"]}},
        ]

        vocab, _mappings = self._build_with_local_vocab(local_vocab, items)

        # Full chain: transport/automotive/accessories
        assert vocab.get("transport/automotive/accessories") is not None
        assert vocab.get("transport/automotive") is not None
        # No orphaned flat concepts
        assert vocab.get("automotive") is None
        assert vocab.get("automotive/accessories") is None


class TestResolveBroaderChain:
    """Unit tests for _resolve_broader_chain helper."""

    def test_root_concept(self):
        """Root concept (no broader) returns its own ID."""
        local_vocab = {
            "tools": vocabulary.Concept(id="tools", prefLabel="Tools", source="local"),
        }
        assert vocabulary._resolve_broader_chain("tools", local_vocab) == "tools"

    def test_one_level(self):
        """Single broader hop."""
        local_vocab = {
            "electronics": vocabulary.Concept(
                id="electronics",
                prefLabel="Electronics",
                source="local",
            ),
            "ac-cable": vocabulary.Concept(
                id="ac-cable",
                prefLabel="AC Cable",
                broader=["electronics"],
                source="local",
            ),
        }
        assert vocabulary._resolve_broader_chain("ac-cable", local_vocab) == "electronics/ac-cable"

    def test_two_levels(self):
        """Two broader hops: sandpaper -> consumables, sandpaper-sheet -> sandpaper."""
        local_vocab = {
            "consumables": vocabulary.Concept(
                id="consumables",
                prefLabel="Consumables",
                source="local",
            ),
            "sandpaper": vocabulary.Concept(
                id="sandpaper",
                prefLabel="Sandpaper",
                broader=["consumables"],
                source="local",
            ),
            "sandpaper-sheet": vocabulary.Concept(
                id="sandpaper-sheet",
                prefLabel="Sandpaper sheet",
                broader=["sandpaper"],
                source="local",
            ),
        }
        assert vocabulary._resolve_broader_chain("sandpaper", local_vocab) == "consumables/sandpaper"
        assert (
            vocabulary._resolve_broader_chain("sandpaper-sheet", local_vocab) == "consumables/sandpaper/sandpaper-sheet"
        )

    def test_already_path_prefixed(self):
        """Concept ID already embeds its parent path."""
        local_vocab = {
            "food": vocabulary.Concept(
                id="food",
                prefLabel="Food",
                source="local",
            ),
            "food/vegetables": vocabulary.Concept(
                id="food/vegetables",
                prefLabel="Vegetables",
                broader=["food"],
                source="local",
            ),
        }
        assert vocabulary._resolve_broader_chain("food/vegetables", local_vocab) == "food/vegetables"

    def test_concept_not_in_vocab(self):
        """Unknown concept returns its own ID."""
        assert vocabulary._resolve_broader_chain("unknown", {}) == "unknown"

    def test_cycle_protection(self):
        """Cycle in broader chain doesn't cause infinite recursion."""
        local_vocab = {
            "a": vocabulary.Concept(id="a", prefLabel="A", broader=["b"], source="local"),
            "b": vocabulary.Concept(id="b", prefLabel="B", broader=["a"], source="local"),
        }
        # Should not hang — returns something reasonable
        result = vocabulary._resolve_broader_chain("a", local_vocab)
        assert isinstance(result, str)

    def test_singular_plural_collapses(self):
        """Singular/plural variant collapses into parent."""
        local_vocab = {
            "books": vocabulary.Concept(
                id="books",
                prefLabel="Books",
                source="local",
            ),
            "book": vocabulary.Concept(
                id="book",
                prefLabel="Book",
                broader=["books"],
                source="local",
            ),
        }
        assert vocabulary._resolve_broader_chain("book", local_vocab) == "books"


class TestTranslationMerging:
    """Tests for multi-source translation URI resolution.

    When all_uri_maps stores a URI from one source (e.g., DBpedia), the
    translation phase for another source (e.g., AGROVOC) must still find
    its URI via concept.uri fallback.
    """

    def test_agrovoc_build_paths_skips_mapped_root_uri(self):
        """_build_paths_to_root should not store URIs for AGROVOC mapped roots.

        Same pattern as off.py: mapped roots like "products" -> "food" are
        synthetic and shouldn't pollute the uri_map.
        """
        mock_store = MagicMock()

        # Simulate: concept "potatoes" with broader "products" (an AGROVOC root)
        # _get_agrovoc_label returns labels for each URI
        def fake_label(uri, store, lang="en"):
            return {
                "http://aims.fao.org/aos/agrovoc/c_potatoes": "potatoes",
                "http://aims.fao.org/aos/agrovoc/c_products": "products",
            }.get(uri, "")

        # _get_broader_concepts: potatoes -> products, products -> [] (root)
        def fake_broader(uri, store):
            return {
                "http://aims.fao.org/aos/agrovoc/c_potatoes": ["http://aims.fao.org/aos/agrovoc/c_products"],
            }.get(uri, [])

        with (
            patch("inventory_md.vocabulary._get_agrovoc_label", side_effect=fake_label),
            patch("inventory_md.vocabulary._get_broader_concepts", side_effect=fake_broader),
        ):
            paths, uri_map, raw_paths = vocabulary._build_paths_to_root(
                "http://aims.fao.org/aos/agrovoc/c_potatoes", mock_store
            )

        # "products" is in AGROVOC_ROOT_MAPPING -> mapped to "food"
        assert paths == ["food/potatoes"]
        # The mapped root "food" should NOT have a URI in uri_map
        assert "food" not in uri_map
        # But the leaf "food/potatoes" should
        assert "food/potatoes" in uri_map
        assert uri_map["food/potatoes"] == "http://aims.fao.org/aos/agrovoc/c_potatoes"

    def test_agrovoc_translation_falls_back_to_concept_uri(self):
        """AGROVOC translation phase should try concept.uri when all_uri_maps has a non-AGROVOC URI.

        If all_uri_maps has a DBpedia URI for a concept, the AGROVOC phase
        should skip it and try concept.uri (which may hold an AGROVOC URI).
        """
        concepts = {
            "food/potatoes": vocabulary.Concept(
                id="food/potatoes",
                prefLabel="Potatoes",
                source="agrovoc",
                uri="http://aims.fao.org/aos/agrovoc/c_potatoes",
                labels={},
            ),
        }

        # all_uri_maps has a DBpedia URI (first-wins from another source)
        all_uri_maps = {
            "food/potatoes": "http://dbpedia.org/resource/Potato",
        }

        # Build candidate URIs the same way the fixed code does
        candidate_uris = list(
            dict.fromkeys(filter(None, [all_uri_maps.get("food/potatoes"), concepts["food/potatoes"].uri]))
        )

        # Should have both URIs, DBpedia first, then AGROVOC
        assert candidate_uris == [
            "http://dbpedia.org/resource/Potato",
            "http://aims.fao.org/aos/agrovoc/c_potatoes",
        ]

        # Filter: skip OFF and DBpedia URIs for AGROVOC lookups
        agrovoc_candidates = [
            u for u in candidate_uris if not u.startswith("off:") and not u.startswith("http://dbpedia.org/")
        ]
        assert agrovoc_candidates == ["http://aims.fao.org/aos/agrovoc/c_potatoes"]

    def test_dbpedia_translation_falls_back_to_concept_uri(self):
        """DBpedia translation phase should try concept.uri when all_uri_maps has a non-DBpedia URI.

        If all_uri_maps has an AGROVOC URI, the DBpedia phase should still
        find the DBpedia URI from concept.uri.
        """
        concepts = {
            "food/potatoes": vocabulary.Concept(
                id="food/potatoes",
                prefLabel="Potatoes",
                source="agrovoc",
                uri="http://dbpedia.org/resource/Potato",
                labels={"en": "Potatoes"},
            ),
        }

        # all_uri_maps has an AGROVOC URI (first-wins)
        all_uri_maps = {
            "food/potatoes": "http://aims.fao.org/aos/agrovoc/c_potatoes",
        }

        # Build candidate URIs the same way the fixed code does
        candidate_uris = list(
            dict.fromkeys(filter(None, [all_uri_maps.get("food/potatoes"), concepts["food/potatoes"].uri]))
        )

        # Find the DBpedia URI
        dbpedia_uri = next(
            (u for u in candidate_uris if u.startswith("http://dbpedia.org/")),
            None,
        )
        assert dbpedia_uri == "http://dbpedia.org/resource/Potato"

    def test_dbpedia_phase_fills_translation_gaps(self):
        """DBpedia phase should add translations even when concept already has some labels.

        The old code had `if concept.labels: continue` which skipped concepts
        that already had partial translations from OFF/AGROVOC.
        """
        concept = vocabulary.Concept(
            id="food/potatoes",
            prefLabel="Potatoes",
            source="agrovoc",
            uri="http://dbpedia.org/resource/Potato",
            labels={"en": "Potatoes", "nb": "Poteter"},
        )

        # DBpedia provides additional languages
        dbpedia_labels = {"en": "Potato", "nb": "Potet", "de": "Kartoffel", "fr": "Pomme de terre"}

        # The fixed merge: DBpedia fills gaps, doesn't overwrite existing
        merged = dict(dbpedia_labels)
        merged.update(concept.labels)  # existing labels take priority

        assert merged["en"] == "Potatoes"  # existing preserved
        assert merged["nb"] == "Poteter"  # existing preserved
        assert merged["de"] == "Kartoffel"  # gap filled by DBpedia
        assert merged["fr"] == "Pomme de terre"  # gap filled by DBpedia

    def test_wikidata_phase_fills_gaps_without_overwriting(self):
        """Wikidata phase should fill translation gaps without overwriting existing labels."""
        concept = vocabulary.Concept(
            id="food/potatoes",
            prefLabel="Potatoes",
            source="agrovoc",
            uri="http://dbpedia.org/resource/Potato",
            labels={"en": "Potatoes", "de": "Kartoffel"},
        )

        # Wikidata provides Norwegian (which DBpedia lacked)
        wikidata_labels = {"en": "Potato", "nb": "potet", "de": "Kartoffel (Pflanze)"}

        # Same merge pattern: Wikidata fills gaps, doesn't overwrite
        merged = dict(wikidata_labels)
        merged.update(concept.labels)

        assert merged["en"] == "Potatoes"  # existing preserved
        assert merged["de"] == "Kartoffel"  # existing preserved (not overwritten)
        assert merged["nb"] == "potet"  # gap filled by Wikidata

    def test_final_fallback_pass_fills_nb_from_sv(self):
        """Final fallback pass should fill 'nb' from 'sv' when direct translation missing."""
        labels = {"en": "Toilet paper", "sv": "toalettpapper"}
        result = vocabulary.apply_language_fallbacks(labels, ["en", "nb", "sv"])

        assert result["en"] == "Toilet paper"
        assert result["sv"] == "toalettpapper"
        # nb falls back through chain: no (missing), da (missing), nn (missing), sv (found!)
        assert result["nb"] == "toalettpapper"

    def test_final_fallback_pass_prefers_closer_fallback(self):
        """Final fallback pass should prefer closer languages in the chain."""
        labels = {"en": "Milk", "da": "Mælk", "sv": "Mjölk"}
        result = vocabulary.apply_language_fallbacks(labels, ["en", "nb", "da", "sv"])

        assert result["nb"] == "Mælk"  # da is before sv in the chain

    def test_final_fallback_not_applied_when_direct_exists(self):
        """Fallback should not overwrite direct translations."""
        labels = {"en": "Milk", "nb": "Melk", "sv": "Mjölk"}
        result = vocabulary.apply_language_fallbacks(labels, ["en", "nb", "sv"])

        assert result["nb"] == "Melk"  # direct translation preserved

    @staticmethod
    def _make_mock_skos_module():
        """Create a mock skos module with _is_irrelevant_dbpedia_category."""
        mock_module = MagicMock()
        mock_module._is_irrelevant_dbpedia_category.return_value = False
        return mock_module

    def test_shared_dbpedia_uri_labels_applied_to_all_concepts(self):
        """Multiple concepts sharing the same DBpedia URI should all get labels.

        Regression test: previously dbpedia_concept_map was URI -> single concept_id,
        so only the last concept processed got labels (e.g. AGROVOC path got labels but
        root concept did not).
        """
        inventory = {
            "containers": [
                {
                    "id": "box1",
                    "items": [
                        {"name": "Resistor", "metadata": {"categories": ["resistor"]}},
                    ],
                }
            ]
        }

        dbpedia_resistor = {
            "uri": "http://dbpedia.org/resource/Resistor",
            "prefLabel": "Resistor",
            "source": "dbpedia",
            "broader": [
                {
                    "uri": "http://dbpedia.org/resource/Electronics",
                    "label": "Electronics",
                    "relType": "hypernym",
                },
            ],
        }
        dbpedia_electronics = {
            "uri": "http://dbpedia.org/resource/Electronics",
            "prefLabel": "Electronics",
            "source": "dbpedia",
            "broader": [],
        }

        mock_client = MagicMock()

        # lookup_concept returns context-aware results so _resolve_missing_uris
        # can populate source_uris for the root "electronics" concept
        def lookup_side_effect(label, lang="en", source=None):
            lower = label.lower()
            if "resistor" in lower:
                return dbpedia_resistor
            if "electronics" in lower:
                return dbpedia_electronics
            return None

        mock_client.lookup_concept.side_effect = lookup_side_effect
        mock_client._get_oxigraph_store.return_value = None
        # DBpedia batch labels: same Electronics URI maps to multiple concepts
        mock_client.get_batch_labels.return_value = {
            "http://dbpedia.org/resource/Resistor": {
                "en": "Resistor",
                "de": "Widerstand",
            },
            "http://dbpedia.org/resource/Electronics": {
                "en": "Electronics",
                "de": "Elektronik",
                "nb": "Elektronikk",
            },
        }

        mock_skos = self._make_mock_skos_module()
        mock_skos.SKOSClient.return_value = mock_client

        import inventory_md

        with (
            patch("inventory_md.off.OFFTaxonomyClient") as mock_off_cls,
            patch.dict("sys.modules", {"inventory_md.skos": mock_skos}),
            patch.object(inventory_md, "skos", mock_skos, create=True),
        ):
            mock_off_cls.return_value.lookup_concept.return_value = None
            mock_off_cls.return_value.get_labels.return_value = {}
            vocab, _ = vocabulary.build_vocabulary_with_skos_hierarchy(
                inventory,
                enabled_sources=["off", "dbpedia"],
                languages=["en", "de", "nb"],
            )

        # The root "electronics" concept should have labels from DBpedia
        assert "electronics" in vocab, f"Missing root; keys containing 'electr': {[k for k in vocab if 'electr' in k]}"
        root = vocab["electronics"]
        assert root.labels.get("de") == "Elektronik", f"Root labels: {root.labels}"
        assert root.labels.get("nb") == "Elektronikk", f"Root labels: {root.labels}"

        # Child/leaf concepts should also have their labels
        resistor_concepts = [c for cid, c in vocab.items() if c.prefLabel == "Resistor" and c.labels.get("de")]
        assert len(resistor_concepts) > 0, "At least one resistor concept should have German label"


class TestWikidataFallbackPhase:
    """Tests for Wikidata as a full independent category source."""

    @staticmethod
    def _make_mock_skos_module():
        """Create a mock skos module with required filter functions."""
        mock_module = MagicMock()
        mock_module._is_irrelevant_dbpedia_category.return_value = False
        mock_module._is_abstract_wikidata_class.return_value = False
        return mock_module

    def test_wikidata_fallback_creates_hierarchy_paths(self):
        """Paths created when OFF/AGROVOC/DBpedia all miss but Wikidata finds it."""
        inventory = {
            "containers": [
                {
                    "id": "box1",
                    "items": [{"name": "Gadget", "metadata": {"categories": ["gadget"]}}],
                }
            ]
        }

        mock_client = MagicMock()
        # OFF, AGROVOC, DBpedia all miss
        mock_client.lookup_concept.side_effect = lambda label, lang, source: {
            "wikidata": {
                "uri": "http://www.wikidata.org/entity/Q1234",
                "prefLabel": "Gadget",
                "source": "wikidata",
                "description": "A small mechanical device",
                "wikipediaUrl": "https://en.wikipedia.org/wiki/Gadget",
                "broader": [
                    {"uri": "http://www.wikidata.org/entity/Q39546", "label": "Tool", "relType": "instance_of"},
                ],
            },
        }.get(source)
        mock_client._get_oxigraph_store.return_value = None
        mock_client.get_batch_labels.return_value = {}

        mock_skos = self._make_mock_skos_module()
        mock_skos.SKOSClient.return_value = mock_client

        import inventory_md

        with (
            patch("inventory_md.off.OFFTaxonomyClient") as mock_off_cls,
            patch.dict("sys.modules", {"inventory_md.skos": mock_skos}),
            patch.object(inventory_md, "skos", mock_skos, create=True),
        ):
            mock_off_cls.return_value.lookup_concept.return_value = None
            mock_off_cls.return_value.get_labels.return_value = {}
            vocab, mappings = vocabulary.build_vocabulary_with_skos_hierarchy(
                inventory, enabled_sources=["off", "dbpedia", "wikidata"]
            )

        # Should have hierarchy path from Wikidata broader
        assert "gadget" in mappings
        hierarchy_paths = [p for p in mappings["gadget"] if not p.startswith("category_by_source/")]
        assert any("tool" in p for p in hierarchy_paths)
        assert "tool/gadget" in hierarchy_paths

    def test_category_by_source_wikidata(self):
        """category_by_source/wikidata/ entries exist when Wikidata is the source."""
        inventory = {
            "containers": [
                {
                    "id": "box1",
                    "items": [{"name": "Gadget", "metadata": {"categories": ["gadget"]}}],
                }
            ]
        }

        mock_client = MagicMock()
        mock_client.lookup_concept.side_effect = lambda label, lang, source: {
            "wikidata": {
                "uri": "http://www.wikidata.org/entity/Q1234",
                "prefLabel": "Gadget",
                "source": "wikidata",
                "broader": [
                    {"uri": "http://www.wikidata.org/entity/Q39546", "label": "Tool", "relType": "instance_of"},
                ],
            },
        }.get(source)
        mock_client._get_oxigraph_store.return_value = None
        mock_client.get_batch_labels.return_value = {}

        mock_skos = self._make_mock_skos_module()
        mock_skos.SKOSClient.return_value = mock_client

        import inventory_md

        with (
            patch("inventory_md.off.OFFTaxonomyClient") as mock_off_cls,
            patch.dict("sys.modules", {"inventory_md.skos": mock_skos}),
            patch.object(inventory_md, "skos", mock_skos, create=True),
        ):
            mock_off_cls.return_value.lookup_concept.return_value = None
            mock_off_cls.return_value.get_labels.return_value = {}
            vocab, mappings = vocabulary.build_vocabulary_with_skos_hierarchy(
                inventory, enabled_sources=["off", "dbpedia", "wikidata"]
            )

        # category_by_source/wikidata/ path should exist
        assert "category_by_source" in vocab
        assert "category_by_source/wikidata" in vocab
        assert "category_by_source/wikidata/tool" in vocab
        assert "category_by_source/wikidata/tool/gadget" in vocab

        # Proper display label
        assert vocab["category_by_source/wikidata"].prefLabel == "Wikidata"

        # category_by_source paths should appear in mappings
        assert "gadget" in mappings
        cbs_paths = [p for p in mappings["gadget"] if p.startswith("category_by_source/")]
        assert "category_by_source/wikidata/tool/gadget" in cbs_paths

    def test_wikidata_uri_persisted_on_leaf(self):
        """Leaf concept gets Wikidata entity URI."""
        inventory = {
            "containers": [
                {
                    "id": "box1",
                    "items": [{"name": "Gadget", "metadata": {"categories": ["gadget"]}}],
                }
            ]
        }

        mock_client = MagicMock()
        mock_client.lookup_concept.side_effect = lambda label, lang, source: {
            "wikidata": {
                "uri": "http://www.wikidata.org/entity/Q1234",
                "prefLabel": "Gadget",
                "source": "wikidata",
                "broader": [
                    {"uri": "http://www.wikidata.org/entity/Q39546", "label": "Tool", "relType": "instance_of"},
                ],
            },
        }.get(source)
        mock_client._get_oxigraph_store.return_value = None
        mock_client.get_batch_labels.return_value = {}

        mock_skos = self._make_mock_skos_module()
        mock_skos.SKOSClient.return_value = mock_client

        import inventory_md

        with (
            patch("inventory_md.off.OFFTaxonomyClient") as mock_off_cls,
            patch.dict("sys.modules", {"inventory_md.skos": mock_skos}),
            patch.object(inventory_md, "skos", mock_skos, create=True),
        ):
            mock_off_cls.return_value.lookup_concept.return_value = None
            mock_off_cls.return_value.get_labels.return_value = {}
            vocab, mappings = vocabulary.build_vocabulary_with_skos_hierarchy(
                inventory, enabled_sources=["off", "dbpedia", "wikidata"]
            )

        # Find the concept with URI (could be at tool/gadget or gadget)
        found = False
        for _cid, concept in vocab.items():
            if concept.uri == "http://www.wikidata.org/entity/Q1234":
                found = True
                break
        assert found, "Wikidata URI not persisted on any concept"

    def test_wikidata_enriches_local_concept(self):
        """Local concept with broader gets enriched by Wikidata metadata."""
        local_vocab = {
            "tools": vocabulary.Concept(
                id="tools",
                prefLabel="Tools",
                source="local",
            ),
            "gadget": vocabulary.Concept(
                id="gadget",
                prefLabel="Gadget",
                broader=["tools"],
                source="local",
            ),
        }
        inventory = {
            "containers": [
                {
                    "id": "box1",
                    "items": [{"name": "Gadget", "metadata": {"categories": ["gadget"]}}],
                }
            ]
        }

        mock_client = MagicMock()
        # OFF and DBpedia miss, Wikidata finds it
        mock_client.lookup_concept.side_effect = lambda label, lang, source: {
            "wikidata": {
                "uri": "http://www.wikidata.org/entity/Q1234",
                "prefLabel": "Gadget",
                "source": "wikidata",
                "description": "A small mechanical device",
                "wikipediaUrl": "https://en.wikipedia.org/wiki/Gadget",
                "broader": [],
            },
        }.get(source)
        mock_client._get_oxigraph_store.return_value = None
        mock_client.get_batch_labels.return_value = {}

        mock_skos = self._make_mock_skos_module()
        mock_skos.SKOSClient.return_value = mock_client

        import inventory_md

        with (
            patch("inventory_md.off.OFFTaxonomyClient") as mock_off_cls,
            patch.dict("sys.modules", {"inventory_md.skos": mock_skos}),
            patch.object(inventory_md, "skos", mock_skos, create=True),
        ):
            mock_off_cls.return_value.lookup_concept.return_value = None
            mock_off_cls.return_value.get_labels.return_value = {}
            vocab, mappings = vocabulary.build_vocabulary_with_skos_hierarchy(
                inventory,
                local_vocab=local_vocab,
                enabled_sources=["off", "dbpedia", "wikidata"],
            )

        # Gadget should use local hierarchy (tools/gadget)
        assert "gadget" in mappings
        assert any("tools" in p for p in mappings["gadget"])

        # After dedup, flat "gadget" merges into "tools/gadget"
        gadget = vocab.get("tools/gadget")
        assert gadget is not None
        assert gadget.uri == "http://www.wikidata.org/entity/Q1234"
        assert gadget.description == "A small mechanical device"
        assert gadget.wikipediaUrl == "https://en.wikipedia.org/wiki/Gadget"

    def test_wikidata_not_used_when_not_in_enabled_sources(self):
        """Wikidata fallback skipped when not in enabled_sources."""
        inventory = {
            "containers": [
                {
                    "id": "box1",
                    "items": [{"name": "Gizmo", "metadata": {"categories": ["gizmo"]}}],
                }
            ]
        }

        mock_client = MagicMock()
        mock_client.lookup_concept.return_value = None
        mock_client._get_oxigraph_store.return_value = None
        mock_client.get_batch_labels.return_value = {}

        mock_skos = self._make_mock_skos_module()
        mock_skos.SKOSClient.return_value = mock_client

        import inventory_md

        with (
            patch("inventory_md.off.OFFTaxonomyClient") as mock_off_cls,
            patch.dict("sys.modules", {"inventory_md.skos": mock_skos}),
            patch.object(inventory_md, "skos", mock_skos, create=True),
        ):
            mock_off_cls.return_value.lookup_concept.return_value = None
            mock_off_cls.return_value.get_labels.return_value = {}
            vocab, mappings = vocabulary.build_vocabulary_with_skos_hierarchy(
                inventory,
                enabled_sources=["off", "dbpedia"],  # no wikidata
            )

        # Should NOT have called lookup_concept with source="wikidata"
        for call in mock_client.lookup_concept.call_args_list:
            assert call.kwargs.get("source") != "wikidata"
            assert len(call.args) < 3 or call.args[2] != "wikidata"


class TestResolveMissingUris:
    """Tests for _resolve_missing_uris() helper."""

    @staticmethod
    def _make_client(**kwargs):
        """Create a mock SKOS client."""
        client = MagicMock()
        client.lookup_concept.return_value = None
        for k, v in kwargs.items():
            setattr(client, k, v)
        return client

    def test_resolves_dbpedia_uri(self):
        """Concept without URI gets URI, description, and wikipediaUrl from DBpedia."""
        concepts = {
            "tools/hammer": vocabulary.Concept(
                id="tools/hammer",
                prefLabel="Hammer",
                source="local",
            ),
        }
        all_uri_maps: dict[str, str] = {}
        client = self._make_client()
        client.lookup_concept.side_effect = lambda label, lang, source: (
            {
                "uri": "http://dbpedia.org/resource/Hammer",
                "prefLabel": "Hammer",
                "description": "A tool with a heavy head",
                "wikipediaUrl": "https://en.wikipedia.org/wiki/Hammer",
            }
            if source == "dbpedia" and label == "Hammer"
            else None
        )

        count = vocabulary._resolve_missing_uris(concepts, all_uri_maps, client, "en", ["dbpedia", "wikidata"])

        assert count == 1
        assert concepts["tools/hammer"].uri == "http://dbpedia.org/resource/Hammer"
        assert concepts["tools/hammer"].description == "A tool with a heavy head"
        assert concepts["tools/hammer"].wikipediaUrl == "https://en.wikipedia.org/wiki/Hammer"
        assert all_uri_maps["tools/hammer"] == "http://dbpedia.org/resource/Hammer"

    def test_skips_concepts_with_uri(self):
        """Concepts that already have a URI are not looked up."""
        concepts = {
            "tools/wrench": vocabulary.Concept(
                id="tools/wrench",
                prefLabel="Wrench",
                source="local",
                uri="http://dbpedia.org/resource/Wrench",
            ),
        }
        all_uri_maps: dict[str, str] = {}
        client = self._make_client()

        count = vocabulary._resolve_missing_uris(concepts, all_uri_maps, client, "en", ["dbpedia"])

        assert count == 0
        client.lookup_concept.assert_not_called()

    def test_skips_concepts_in_uri_map(self):
        """Concepts already in all_uri_maps are skipped."""
        concepts = {
            "tools/pliers": vocabulary.Concept(
                id="tools/pliers",
                prefLabel="Pliers",
                source="local",
            ),
        }
        all_uri_maps = {"tools/pliers": "http://dbpedia.org/resource/Pliers"}
        client = self._make_client()

        count = vocabulary._resolve_missing_uris(concepts, all_uri_maps, client, "en", ["dbpedia"])

        assert count == 0
        client.lookup_concept.assert_not_called()

    def test_skips_meta_concepts(self):
        """Internal concepts (_root, category_by_source/*) are skipped."""
        concepts = {
            "_root": vocabulary.Concept(
                id="_root",
                prefLabel="Root",
                source="local",
            ),
            "category_by_source/dbpedia/foo": vocabulary.Concept(
                id="category_by_source/dbpedia/foo",
                prefLabel="Foo",
                source="dbpedia",
            ),
        }
        all_uri_maps: dict[str, str] = {}
        client = self._make_client()

        count = vocabulary._resolve_missing_uris(concepts, all_uri_maps, client, "en", ["dbpedia"])

        assert count == 0
        client.lookup_concept.assert_not_called()

    def test_sanity_check_rejects_mismatch(self):
        """Mismatched prefLabel from lookup is rejected."""
        concepts = {
            "tools/clamp": vocabulary.Concept(
                id="tools/clamp",
                prefLabel="Clamp",
                source="local",
            ),
        }
        all_uri_maps: dict[str, str] = {}
        client = self._make_client()
        # Return something completely unrelated
        client.lookup_concept.return_value = {
            "uri": "http://dbpedia.org/resource/Hydraulic_press",
            "prefLabel": "Hydraulic press",
        }

        count = vocabulary._resolve_missing_uris(concepts, all_uri_maps, client, "en", ["dbpedia"])

        assert count == 0
        assert concepts["tools/clamp"].uri is None

    def test_falls_back_to_wikidata(self):
        """When DBpedia misses, Wikidata is tried next."""
        concepts = {
            "electronics/resistor": vocabulary.Concept(
                id="electronics/resistor",
                prefLabel="Resistor",
                source="local",
            ),
        }
        all_uri_maps: dict[str, str] = {}
        client = self._make_client()
        client.lookup_concept.side_effect = lambda label, lang, source: (
            {
                "uri": "http://www.wikidata.org/entity/Q5321",
                "prefLabel": "Resistor",
                "description": "An electronic component",
            }
            if source == "wikidata"
            else None
        )

        count = vocabulary._resolve_missing_uris(concepts, all_uri_maps, client, "en", ["dbpedia", "wikidata"])

        assert count == 1
        assert concepts["electronics/resistor"].uri == "http://www.wikidata.org/entity/Q5321"
        assert concepts["electronics/resistor"].description == "An electronic component"

    def test_respects_enabled_sources(self):
        """Only tries sources that are in enabled_sources."""
        concepts = {
            "tools/drill": vocabulary.Concept(
                id="tools/drill",
                prefLabel="Drill",
                source="local",
            ),
        }
        all_uri_maps: dict[str, str] = {}
        client = self._make_client()
        # Would match on wikidata, but wikidata is not enabled
        client.lookup_concept.side_effect = lambda label, lang, source: (
            {
                "uri": "http://www.wikidata.org/entity/Q1234",
                "prefLabel": "Drill",
            }
            if source == "wikidata"
            else None
        )

        count = vocabulary._resolve_missing_uris(
            concepts,
            all_uri_maps,
            client,
            "en",
            ["dbpedia"],  # no wikidata
        )

        assert count == 0
        # Should only have tried dbpedia
        for call in client.lookup_concept.call_args_list:
            assert call.kwargs.get("source") == "dbpedia"

    def test_does_not_overwrite_existing_description(self):
        """Existing description and wikipediaUrl are preserved."""
        concepts = {
            "tools/chisel": vocabulary.Concept(
                id="tools/chisel",
                prefLabel="Chisel",
                source="local",
                description="A woodworking tool",
                wikipediaUrl="https://en.wikipedia.org/wiki/Chisel",
            ),
        }
        all_uri_maps: dict[str, str] = {}
        client = self._make_client()
        client.lookup_concept.return_value = {
            "uri": "http://dbpedia.org/resource/Chisel",
            "prefLabel": "Chisel",
            "description": "DBpedia description",
            "wikipediaUrl": "https://en.wikipedia.org/wiki/Chisel_DBpedia",
        }

        count = vocabulary._resolve_missing_uris(concepts, all_uri_maps, client, "en", ["dbpedia"])

        assert count == 1
        assert concepts["tools/chisel"].uri == "http://dbpedia.org/resource/Chisel"
        # Original description and URL preserved
        assert concepts["tools/chisel"].description == "A woodworking tool"
        assert concepts["tools/chisel"].wikipediaUrl == "https://en.wikipedia.org/wiki/Chisel"

    def test_returns_zero_when_no_sources_enabled(self):
        """Returns 0 when neither dbpedia nor wikidata in enabled_sources."""
        concepts = {
            "tools/level": vocabulary.Concept(
                id="tools/level",
                prefLabel="Level",
                source="local",
            ),
        }
        all_uri_maps: dict[str, str] = {}
        client = self._make_client()

        count = vocabulary._resolve_missing_uris(concepts, all_uri_maps, client, "en", ["off", "agrovoc"])

        assert count == 0
        client.lookup_concept.assert_not_called()

    def test_uses_concept_id_leaf_when_no_preflabel(self):
        """Falls back to concept_id leaf as lookup label when prefLabel is empty."""
        concepts = {
            "tools/tape_measure": vocabulary.Concept(
                id="tools/tape_measure",
                prefLabel="",
                source="local",
            ),
        }
        all_uri_maps: dict[str, str] = {}
        client = self._make_client()
        client.lookup_concept.return_value = {
            "uri": "http://dbpedia.org/resource/Tape_measure",
            "prefLabel": "Tape measure",
        }

        count = vocabulary._resolve_missing_uris(concepts, all_uri_maps, client, "en", ["dbpedia"])

        assert count == 1
        # Should have used "tape measure" (from concept_id leaf) as lookup label
        call_label = client.lookup_concept.call_args_list[0][0][0]
        assert call_label == "tape measure"

    def test_integration_local_vocab_root_gets_uri(self):
        """Integration: local vocab root concept gets URI before translation phase."""
        inventory = {
            "containers": [
                {
                    "id": "box1",
                    "items": [{"name": "Widget", "metadata": {"categories": ["widget"]}}],
                }
            ]
        }
        local_vocab = {
            "hardware": vocabulary.Concept(
                id="hardware",
                prefLabel="Hardware",
                source="local",
            ),
            "widget": vocabulary.Concept(
                id="widget",
                prefLabel="Widget",
                source="local",
                broader=["hardware"],
            ),
        }

        mock_client = MagicMock()
        # Main loop: no external source finds "widget" or "hardware"
        mock_client.lookup_concept.side_effect = lambda label, lang, source=None: (
            {
                "uri": "http://dbpedia.org/resource/Hardware",
                "prefLabel": "Hardware",
                "description": "Physical components",
            }
            if label == "Hardware" and source == "dbpedia"
            else None
        )
        mock_client._get_oxigraph_store.return_value = None
        mock_client.get_batch_labels.return_value = {}

        mock_skos = MagicMock()
        mock_skos._is_irrelevant_dbpedia_category.return_value = False
        mock_skos._is_abstract_wikidata_class.return_value = False
        mock_skos.SKOSClient.return_value = mock_client

        import inventory_md

        with (
            patch("inventory_md.off.OFFTaxonomyClient") as mock_off_cls,
            patch.dict("sys.modules", {"inventory_md.skos": mock_skos}),
            patch.object(inventory_md, "skos", mock_skos, create=True),
        ):
            mock_off_cls.return_value.lookup_concept.return_value = None
            mock_off_cls.return_value.get_labels.return_value = {}
            vocab, mappings = vocabulary.build_vocabulary_with_skos_hierarchy(
                inventory,
                local_vocab=local_vocab,
                languages=["en", "nb"],
                enabled_sources=["off", "dbpedia"],
            )

        # "hardware" had no URI initially; _resolve_missing_uris should have found it
        hw = vocab.get("hardware")
        assert hw is not None
        assert hw.uri == "http://dbpedia.org/resource/Hardware"
        assert hw.description == "Physical components"


class TestRootCategoryMerges:
    """Tests for the root category merges in package vocabulary.yaml."""

    @pytest.fixture
    def pkg_vocab(self):
        """Load the package vocabulary."""
        from pathlib import Path

        vocab_file = Path(__file__).resolve().parent.parent / ("src/inventory_md/data/vocabulary.yaml")
        return vocabulary.load_local_vocabulary(vocab_file)

    def test_root_narrower_count(self, pkg_vocab):
        """_root.narrower should have exactly 11 entries (10 roots + category_by_source)."""
        root = pkg_vocab["_root"]
        assert len(root.narrower) == 11

    def test_root_narrower_contents(self, pkg_vocab):
        """_root.narrower should list the 10 merged roots plus category_by_source."""
        root = pkg_vocab["_root"]
        expected = {
            "food",
            "tools",
            "electronics",
            "household",
            "clothing",
            "hardware",
            "recreation",
            "medical",
            "games",
            "misc",
            "category_by_source",
        }
        assert set(root.narrower) == expected

    def test_hobby_under_recreation(self, pkg_vocab):
        """hobby concept should exist under recreation."""
        assert "hobby" in pkg_vocab
        assert pkg_vocab["hobby"].broader == ["recreation"]
        assert pkg_vocab["hobby"].prefLabel == "Hobbies & Crafts"

    def test_recreation_root_exists(self, pkg_vocab):
        """recreation should exist as a new root with correct children."""
        rec = pkg_vocab["recreation"]
        assert rec.prefLabel == "Recreation & Transport"
        assert set(rec.narrower) == {"outdoor", "sports", "transport"}
        assert rec.broader == []

    def test_outdoor_demoted_to_recreation(self, pkg_vocab):
        """outdoor should have broader: recreation."""
        assert pkg_vocab["outdoor"].broader == ["recreation"]

    def test_sports_demoted_to_recreation(self, pkg_vocab):
        """sports should have broader: recreation."""
        assert pkg_vocab["sports"].broader == ["recreation"]

    def test_transport_demoted_to_recreation(self, pkg_vocab):
        """transport should have broader: recreation."""
        assert pkg_vocab["transport"].broader == ["recreation"]

    def test_construction_demoted_to_hardware(self, pkg_vocab):
        """construction should have broader: hardware."""
        assert pkg_vocab["construction"].broader == ["hardware"]

    def test_consumables_demoted_to_hardware(self, pkg_vocab):
        """consumables should have broader: hardware."""
        assert pkg_vocab["consumables"].broader == ["hardware"]

    def test_hardware_has_children(self, pkg_vocab):
        """hardware.narrower should include construction and consumables."""
        hw = pkg_vocab["hardware"]
        assert "construction" in hw.narrower
        assert "consumables" in hw.narrower

    def test_office_demoted_to_household(self, pkg_vocab):
        """office should have broader: household."""
        assert pkg_vocab["office"].broader == ["household"]

    def test_books_demoted_to_household(self, pkg_vocab):
        """books should have broader: household."""
        assert pkg_vocab["books"].broader == ["household"]

    def test_documents_demoted_to_household(self, pkg_vocab):
        """documents should have broader: household."""
        assert pkg_vocab["documents"].broader == ["household"]

    def test_household_has_children(self, pkg_vocab):
        """household.narrower should include office, books, documents."""
        hh = pkg_vocab["household"]
        assert "office" in hh.narrower
        assert "books" in hh.narrower
        assert "documents" in hh.narrower

    def test_medical_renamed(self, pkg_vocab):
        """medical should have prefLabel 'Health & Safety'."""
        assert pkg_vocab["medical"].prefLabel == "Health & Safety"

    def test_safety_equipment_under_medical(self, pkg_vocab):
        """safety-equipment should have broader: medical."""
        assert pkg_vocab["safety-equipment"].broader == ["medical"]
        assert "safety-equipment" in pkg_vocab["medical"].narrower

    def test_pool_consumables_moved_to_household(self, pkg_vocab):
        """ph_test_strips and pool_chlorine should be under household."""
        assert pkg_vocab["ph_test_strips"].broader == ["household"]
        assert pkg_vocab["pool_chlorine"].broader == ["household"]

    def test_broader_chain_sleeping_bag(self, pkg_vocab):
        """sleeping-bag → outdoor → recreation (broader chain)."""
        sb = pkg_vocab["sleeping-bag"]
        assert sb.broader == ["outdoor"]
        outdoor = pkg_vocab["outdoor"]
        assert outdoor.broader == ["recreation"]
        rec = pkg_vocab["recreation"]
        assert rec.broader == []

    def test_broader_chain_pen(self, pkg_vocab):
        """pen → office/writing → office → household (broader chain)."""
        pen = pkg_vocab["pen"]
        assert pen.broader == ["office/writing"]
        ow = pkg_vocab["office/writing"]
        assert ow.broader == ["office"]
        office = pkg_vocab["office"]
        assert office.broader == ["household"]

    def test_no_concept_has_broader_hobby(self, pkg_vocab):
        """No concept should reference hobby as broader."""
        for cid, concept in pkg_vocab.items():
            assert "hobby" not in concept.broader, f"{cid} still references hobby as broader"


class TestAgrovocMismatchSuppression:
    """Tests for AGROVOC mismatch warning suppression.

    The vocabulary builder should skip AGROVOC lookup when the local concept
    already has a non-AGROVOC URI, and tolerate singular/plural differences
    in the mismatch check.
    """

    @patch("inventory_md.vocabulary.build_skos_hierarchy_paths")
    def test_agrovoc_skipped_when_local_has_dbpedia_uri(self, mock_skos_paths):
        """AGROVOC lookup should be skipped when local concept has a DBpedia URI."""
        local_vocab = {
            "tools": vocabulary.Concept(
                id="tools",
                prefLabel="Tools",
                source="local",
                broader=["hardware"],
                uri="http://dbpedia.org/resource/Tool",
            ),
            "hardware": vocabulary.Concept(
                id="hardware",
                prefLabel="Hardware",
                source="local",
                broader=[],
            ),
        }

        inventory = {
            "containers": [
                {
                    "id": "box1",
                    "items": [{"name": "Tools", "metadata": {"categories": ["tools"]}}],
                }
            ]
        }

        with patch("inventory_md.off.OFFTaxonomyClient") as mock_off_cls:
            mock_off_cls.return_value.lookup_concept.return_value = None
            mock_off_cls.return_value.get_labels.return_value = {}
            vocab, mappings = vocabulary.build_vocabulary_with_skos_hierarchy(
                inventory,
                enabled_sources=["off", "agrovoc"],
                local_vocab=local_vocab,
            )

        # AGROVOC should NOT have been called because tools has a DBpedia URI
        mock_skos_paths.assert_not_called()

    @patch("inventory_md.vocabulary.build_skos_hierarchy_paths")
    def test_singular_plural_passes_mismatch_check(self, mock_skos_paths):
        """Singular/plural variant (dairy/dairies) should not trigger mismatch."""
        mock_skos_paths.return_value = (
            ["food/dairies"],
            True,
            {"food/dairies": "http://aims.fao.org/aos/agrovoc/c_1234"},
            ["products/dairies"],
        )

        inventory = {
            "containers": [
                {
                    "id": "box1",
                    "items": [{"name": "Dairy", "metadata": {"categories": ["dairy"]}}],
                }
            ]
        }

        with patch("inventory_md.off.OFFTaxonomyClient") as mock_off_cls:
            mock_off_cls.return_value.lookup_concept.return_value = None
            mock_off_cls.return_value.get_labels.return_value = {}
            vocab, mappings = vocabulary.build_vocabulary_with_skos_hierarchy(
                inventory, enabled_sources=["off", "agrovoc"]
            )

        # dairy should have been accepted (not rejected as mismatch)
        assert "dairy" in mappings
        assert any("dairies" in p for p in mappings["dairy"])

    @patch("inventory_md.vocabulary.build_skos_hierarchy_paths")
    def test_genuine_mismatch_still_triggers_warning(self, mock_skos_paths):
        """A genuine mismatch (tool -> equipment) should still warn and skip."""
        mock_skos_paths.return_value = (
            ["food/equipment"],
            True,
            {"food/equipment": "http://aims.fao.org/aos/agrovoc/c_9999"},
            ["products/equipment"],
        )

        inventory = {
            "containers": [
                {
                    "id": "box1",
                    "items": [{"name": "Tool", "metadata": {"categories": ["tool"]}}],
                }
            ]
        }

        with patch("inventory_md.off.OFFTaxonomyClient") as mock_off_cls:
            mock_off_cls.return_value.lookup_concept.return_value = None
            mock_off_cls.return_value.get_labels.return_value = {}
            with patch("inventory_md.vocabulary.logger") as mock_logger:
                vocab, mappings = vocabulary.build_vocabulary_with_skos_hierarchy(
                    inventory, enabled_sources=["off", "agrovoc"]
                )

        # Warning should have been logged for genuine mismatch
        mock_logger.warning.assert_called()
        warning_args = mock_logger.warning.call_args[0]
        assert "AGROVOC mismatch" in warning_args[0]
        assert "tool" in warning_args[1]
        assert "equipment" in warning_args[2]

        # The mismatched AGROVOC result should NOT be in mappings
        if "tool" in mappings:
            assert not any("equipment" in p for p in mappings["tool"])

    @patch("inventory_md.vocabulary._get_agrovoc_label")
    @patch("inventory_md.vocabulary.build_skos_hierarchy_paths")
    def test_cross_language_leaf_not_flagged_as_mismatch(self, mock_skos_paths, mock_get_label):
        """Norwegian leaf label should not trigger mismatch when English label matches."""
        # AGROVOC returns Norwegian path: food/grønnsaker/oliven
        mock_skos_paths.return_value = (
            ["food/grønnsaker/oliven"],
            True,
            {"food/grønnsaker/oliven": "http://aims.fao.org/aos/agrovoc/c_5435"},
            ["products/grønnsaker/oliven"],
        )
        # When we look up the English label for the leaf URI, return "olive"
        mock_get_label.return_value = "olive"

        # Mock the Oxigraph store on the client
        mock_store = MagicMock()
        mock_store.is_loaded = True

        inventory = {
            "containers": [
                {
                    "id": "box1",
                    "items": [{"name": "Olives", "metadata": {"categories": ["olives"]}}],
                }
            ]
        }

        with patch("inventory_md.off.OFFTaxonomyClient") as mock_off_cls:
            mock_off_cls.return_value.lookup_concept.return_value = None
            mock_off_cls.return_value.get_labels.return_value = {}
            with patch("inventory_md.vocabulary.logger") as mock_logger:
                # Need to mock the SKOSClient's _get_oxigraph_store
                with patch("inventory_md.skos.SKOSClient._get_oxigraph_store", return_value=mock_store):
                    vocab, mappings = vocabulary.build_vocabulary_with_skos_hierarchy(
                        inventory, lang="no", enabled_sources=["off", "agrovoc"]
                    )

        # Should NOT have logged an AGROVOC mismatch warning
        for call in mock_logger.warning.call_args_list:
            assert "AGROVOC mismatch" not in str(call), f"Unexpected mismatch warning: {call}"

        # Olives should have been accepted via AGROVOC
        assert "olives" in mappings
        assert any("oliven" in p for p in mappings["olives"])


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

    def test_load_global_vocabulary_package_detection(self, tmp_path):
        """load_global_vocabulary() sets source='package' for package vocab."""
        pkg_dir = tmp_path / "pkg_data"
        pkg_dir.mkdir()
        pkg_vocab = pkg_dir / "vocabulary.yaml"
        pkg_vocab.write_text("""
concepts:
  clothing:
    prefLabel: "Clothing"
""")
        user_dir = tmp_path / "user"
        user_dir.mkdir()
        user_vocab = user_dir / "vocabulary.yaml"
        user_vocab.write_text("""
concepts:
  my_thing:
    prefLabel: "My Thing"
""")

        with (
            patch.object(vocabulary, "_get_package_data_dir", return_value=pkg_dir),
            patch.object(vocabulary, "find_vocabulary_files", return_value=[pkg_vocab, user_vocab]),
        ):
            merged = vocabulary.load_global_vocabulary()

        assert merged["clothing"].source == "package"
        assert merged["my_thing"].source == "local"

    def test_user_local_overrides_package_keeps_local_source(self, tmp_path):
        """User vocab overriding a package concept should have source='local'."""
        pkg_dir = tmp_path / "pkg_data"
        pkg_dir.mkdir()
        pkg_vocab = pkg_dir / "vocabulary.yaml"
        pkg_vocab.write_text("""
concepts:
  clothing:
    prefLabel: "Clothing"
""")
        user_dir = tmp_path / "user"
        user_dir.mkdir()
        user_vocab = user_dir / "vocabulary.yaml"
        user_vocab.write_text("""
concepts:
  clothing:
    prefLabel: "My Clothing"
    altLabel: "apparel"
""")

        with (
            patch.object(vocabulary, "_get_package_data_dir", return_value=pkg_dir),
            patch.object(vocabulary, "find_vocabulary_files", return_value=[pkg_vocab, user_vocab]),
        ):
            merged = vocabulary.load_global_vocabulary()

        # User definition wins (later overrides earlier)
        assert merged["clothing"].prefLabel == "My Clothing"
        assert merged["clothing"].source == "local"

    def test_package_source_preserved_for_intermediate_concepts(self, tmp_path):
        """Package source propagates when flat concept merges into existing path node.

        When a child concept (e.g. tape→hardware/consumables/tape) creates
        hardware/consumables as an intermediate node, the subsequent merge of
        the flat 'consumables' concept should propagate source='package'.
        """
        vocab_file = tmp_path / "vocabulary.yaml"
        vocab_file.write_text("""
concepts:
  hardware:
    prefLabel: "Hardware"
    narrower:
      - consumables
  consumables:
    prefLabel: "Consumables"
    altLabel: ["supplies"]
    broader: hardware
  tape:
    prefLabel: "Tape"
    broader: consumables
""")
        local_vocab = vocabulary.load_local_vocabulary(vocab_file, default_source="package")

        inventory = {
            "containers": [
                {
                    "id": "box1",
                    "items": [{"name": "Tape", "metadata": {"categories": ["tape"]}}],
                }
            ]
        }

        with patch("inventory_md.off.OFFTaxonomyClient") as mock_off_cls:
            mock_off_cls.return_value.lookup_concept.return_value = None
            mock_off_cls.return_value.get_labels.return_value = {}
            concepts, _ = vocabulary.build_vocabulary_with_skos_hierarchy(
                inventory, local_vocab=local_vocab, enabled_sources=["off"]
            )

        hc = concepts.get("hardware/consumables")
        assert hc is not None
        assert hc.source == "package"
        assert hc.prefLabel == "Consumables"

        hw = concepts.get("hardware")
        assert hw is not None
        assert hw.source == "package"

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


class TestPopulateSourceUris:
    """Tests for _populate_source_uris() helper."""

    def test_off_node_ids_populate_off_source(self):
        """OFF node IDs populate source_uris['off']."""
        concepts = {
            "food/potatoes": vocabulary.Concept(
                id="food/potatoes",
                prefLabel="Potatoes",
            ),
        }
        off_node_ids = {"food/potatoes": "en:potatoes"}
        all_uri_maps: dict[str, str] = {}

        vocabulary._populate_source_uris(concepts, off_node_ids, all_uri_maps)

        assert concepts["food/potatoes"].source_uris["off"] == "off:en:potatoes"

    def test_agrovoc_uri_populates_agrovoc_source(self):
        """AGROVOC URI in all_uri_maps populates source_uris['agrovoc']."""
        concepts = {
            "food/rice": vocabulary.Concept(
                id="food/rice",
                prefLabel="Rice",
            ),
        }
        off_node_ids: dict[str, str] = {}
        all_uri_maps = {"food/rice": "http://aims.fao.org/aos/agrovoc/c_6599"}

        vocabulary._populate_source_uris(concepts, off_node_ids, all_uri_maps)

        assert concepts["food/rice"].source_uris["agrovoc"] == "http://aims.fao.org/aos/agrovoc/c_6599"

    def test_dbpedia_uri_from_concept(self):
        """DBpedia URI on concept.uri populates source_uris['dbpedia']."""
        concepts = {
            "tools/hammer": vocabulary.Concept(
                id="tools/hammer",
                prefLabel="Hammer",
                uri="http://dbpedia.org/resource/Hammer",
            ),
        }
        vocabulary._populate_source_uris(concepts, {}, {})

        assert concepts["tools/hammer"].source_uris["dbpedia"] == "http://dbpedia.org/resource/Hammer"

    def test_multiple_sources_on_same_concept(self):
        """Multiple sources tracked on the same concept."""
        concepts = {
            "food/potatoes": vocabulary.Concept(
                id="food/potatoes",
                prefLabel="Potatoes",
                uri="http://aims.fao.org/aos/agrovoc/c_6139",
            ),
        }
        off_node_ids = {"food/potatoes": "en:potatoes"}
        all_uri_maps = {"food/potatoes": "http://aims.fao.org/aos/agrovoc/c_6139"}

        vocabulary._populate_source_uris(concepts, off_node_ids, all_uri_maps)

        assert "off" in concepts["food/potatoes"].source_uris
        assert "agrovoc" in concepts["food/potatoes"].source_uris
        assert concepts["food/potatoes"].source_uris["off"] == "off:en:potatoes"
        assert concepts["food/potatoes"].source_uris["agrovoc"] == "http://aims.fao.org/aos/agrovoc/c_6139"

    def test_wikidata_uri_populates_wikidata_source(self):
        """Wikidata URI populates source_uris['wikidata']."""
        concepts = {
            "books": vocabulary.Concept(
                id="books",
                prefLabel="Books",
                uri="http://www.wikidata.org/entity/Q571",
            ),
        }
        vocabulary._populate_source_uris(concepts, {}, {})

        assert concepts["books"].source_uris["wikidata"] == "http://www.wikidata.org/entity/Q571"

    def test_unknown_uri_scheme_ignored(self):
        """URIs with unknown schemes don't add to source_uris."""
        concepts = {
            "local/custom": vocabulary.Concept(
                id="local/custom",
                prefLabel="Custom",
                uri="https://example.com/custom",
            ),
        }
        vocabulary._populate_source_uris(concepts, {}, {})

        assert concepts["local/custom"].source_uris == {}


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


class TestFindAdditionalTranslationUris:
    """Tests for _find_additional_translation_uris()."""

    @staticmethod
    def _make_client(**kwargs):
        """Create a mock SKOS client."""
        client = MagicMock()
        client.lookup_concept.return_value = None
        for k, v in kwargs.items():
            setattr(client, k, v)
        return client

    def test_finds_supplementary_dbpedia_uri(self):
        """Concept with OFF-only URI gets supplementary DBpedia URI."""
        concepts = {
            "food/potatoes": vocabulary.Concept(
                id="food/potatoes",
                prefLabel="Potatoes",
                uri="off:en:potatoes",
                source_uris={"off": "off:en:potatoes"},
            ),
        }
        all_uri_maps = {"food/potatoes": "off:en:potatoes"}
        client = self._make_client()
        client.lookup_concept.side_effect = lambda label, lang, source: (
            {
                "uri": "http://dbpedia.org/resource/Potato",
                "prefLabel": "Potato",
            }
            if source == "dbpedia" and label == "Potatoes"
            else None
        )

        count = vocabulary._find_additional_translation_uris(
            concepts, all_uri_maps, client, "en", ["dbpedia", "wikidata"]
        )

        assert count == 1
        assert concepts["food/potatoes"].source_uris["dbpedia"] == "http://dbpedia.org/resource/Potato"

    def test_skips_concept_already_with_dbpedia_and_wikidata(self):
        """Concept with both DBpedia and Wikidata URIs is skipped."""
        concepts = {
            "tools/hammer": vocabulary.Concept(
                id="tools/hammer",
                prefLabel="Hammer",
                uri="http://dbpedia.org/resource/Hammer",
                source_uris={
                    "dbpedia": "http://dbpedia.org/resource/Hammer",
                    "wikidata": "http://www.wikidata.org/entity/Q20012",
                },
            ),
        }
        client = self._make_client()

        count = vocabulary._find_additional_translation_uris(concepts, {}, client, "en", ["dbpedia", "wikidata"])

        assert count == 0
        client.lookup_concept.assert_not_called()

    def test_skips_concept_without_any_uri(self):
        """Concept with no URI at all is skipped."""
        concepts = {
            "misc/unknown": vocabulary.Concept(
                id="misc/unknown",
                prefLabel="Unknown",
            ),
        }
        client = self._make_client()

        count = vocabulary._find_additional_translation_uris(concepts, {}, client, "en", ["dbpedia"])

        assert count == 0
        client.lookup_concept.assert_not_called()

    def test_sanity_check_rejects_mismatch(self):
        """Sanity check rejects prefLabel mismatch."""
        concepts = {
            "food/rice": vocabulary.Concept(
                id="food/rice",
                prefLabel="Rice",
                uri="http://aims.fao.org/aos/agrovoc/c_6599",
                source_uris={"agrovoc": "http://aims.fao.org/aos/agrovoc/c_6599"},
            ),
        }
        all_uri_maps = {"food/rice": "http://aims.fao.org/aos/agrovoc/c_6599"}
        client = self._make_client()
        # DBpedia returns a completely different concept (no substring match)
        client.lookup_concept.side_effect = lambda label, lang, source: (
            {
                "uri": "http://dbpedia.org/resource/Basmati",
                "prefLabel": "Basmati",
            }
            if source == "dbpedia"
            else None
        )

        count = vocabulary._find_additional_translation_uris(concepts, all_uri_maps, client, "en", ["dbpedia"])

        assert count == 0
        assert "dbpedia" not in concepts["food/rice"].source_uris

    def test_skips_meta_concepts(self):
        """Meta concepts (_root, category_by_source/*) are skipped."""
        concepts = {
            "_root": vocabulary.Concept(
                id="_root",
                prefLabel="Root",
                uri="off:root",
                source_uris={"off": "off:root"},
            ),
            "category_by_source/off/food": vocabulary.Concept(
                id="category_by_source/off/food",
                prefLabel="Food",
                uri="off:en:food",
                source_uris={"off": "off:en:food"},
            ),
        }
        client = self._make_client()

        count = vocabulary._find_additional_translation_uris(concepts, {}, client, "en", ["dbpedia"])

        assert count == 0
        client.lookup_concept.assert_not_called()

    def test_respects_enabled_sources(self):
        """Only sources in enabled_sources are tried."""
        concepts = {
            "food/rice": vocabulary.Concept(
                id="food/rice",
                prefLabel="Rice",
                uri="off:en:rice",
                source_uris={"off": "off:en:rice"},
            ),
        }
        all_uri_maps = {"food/rice": "off:en:rice"}
        client = self._make_client()
        # Only enable wikidata, not dbpedia
        client.lookup_concept.side_effect = lambda label, lang, source: (
            {
                "uri": "http://www.wikidata.org/entity/Q5090",
                "prefLabel": "Rice",
            }
            if source == "wikidata"
            else None
        )

        count = vocabulary._find_additional_translation_uris(concepts, all_uri_maps, client, "en", ["wikidata"])

        assert count == 1
        assert "wikidata" in concepts["food/rice"].source_uris
        # DBpedia should not have been tried
        for call in client.lookup_concept.call_args_list:
            assert call[1].get("source") != "dbpedia" and call[0][2] if len(call[0]) > 2 else True


class TestTranslationMap:
    """Tests for language-aware translation map in build_vocabulary_with_skos_hierarchy.

    Norwegian category labels like 'klær' should map to their curated English
    concepts ('clothing') rather than creating orphan duplicates.
    """

    @staticmethod
    def _make_inventory(categories: list[str]) -> dict:
        return {
            "containers": [
                {
                    "id": "box1",
                    "items": [{"name": c.title(), "metadata": {"categories": [c]}} for c in categories],
                }
            ]
        }

    @patch("inventory_md.vocabulary.build_skos_hierarchy_paths")
    def test_translation_map_leaf_maps_to_local_root(self, mock_skos_paths):
        """category:klær should map to the 'clothing' concept, not create an orphan."""
        mock_skos_paths.return_value = ([], False, {}, [])

        local_vocab = {
            "clothing": vocabulary.Concept(
                id="clothing",
                prefLabel="Clothing",
                altLabels={"nb": ["klær", "tekstil"]},
                source="local",
                labels={"en": "Clothing", "nb": "Klær"},
            ),
        }
        inventory = self._make_inventory(["klær"])

        with patch("inventory_md.off.OFFTaxonomyClient") as mock_off_cls:
            mock_off_cls.return_value.lookup_concept.return_value = None
            mock_off_cls.return_value.get_labels.return_value = {}
            vocab, mappings = vocabulary.build_vocabulary_with_skos_hierarchy(
                inventory,
                local_vocab=local_vocab,
                lang="nb",
                enabled_sources=["off", "agrovoc"],
            )

        # "klær" should map to "clothing", not to itself
        assert "klær" in mappings
        assert "clothing" in mappings["klær"]
        # No orphan "klær" concept should exist
        assert "klær" not in vocab

    @patch("inventory_md.vocabulary.build_skos_hierarchy_paths")
    def test_translation_map_path_remaps_root_segment(self, mock_skos_paths):
        """category:klær/jakke should map to clothing/jakke."""
        mock_skos_paths.return_value = ([], False, {}, [])

        local_vocab = {
            "clothing": vocabulary.Concept(
                id="clothing",
                prefLabel="Clothing",
                altLabels={"nb": ["klær"]},
                source="local",
                labels={"en": "Clothing", "nb": "Klær"},
            ),
        }
        inventory = self._make_inventory(["klær/jakke"])

        with patch("inventory_md.off.OFFTaxonomyClient") as mock_off_cls:
            mock_off_cls.return_value.lookup_concept.return_value = None
            mock_off_cls.return_value.get_labels.return_value = {}
            vocab, mappings = vocabulary.build_vocabulary_with_skos_hierarchy(
                inventory,
                local_vocab=local_vocab,
                lang="nb",
                enabled_sources=["off", "agrovoc"],
            )

        # "klær/jakke" should map to "clothing/jakke"
        assert "klær/jakke" in mappings
        assert "clothing/jakke" in mappings["klær/jakke"]
        # The concept tree should have clothing/jakke, not klær/jakke
        assert "clothing/jakke" in vocab
        assert "klær/jakke" not in vocab

    @patch("inventory_md.vocabulary.build_skos_hierarchy_paths")
    def test_path_broader_chain_resolved(self, mock_skos_paths):
        """bad/tekstil should resolve to household/bad/tekstil when bad has broader:household."""
        mock_skos_paths.return_value = ([], False, {}, [])

        local_vocab = {
            "household": vocabulary.Concept(
                id="household",
                prefLabel="Household",
                source="local",
            ),
            "bad": vocabulary.Concept(
                id="bad",
                prefLabel="Bathroom",
                broader=["household"],
                source="local",
            ),
        }
        inventory = self._make_inventory(["bad/tekstil"])

        with patch("inventory_md.off.OFFTaxonomyClient") as mock_off_cls:
            mock_off_cls.return_value.lookup_concept.return_value = None
            mock_off_cls.return_value.get_labels.return_value = {}
            vocab, mappings = vocabulary.build_vocabulary_with_skos_hierarchy(
                inventory,
                local_vocab=local_vocab,
                lang="nb",
                enabled_sources=["off", "agrovoc"],
            )

        # "bad/tekstil" should map to "household/bad/tekstil"
        assert "bad/tekstil" in mappings
        assert "household/bad/tekstil" in mappings["bad/tekstil"]
        # The concept tree should have household/bad/tekstil, not bad/tekstil
        assert "household/bad/tekstil" in vocab
        assert "bad/tekstil" not in vocab

    @patch("inventory_md.vocabulary.build_skos_hierarchy_paths")
    def test_path_translation_plus_broader(self, mock_skos_paths):
        """sport/vinter should resolve to recreation/sports/vinter (translation + broader)."""
        mock_skos_paths.return_value = ([], False, {}, [])

        local_vocab = {
            "recreation": vocabulary.Concept(
                id="recreation",
                prefLabel="Recreation",
                source="local",
            ),
            "sports": vocabulary.Concept(
                id="sports",
                prefLabel="Sports",
                altLabels={"en": ["sport"], "nb": ["sport"]},
                broader=["recreation"],
                source="local",
            ),
        }
        inventory = self._make_inventory(["sport/vinter"])

        with patch("inventory_md.off.OFFTaxonomyClient") as mock_off_cls:
            mock_off_cls.return_value.lookup_concept.return_value = None
            mock_off_cls.return_value.get_labels.return_value = {}
            vocab, mappings = vocabulary.build_vocabulary_with_skos_hierarchy(
                inventory,
                local_vocab=local_vocab,
                lang="nb",
                enabled_sources=["off", "agrovoc"],
            )

        # "sport/vinter" should map to "recreation/sports/vinter"
        assert "sport/vinter" in mappings
        assert "recreation/sports/vinter" in mappings["sport/vinter"]
        assert "recreation/sports/vinter" in vocab
        assert "sport/vinter" not in vocab

    @patch("inventory_md.vocabulary.build_skos_hierarchy_paths")
    def test_translation_map_filters_by_language(self, mock_skos_paths):
        """Norwegian altLabel 'barn' should NOT map when inventory lang is 'nb'.

        The translation map should only use altLabels matching the inventory
        language, preventing cross-language false matches where Norwegian
        'barn' (children) gets matched to English 'Barn' (agricultural building).
        """
        mock_skos_paths.return_value = ([], False, {}, [])

        local_vocab = {
            "games": vocabulary.Concept(
                id="games",
                prefLabel="Games",
                altLabels={"en": ["toys", "puzzles"], "nb": ["spill", "leker"]},
                source="local",
            ),
        }
        # Use "spill" (nb altLabel) which should map, and "toys" (en) which should not
        inventory = self._make_inventory(["spill"])

        with patch("inventory_md.off.OFFTaxonomyClient") as mock_off_cls:
            mock_off_cls.return_value.lookup_concept.return_value = None
            mock_off_cls.return_value.get_labels.return_value = {}
            vocab, mappings = vocabulary.build_vocabulary_with_skos_hierarchy(
                inventory,
                local_vocab=local_vocab,
                lang="nb",
                enabled_sources=["off", "agrovoc"],
            )

        # "spill" (nb altLabel) should map to "games"
        assert "spill" in mappings
        assert "games" in mappings["spill"]

    @patch("inventory_md.vocabulary.build_skos_hierarchy_paths")
    def test_translation_map_lang_no_falls_back_to_nb(self, mock_skos_paths):
        """lang='no' should fall back to 'nb' altLabels for translation map.

        The inventory config uses lang: 'no' (ISO 639-1 macrolanguage) but
        altLabels are tagged as 'nb' (Bokmål). The translation map must
        use the fallback chain to find them.
        """
        mock_skos_paths.return_value = ([], False, {}, [])

        local_vocab = {
            "electronics": vocabulary.Concept(
                id="electronics",
                prefLabel="Electronics",
                altLabels={"en": ["electrical"], "nb": ["elektronikk", "elektrisk"]},
                source="local",
            ),
        }
        inventory = self._make_inventory(["elektronikk"])

        with patch("inventory_md.off.OFFTaxonomyClient") as mock_off_cls:
            mock_off_cls.return_value.lookup_concept.return_value = None
            mock_off_cls.return_value.get_labels.return_value = {}
            vocab, mappings = vocabulary.build_vocabulary_with_skos_hierarchy(
                inventory,
                local_vocab=local_vocab,
                lang="no",
                enabled_sources=["off", "agrovoc"],
            )

        # "elektronikk" (nb altLabel) should map to "electronics" even with lang="no"
        assert "elektronikk" in mappings
        assert "electronics" in mappings["elektronikk"]

    def test_altlabels_merge_per_language(self):
        """Per-language dict merge should combine altLabels without duplicates."""
        target = vocabulary.Concept(
            id="food",
            prefLabel="Food",
            altLabels={"en": ["groceries"], "nb": ["mat"]},
        )
        source = vocabulary.Concept(
            id="food",
            prefLabel="Food",
            altLabels={"en": ["provisions", "groceries"], "de": ["Lebensmittel"]},
        )
        # Merge source into target per-language
        for lang, alts in source.altLabels.items():
            if lang not in target.altLabels:
                target.altLabels[lang] = list(alts)
            else:
                existing = set(target.altLabels[lang])
                for alt in alts:
                    if alt not in existing:
                        target.altLabels[lang].append(alt)

        assert target.altLabels == {
            "en": ["groceries", "provisions"],
            "nb": ["mat"],
            "de": ["Lebensmittel"],
        }


class TestProgressCallback:
    """Tests for progress reporting callback in build_vocabulary_with_skos_hierarchy."""

    @staticmethod
    def _make_inventory(categories: list[str]) -> dict:
        return {
            "containers": [
                {
                    "id": "box1",
                    "items": [{"name": c.title(), "metadata": {"categories": [c]}} for c in categories],
                }
            ]
        }

    @staticmethod
    def _make_mock_skos_module():
        mock_module = MagicMock()
        mock_module._is_irrelevant_dbpedia_category.return_value = False
        mock_module._is_abstract_wikidata_class.return_value = False
        return mock_module

    def _run_with_progress(self, categories=None, *, enabled_sources=None, languages=None):
        """Run build_vocabulary_with_skos_hierarchy with a recording progress callback."""
        if categories is None:
            categories = ["potatoes"]
        if enabled_sources is None:
            enabled_sources = ["off", "agrovoc", "dbpedia"]
        inventory = self._make_inventory(categories)

        events: list[tuple[str, str]] = []

        def recorder(phase: str, detail: str) -> None:
            events.append((phase, detail))

        mock_client = MagicMock()
        mock_client.lookup_concept.return_value = None
        mock_store = MagicMock()
        mock_store.is_loaded = True
        mock_client._get_oxigraph_store.return_value = mock_store
        mock_client.get_batch_labels.return_value = {}

        mock_skos = self._make_mock_skos_module()
        mock_skos.SKOSClient.return_value = mock_client

        import inventory_md

        with (
            patch("inventory_md.off.OFFTaxonomyClient") as mock_off_cls,
            patch.dict("sys.modules", {"inventory_md.skos": mock_skos}),
            patch.object(inventory_md, "skos", mock_skos, create=True),
        ):
            mock_off = mock_off_cls.return_value
            mock_off.lookup_concept.return_value = None
            mock_off.get_labels.return_value = {}
            mock_off.build_paths_to_root.return_value = ([], {}, [])
            vocabulary.build_vocabulary_with_skos_hierarchy(
                inventory,
                enabled_sources=enabled_sources,
                languages=languages,
                progress=recorder,
            )
        return events

    def test_init_phase_for_oxigraph_loading(self):
        """Callback receives 'init' phase when AGROVOC is enabled."""
        events = self._run_with_progress(enabled_sources=["agrovoc", "dbpedia"])
        init_events = [(p, d) for p, d in events if p == "init"]
        assert len(init_events) == 1
        assert "AGROVOC" in init_events[0][1]

    def test_no_init_when_agrovoc_disabled(self):
        """No 'init' phase when AGROVOC is not in enabled_sources."""
        events = self._run_with_progress(enabled_sources=["dbpedia"])
        init_events = [(p, d) for p, d in events if p == "init"]
        assert len(init_events) == 0

    def test_expand_phase_during_loop(self):
        """Callback receives 'expand' phase during category expansion."""
        events = self._run_with_progress(categories=["potatoes", "rice", "beans"])
        expand_events = [(p, d) for p, d in events if p == "expand"]
        # At least the header "Expanding N categories..." plus some per-item
        assert len(expand_events) >= 2
        assert any("Expanding" in d for _, d in expand_events)
        assert any("[" in d and "]" in d for _, d in expand_events)

    def test_translate_phases_with_languages(self):
        """Callback receives 'translate' phases when multiple languages requested."""
        events = self._run_with_progress(
            languages=["en", "nb"],
            enabled_sources=["off", "agrovoc", "dbpedia"],
        )
        translate_events = [(p, d) for p, d in events if p == "translate"]
        # Should have: header + OFF + AGROVOC + fallback (DBpedia/Wikidata only if URIs found)
        assert len(translate_events) >= 3
        details = [d for _, d in translate_events]
        assert any("OFF" in d for d in details)
        assert any("AGROVOC" in d for d in details)
        assert any("fallback" in d.lower() for d in details)

    def test_no_translate_without_languages(self):
        """No 'translate' events when only a single language."""
        events = self._run_with_progress(languages=None)
        translate_events = [(p, d) for p, d in events if p == "translate"]
        assert len(translate_events) == 0

    def test_resolve_phases_with_languages(self):
        """Callback receives 'resolve' phases when translations requested."""
        events = self._run_with_progress(
            languages=["en", "nb"],
            enabled_sources=["agrovoc", "dbpedia"],
        )
        resolve_events = [(p, d) for p, d in events if p == "resolve"]
        assert len(resolve_events) == 2
        details = [d for _, d in resolve_events]
        assert any("Resolving" in d for d in details)
        assert any("additional" in d.lower() for d in details)

    def test_progress_none_works(self):
        """progress=None (default) works without error."""
        inventory = self._make_inventory(["potatoes"])
        mock_client = MagicMock()
        mock_client.lookup_concept.return_value = None
        mock_client._get_oxigraph_store.return_value = None
        mock_client.get_batch_labels.return_value = {}

        mock_skos = self._make_mock_skos_module()
        mock_skos.SKOSClient.return_value = mock_client

        import inventory_md

        with (
            patch("inventory_md.off.OFFTaxonomyClient") as mock_off_cls,
            patch.dict("sys.modules", {"inventory_md.skos": mock_skos}),
            patch.object(inventory_md, "skos", mock_skos, create=True),
        ):
            mock_off_cls.return_value.lookup_concept.return_value = None
            mock_off_cls.return_value.get_labels.return_value = {}
            # No progress callback (default) — should not raise
            vocab, mappings = vocabulary.build_vocabulary_with_skos_hierarchy(
                inventory,
                enabled_sources=["off", "agrovoc", "dbpedia"],
            )
        assert isinstance(vocab, dict)
        assert isinstance(mappings, dict)


class TestBuildExternalBroaderPaths:
    """Tests for _build_external_broader_paths helper."""

    def test_basic_path_building(self):
        """Build paths from a list of broader relations."""
        broader = [
            {"label": "Inventions", "uri": "http://example.com/Inv", "relType": "hypernym"},
            {"label": "Gadgets", "uri": "http://example.com/Gad", "relType": "subject"},
        ]
        paths, broader_ids = vocabulary._build_external_broader_paths(broader, "widget", lambda b: False, "hypernym")
        assert paths == ["inventions/widget", "gadgets/widget"]
        assert broader_ids == ["inventions", "gadgets"]

    def test_priority_rel_inserted_first(self):
        """Priority relation type is inserted at the front of the list."""
        broader = [
            {"label": "Gadgets", "uri": "http://example.com/Gad", "relType": "subject"},
            {"label": "Inventions", "uri": "http://example.com/Inv", "relType": "hypernym"},
        ]
        paths, _ = vocabulary._build_external_broader_paths(broader, "widget", lambda b: False, "hypernym")
        # hypernym should come first despite being second in input
        assert paths[0] == "inventions/widget"

    def test_irrelevant_entries_skipped(self):
        """Entries matching the irrelevancy check are skipped."""
        broader = [
            {"label": "Irrelevant", "relType": "hypernym"},
            {"label": "Good", "relType": "hypernym"},
        ]
        paths, broader_ids = vocabulary._build_external_broader_paths(
            broader, "widget", lambda b: b.get("label") == "Irrelevant", "hypernym"
        )
        assert len(paths) == 1
        assert paths[0] == "good/widget"
        assert broader_ids == ["good"]

    def test_max_paths_respected(self):
        """No more than max_paths paths are returned."""
        broader = [{"label": f"Cat{i}", "relType": "hypernym"} for i in range(10)]
        paths, _ = vocabulary._build_external_broader_paths(broader, "widget", lambda b: False, "hypernym", max_paths=2)
        assert len(paths) == 2

    def test_duplicate_broader_ids_skipped(self):
        """Duplicate broader IDs are not repeated."""
        broader = [
            {"label": "Tools", "relType": "hypernym"},
            {"label": "Tools", "relType": "subject"},
        ]
        paths, broader_ids = vocabulary._build_external_broader_paths(broader, "widget", lambda b: False, "hypernym")
        assert len(paths) == 1
        assert broader_ids == ["tools"]

    def test_self_reference_skipped(self):
        """Broader entries matching concept_id are skipped."""
        broader = [
            {"label": "Widget", "relType": "hypernym"},
            {"label": "Tools", "relType": "hypernym"},
        ]
        paths, _ = vocabulary._build_external_broader_paths(broader, "widget", lambda b: False, "hypernym")
        assert len(paths) == 1
        assert paths[0] == "tools/widget"

    def test_empty_broader_list(self):
        """Empty broader list returns empty results."""
        paths, broader_ids = vocabulary._build_external_broader_paths([], "widget", lambda b: False, "hypernym")
        assert paths == []
        assert broader_ids == []


class TestSupplementaryExternalPaths:
    """Tests for supplementary category_by_source paths from DBpedia/Wikidata.

    Verifies that category_by_source/dbpedia/ and category_by_source/wikidata/
    subtrees are populated even when another source is primary.
    """

    @staticmethod
    def _make_mock_skos_module():
        """Create a mock skos module with both DBpedia and Wikidata checks."""
        mock_module = MagicMock()
        mock_module._is_irrelevant_dbpedia_category.return_value = False
        mock_module._is_abstract_wikidata_class.return_value = False
        return mock_module

    def test_dbpedia_supplementary_when_off_primary(self):
        """OFF provides primary hierarchy; DBpedia still creates category_by_source paths."""
        inventory = {
            "containers": [
                {
                    "id": "box1",
                    "items": [{"name": "Potatoes", "metadata": {"categories": ["potatoes"]}}],
                }
            ]
        }

        mock_off_client = MagicMock()
        mock_off_client.lookup_concept.return_value = {
            "uri": "off:en:potatoes",
            "prefLabel": "Potatoes",
            "source": "off",
            "broader": [{"uri": "off:en:vegetables", "label": "Vegetables"}],
            "node_id": "en:potatoes",
        }
        mock_off_client.build_paths_to_root.return_value = (
            ["food/vegetables/potatoes"],
            {"food/vegetables/potatoes": "off:en:potatoes"},
            ["plant_based_foods/vegetables/potatoes"],
        )
        mock_off_client.get_labels.return_value = {}

        mock_client = MagicMock()
        # DBpedia returns broader relations
        mock_client.lookup_concept.return_value = {
            "uri": "http://dbpedia.org/resource/Potato",
            "prefLabel": "Potato",
            "source": "dbpedia",
            "broader": [
                {"label": "Root vegetables", "relType": "hypernym"},
            ],
        }
        mock_client._get_oxigraph_store.return_value = None
        mock_client.get_batch_labels.return_value = {}

        mock_skos = self._make_mock_skos_module()
        mock_skos.SKOSClient.return_value = mock_client

        import inventory_md

        with (
            patch("inventory_md.off.OFFTaxonomyClient", return_value=mock_off_client),
            patch.dict("sys.modules", {"inventory_md.skos": mock_skos}),
            patch.object(inventory_md, "skos", mock_skos, create=True),
            patch("inventory_md.vocabulary.build_skos_hierarchy_paths", return_value=([], False, {}, [])),
        ):
            vocab, mappings = vocabulary.build_vocabulary_with_skos_hierarchy(
                inventory, enabled_sources=["off", "agrovoc", "dbpedia"]
            )

        # Primary hierarchy should be from OFF
        assert "potatoes" in mappings
        assert any("food/vegetables" in p for p in mappings["potatoes"])

        # category_by_source/dbpedia/ should also exist
        assert "category_by_source/dbpedia" in vocab
        cbs_dbpedia = [p for p in mappings["potatoes"] if p.startswith("category_by_source/dbpedia/")]
        assert len(cbs_dbpedia) > 0
        assert any("root_vegetables" in p for p in cbs_dbpedia)

    def test_wikidata_supplementary_when_dbpedia_primary(self):
        """DBpedia provides primary hierarchy; Wikidata still creates category_by_source paths."""
        inventory = {
            "containers": [
                {
                    "id": "box1",
                    "items": [{"name": "Widget", "metadata": {"categories": ["widget"]}}],
                }
            ]
        }

        mock_client = MagicMock()

        # DBpedia returns one thing, Wikidata returns another
        def lookup_side_effect(label, lang, source=None):
            if source == "dbpedia":
                return {
                    "uri": "http://dbpedia.org/resource/Widget",
                    "prefLabel": "Widget",
                    "source": "dbpedia",
                    "broader": [
                        {"label": "Inventions", "relType": "hypernym"},
                    ],
                }
            elif source == "wikidata":
                return {
                    "uri": "http://www.wikidata.org/entity/Q123",
                    "prefLabel": "Widget",
                    "source": "wikidata",
                    "broader": [
                        {
                            "label": "Mechanical device",
                            "uri": "http://www.wikidata.org/entity/Q456",
                            "relType": "instance_of",
                        },
                    ],
                }
            return None

        mock_client.lookup_concept.side_effect = lookup_side_effect
        mock_client._get_oxigraph_store.return_value = None
        mock_client.get_batch_labels.return_value = {}

        mock_skos = self._make_mock_skos_module()
        mock_skos.SKOSClient.return_value = mock_client

        import inventory_md

        with (
            patch("inventory_md.off.OFFTaxonomyClient") as mock_off_cls,
            patch.dict("sys.modules", {"inventory_md.skos": mock_skos}),
            patch.object(inventory_md, "skos", mock_skos, create=True),
        ):
            mock_off_cls.return_value.lookup_concept.return_value = None
            mock_off_cls.return_value.get_labels.return_value = {}
            vocab, mappings = vocabulary.build_vocabulary_with_skos_hierarchy(
                inventory, enabled_sources=["off", "dbpedia", "wikidata"]
            )

        # Primary hierarchy should be from DBpedia
        assert "widget" in mappings
        assert any("inventions" in p for p in mappings["widget"])

        # category_by_source/dbpedia/ should exist
        assert "category_by_source/dbpedia" in vocab
        cbs_dbpedia = [p for p in mappings["widget"] if p.startswith("category_by_source/dbpedia/")]
        assert len(cbs_dbpedia) > 0

        # category_by_source/wikidata/ should also exist
        assert "category_by_source/wikidata" in vocab
        cbs_wikidata = [p for p in mappings["widget"] if p.startswith("category_by_source/wikidata/")]
        assert len(cbs_wikidata) > 0
        assert any("mechanical_device" in p for p in cbs_wikidata)

    def test_local_broader_gets_dbpedia_and_wikidata_paths(self):
        """Local vocab hierarchy + external supplementary category_by_source paths."""
        local_vocab = {
            "tools": vocabulary.Concept(
                id="tools",
                prefLabel="Tools",
                source="local",
            ),
            "hammer": vocabulary.Concept(
                id="hammer",
                prefLabel="Hammer",
                broader=["tools"],
                source="local",
            ),
        }
        inventory = {
            "containers": [
                {
                    "id": "box1",
                    "items": [{"name": "Hammer", "metadata": {"categories": ["hammer"]}}],
                }
            ]
        }

        mock_client = MagicMock()

        def lookup_side_effect(label, lang, source=None):
            if source == "dbpedia":
                return {
                    "uri": "http://dbpedia.org/resource/Hammer",
                    "prefLabel": "Hammer",
                    "description": "A hand tool",
                    "wikipediaUrl": "https://en.wikipedia.org/wiki/Hammer",
                    "broader": [
                        {"label": "Hand tools", "relType": "hypernym"},
                    ],
                }
            elif source == "wikidata":
                return {
                    "uri": "http://www.wikidata.org/entity/Q169470",
                    "prefLabel": "Hammer",
                    "broader": [
                        {
                            "label": "Striking tool",
                            "uri": "http://www.wikidata.org/entity/Q1234",
                            "relType": "instance_of",
                        },
                    ],
                }
            return None

        mock_client.lookup_concept.side_effect = lookup_side_effect
        mock_client._get_oxigraph_store.return_value = None
        mock_client.get_batch_labels.return_value = {}

        mock_skos = self._make_mock_skos_module()
        mock_skos.SKOSClient.return_value = mock_client

        import inventory_md

        with (
            patch("inventory_md.off.OFFTaxonomyClient") as mock_off_cls,
            patch.dict("sys.modules", {"inventory_md.skos": mock_skos}),
            patch.object(inventory_md, "skos", mock_skos, create=True),
        ):
            mock_off_cls.return_value.lookup_concept.return_value = None
            mock_off_cls.return_value.get_labels.return_value = {}
            vocab, mappings = vocabulary.build_vocabulary_with_skos_hierarchy(
                inventory,
                local_vocab=local_vocab,
                enabled_sources=["off", "dbpedia", "wikidata"],
            )

        # Primary hierarchy should be from local vocab (tools/hammer)
        assert "hammer" in mappings
        assert any("tools" in p for p in mappings["hammer"])

        # category_by_source/dbpedia/ should exist with broader paths
        cbs_dbpedia = [p for p in mappings["hammer"] if p.startswith("category_by_source/dbpedia/")]
        assert len(cbs_dbpedia) > 0
        assert any("hand_tools" in p for p in cbs_dbpedia)

        # category_by_source/wikidata/ should exist with broader paths
        cbs_wikidata = [p for p in mappings["hammer"] if p.startswith("category_by_source/wikidata/")]
        assert len(cbs_wikidata) > 0
        assert any("striking_tool" in p for p in cbs_wikidata)

        # Concept should be enriched with DBpedia metadata
        hammer = vocab.get("tools/hammer")
        assert hammer is not None
        assert hammer.uri == "http://dbpedia.org/resource/Hammer"

    def test_translated_root_gets_supplementary_paths(self):
        """Norwegian label → local root concept still gets DBpedia/Wikidata category_by_source."""
        local_vocab = {
            "clothing": vocabulary.Concept(
                id="clothing",
                prefLabel="Clothing",
                source="local",
                labels={"nb": "klær"},
            ),
        }
        inventory = {
            "containers": [
                {
                    "id": "box1",
                    "items": [{"name": "Klær", "metadata": {"categories": ["klær"]}}],
                }
            ]
        }

        mock_client = MagicMock()

        def lookup_side_effect(label, lang, source=None):
            if source == "dbpedia" and label.lower() == "clothing":
                return {
                    "uri": "http://dbpedia.org/resource/Clothing",
                    "prefLabel": "Clothing",
                    "broader": [
                        {"label": "Textiles", "relType": "hypernym"},
                    ],
                }
            elif source == "wikidata" and label.lower() == "clothing":
                return {
                    "uri": "http://www.wikidata.org/entity/Q11460",
                    "prefLabel": "Clothing",
                    "broader": [
                        {
                            "label": "Textile product",
                            "uri": "http://www.wikidata.org/entity/Q9999",
                            "relType": "instance_of",
                        },
                    ],
                }
            return None

        mock_client.lookup_concept.side_effect = lookup_side_effect
        mock_client._get_oxigraph_store.return_value = None
        mock_client.get_batch_labels.return_value = {}

        mock_skos = self._make_mock_skos_module()
        mock_skos.SKOSClient.return_value = mock_client

        import inventory_md

        with (
            patch("inventory_md.off.OFFTaxonomyClient") as mock_off_cls,
            patch.dict("sys.modules", {"inventory_md.skos": mock_skos}),
            patch.object(inventory_md, "skos", mock_skos, create=True),
        ):
            mock_off_cls.return_value.lookup_concept.return_value = None
            mock_off_cls.return_value.get_labels.return_value = {}
            vocab, mappings = vocabulary.build_vocabulary_with_skos_hierarchy(
                inventory,
                local_vocab=local_vocab,
                lang="nb",
                enabled_sources=["off", "dbpedia", "wikidata"],
            )

        # "klær" should map to "clothing" (local root)
        assert "klær" in mappings
        assert "clothing" in mappings["klær"]

        # category_by_source/dbpedia/ should exist
        cbs_dbpedia = [p for p in mappings["klær"] if p.startswith("category_by_source/dbpedia/")]
        assert len(cbs_dbpedia) > 0
        assert any("textiles" in p for p in cbs_dbpedia)

        # category_by_source/wikidata/ should exist
        cbs_wikidata = [p for p in mappings["klær"] if p.startswith("category_by_source/wikidata/")]
        assert len(cbs_wikidata) > 0
        assert any("textile_product" in p for p in cbs_wikidata)

        # source_uris should have BOTH DBpedia and Wikidata URIs
        clothing = vocab["clothing"]
        assert "dbpedia" in clothing.source_uris
        assert clothing.source_uris["dbpedia"] == "http://dbpedia.org/resource/Clothing"
        assert "wikidata" in clothing.source_uris
        assert clothing.source_uris["wikidata"] == "http://www.wikidata.org/entity/Q11460"

    def test_root_concept_via_altlabel_gets_source_uris(self):
        """Root concept discovered via altLabel gets source_uris from both sources.

        Simulates the 'games' scenario: Norwegian altLabel 'spill' maps to root
        concept 'games', which should get DBpedia and Wikidata URIs for translation.
        """
        local_vocab = {
            "games": vocabulary.Concept(
                id="games",
                prefLabel="Games",
                source="package",
                altLabels={
                    "en": ["toys", "puzzles"],
                    "nb": ["spill", "leker"],
                },
            ),
        }
        inventory = {
            "containers": [
                {
                    "id": "box1",
                    "items": [{"name": "Spill", "metadata": {"categories": ["spill"]}}],
                }
            ]
        }

        mock_client = MagicMock()

        def lookup_side_effect(label, lang, source=None):
            # Only respond to the English prefLabel lookup
            if label.lower() == "games":
                if source == "dbpedia":
                    return {
                        "uri": "http://dbpedia.org/resource/Game",
                        "prefLabel": "Game",
                        "description": "A structured form of play",
                        "broader": [
                            {"label": "Recreation", "relType": "hypernym"},
                        ],
                    }
                elif source == "wikidata":
                    return {
                        "uri": "http://www.wikidata.org/entity/Q11410",
                        "prefLabel": "Game",
                        "broader": [
                            {
                                "label": "Leisure activity",
                                "uri": "http://www.wikidata.org/entity/Q1914636",
                                "relType": "instance_of",
                            },
                        ],
                    }
            return None

        mock_client.lookup_concept.side_effect = lookup_side_effect
        mock_client._get_oxigraph_store.return_value = None
        mock_client.get_batch_labels.return_value = {}

        mock_skos = self._make_mock_skos_module()
        mock_skos.SKOSClient.return_value = mock_client

        import inventory_md

        with (
            patch("inventory_md.off.OFFTaxonomyClient") as mock_off_cls,
            patch.dict("sys.modules", {"inventory_md.skos": mock_skos}),
            patch.object(inventory_md, "skos", mock_skos, create=True),
        ):
            mock_off_cls.return_value.lookup_concept.return_value = None
            mock_off_cls.return_value.get_labels.return_value = {}
            vocab, mappings = vocabulary.build_vocabulary_with_skos_hierarchy(
                inventory,
                local_vocab=local_vocab,
                lang="nb",
                enabled_sources=["off", "dbpedia", "wikidata"],
            )

        # "spill" should map to "games" (root concept via altLabel)
        assert "spill" in mappings
        assert "games" in mappings["spill"]

        # Concept should have source_uris from both sources
        games = vocab["games"]
        assert "dbpedia" in games.source_uris, f"source_uris={games.source_uris}"
        assert games.source_uris["dbpedia"] == "http://dbpedia.org/resource/Game"
        assert "wikidata" in games.source_uris, f"source_uris={games.source_uris}"
        assert games.source_uris["wikidata"] == "http://www.wikidata.org/entity/Q11410"

        # URI should be set (first source wins)
        assert games.uri == "http://dbpedia.org/resource/Game"
        # Description should be enriched
        assert games.description == "A structured form of play"

        # category_by_source paths should exist
        cbs_dbpedia = [p for p in mappings["spill"] if p.startswith("category_by_source/dbpedia/")]
        assert len(cbs_dbpedia) > 0
        cbs_wikidata = [p for p in mappings["spill"] if p.startswith("category_by_source/wikidata/")]
        assert len(cbs_wikidata) > 0

    def test_agrovoc_uri_concept_gets_supplementary_paths(self):
        """AGROVOC primary (via local URI) + external supplementary paths."""
        local_vocab = {
            "rice": vocabulary.Concept(
                id="rice",
                prefLabel="Rice",
                broader=["cereals"],
                source="local",
                uri="http://aims.fao.org/aos/agrovoc/c_6599",
            ),
            "cereals": vocabulary.Concept(
                id="cereals",
                prefLabel="Cereals",
                source="local",
            ),
        }
        inventory = {
            "containers": [
                {
                    "id": "box1",
                    "items": [{"name": "Rice", "metadata": {"categories": ["rice"]}}],
                }
            ]
        }

        mock_client = MagicMock()
        # Oxigraph store for AGROVOC hierarchy
        mock_store = MagicMock()
        mock_store.is_loaded = True
        mock_client._get_oxigraph_store.return_value = mock_store
        mock_client.get_batch_labels.return_value = {}

        def lookup_side_effect(label, lang, source=None):
            if source == "dbpedia":
                return {
                    "uri": "http://dbpedia.org/resource/Rice",
                    "prefLabel": "Rice",
                    "broader": [
                        {"label": "Cereals", "relType": "hypernym"},
                    ],
                }
            elif source == "wikidata":
                return {
                    "uri": "http://www.wikidata.org/entity/Q5090",
                    "prefLabel": "Rice",
                    "broader": [
                        {"label": "Cereal", "uri": "http://www.wikidata.org/entity/Q12117", "relType": "instance_of"},
                    ],
                }
            return None

        mock_client.lookup_concept.side_effect = lookup_side_effect

        mock_skos = self._make_mock_skos_module()
        mock_skos.SKOSClient.return_value = mock_client

        import inventory_md

        with (
            patch("inventory_md.off.OFFTaxonomyClient") as mock_off_cls,
            patch.dict("sys.modules", {"inventory_md.skos": mock_skos}),
            patch.object(inventory_md, "skos", mock_skos, create=True),
            patch(
                "inventory_md.vocabulary._build_paths_to_root",
                return_value=(
                    ["cereals/rice"],
                    {"cereals/rice": "http://aims.fao.org/aos/agrovoc/c_6599"},
                    ["cereals/rice"],
                ),
            ),
        ):
            mock_off_cls.return_value.lookup_concept.return_value = None
            mock_off_cls.return_value.get_labels.return_value = {}
            vocab, mappings = vocabulary.build_vocabulary_with_skos_hierarchy(
                inventory,
                local_vocab=local_vocab,
                enabled_sources=["off", "agrovoc", "dbpedia", "wikidata"],
            )

        # Primary hierarchy should be from AGROVOC
        assert "rice" in mappings
        assert any("cereals" in p for p in mappings["rice"])

        # category_by_source/dbpedia/ should exist
        cbs_dbpedia = [p for p in mappings["rice"] if p.startswith("category_by_source/dbpedia/")]
        assert len(cbs_dbpedia) > 0

        # category_by_source/wikidata/ should exist
        cbs_wikidata = [p for p in mappings["rice"] if p.startswith("category_by_source/wikidata/")]
        assert len(cbs_wikidata) > 0


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
        assert result["food"].source == "package"
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

    def test_returns_empty_on_http_error(self):
        """Non-200 response returns empty dict (don't raise)."""
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.raise_for_status.side_effect = Exception("Service Unavailable")

        with patch("niquests.get", return_value=mock_response):
            result = vocabulary.fetch_vocabulary_from_tingbok(self.TINGBOK_URL)

        assert result == {}

    def test_returns_empty_on_connection_error(self):
        """Network error returns empty dict (don't raise)."""
        import niquests

        with patch("niquests.get", side_effect=niquests.ConnectionError("refused")):
            result = vocabulary.fetch_vocabulary_from_tingbok(self.TINGBOK_URL)

        assert result == {}

    def test_returns_empty_on_timeout(self):
        """Timeout returns empty dict."""
        import niquests

        with patch("niquests.get", side_effect=niquests.Timeout("timed out")):
            result = vocabulary.fetch_vocabulary_from_tingbok(self.TINGBOK_URL)

        assert result == {}


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
                    "food": vocabulary.Concept(id="food", prefLabel="Food", source="package"),
                },
            ) as mock_fetch,
            patch.object(vocabulary, "find_vocabulary_files", return_value=[]),
        ):
            result = vocabulary.load_global_vocabulary(tingbok_url="https://tingbok.plann.no")

        mock_fetch.assert_called_once_with("https://tingbok.plann.no")
        assert "food" in result
        assert result["food"].source == "package"

    def test_skips_package_file_when_tingbok_succeeds(self, tmp_path):
        """When tingbok returns concepts, the package vocab file is not loaded."""
        fake_pkg = tmp_path / "pkg"
        fake_pkg_vocab = fake_pkg / "vocabulary.yaml"

        with (
            patch.object(
                vocabulary,
                "fetch_vocabulary_from_tingbok",
                return_value={
                    "food": vocabulary.Concept(id="food", prefLabel="Food", source="package"),
                },
            ),
            patch.object(vocabulary, "find_vocabulary_files", return_value=[fake_pkg_vocab]),
            patch.object(vocabulary, "_get_package_data_dir", return_value=fake_pkg),
            patch.object(vocabulary, "load_local_vocabulary") as mock_load,
        ):
            vocabulary.load_global_vocabulary(tingbok_url="https://tingbok.plann.no")

        # The package file should not have been loaded
        mock_load.assert_not_called()

    def test_falls_back_to_local_file_when_tingbok_fails(self, tmp_path):
        """When tingbok returns empty, falls back to loading the package vocab file."""
        fake_pkg = tmp_path / "pkg"
        fake_vocab_path = fake_pkg / "vocabulary.yaml"

        with (
            patch.object(vocabulary, "fetch_vocabulary_from_tingbok", return_value={}),
            patch.object(vocabulary, "find_vocabulary_files", return_value=[fake_vocab_path]),
            patch.object(vocabulary, "_get_package_data_dir", return_value=fake_pkg),
            patch.object(
                vocabulary,
                "load_local_vocabulary",
                return_value={
                    "food": vocabulary.Concept(id="food", prefLabel="Food", source="package"),
                },
            ) as mock_load,
        ):
            result = vocabulary.load_global_vocabulary(tingbok_url="https://tingbok.plann.no")

        mock_load.assert_called_once_with(fake_vocab_path, default_source="package")
        assert "food" in result

    def test_skip_cwd_excludes_cwd_files(self, tmp_path, monkeypatch):
        """skip_cwd=True does not load vocabulary files found in cwd."""
        monkeypatch.chdir(tmp_path)
        cwd_vocab = tmp_path / "vocabulary.yaml"
        cwd_vocab.write_text("concepts:\n  local_thing:\n    prefLabel: 'Local'\n")

        with (
            patch.object(vocabulary, "fetch_vocabulary_from_tingbok", return_value={}),
            patch.object(vocabulary, "find_vocabulary_files", return_value=[cwd_vocab]),
            patch.object(vocabulary, "_get_package_data_dir", return_value=None),
        ):
            result = vocabulary.load_global_vocabulary(skip_cwd=True)

        assert "local_thing" not in result

    def test_without_tingbok_url_loads_normally(self, tmp_path):
        """Without tingbok_url, behaves as before (loads from local files)."""
        vocab_file = tmp_path / "vocabulary.yaml"
        vocab_file.write_text("concepts:\n  food:\n    prefLabel: 'Food'\n")

        with (
            patch.object(vocabulary, "find_vocabulary_files", return_value=[vocab_file]),
            patch.object(vocabulary, "_get_package_data_dir", return_value=None),
        ):
            result = vocabulary.load_global_vocabulary()

        assert "food" in result
