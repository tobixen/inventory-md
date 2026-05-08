"""Tests for find_expiring_items script."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "scripts" / "find_expiring_items.py"

MINIMAL_VOCABULARY = {
    "concepts": {
        "food": {"id": "food", "prefLabel": "Food", "broader": [], "narrower": ["food/oilseeds"]},
        "food/oilseeds": {
            "id": "food/oilseeds",
            "prefLabel": "Oilseeds",
            "broader": ["food"],
            "narrower": ["food/oilseeds/sesame_seed"],
        },
        "food/oilseeds/sesame_seed": {
            "id": "food/oilseeds/sesame_seed",
            "prefLabel": "Sesame seed",
            "broader": ["food/oilseeds"],
            "narrower": [],
        },
        # 'fender' is intentionally absent from food hierarchy
        "fender": {"id": "fender", "prefLabel": "Fender", "broader": [], "narrower": []},
    }
}

# bb dates use the new normalized format: full YYYY-MM-DD, bb_inferred:true for EST
MINIMAL_INVENTORY = {
    "containers": [
        {
            "id": "pantry",
            "parent": "",
            "items": [
                {
                    "id": "sesame-greek",
                    "name": "Sesame seeds",
                    "metadata": {"id": "sesame-greek", "bb": "2020-01-31", "categories": ["sesame_seed"]},
                },
                {
                    "id": "sesame-inferred",
                    "name": "Sesame seeds (estimated expiry)",
                    "metadata": {
                        "id": "sesame-inferred",
                        "bb": "2020-06-30",
                        "bb_inferred": True,
                        "categories": ["sesame_seed"],
                    },
                },
                {
                    "id": "fender-old",
                    "name": "Old fender",
                    "metadata": {"id": "fender-old", "bb": "2019-06-30", "categories": ["fender"]},
                },
                {
                    "id": "no-date-item",
                    "name": "Item without expiry",
                    "metadata": {"id": "no-date-item", "categories": ["sesame_seed"]},
                },
            ],
        }
    ]
}


@pytest.fixture
def inventory_dir(tmp_path):
    (tmp_path / "inventory.json").write_text(json.dumps(MINIMAL_INVENTORY))
    (tmp_path / "vocabulary.json").write_text(json.dumps(MINIMAL_VOCABULARY))
    return tmp_path


def run_script(inventory_dir, *args):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(inventory_dir / "inventory.json"), *args],
        capture_output=True,
        text=True,
    )
    return result


class TestDefaultBehavior:
    """Default: show all expired items regardless of category."""

    def test_shows_expired_non_food(self, inventory_dir):
        result = run_script(inventory_dir)
        assert result.returncode == 0
        assert "fender-old" in result.stdout

    def test_shows_expired_food(self, inventory_dir):
        result = run_script(inventory_dir)
        assert result.returncode == 0
        assert "sesame-greek" in result.stdout

    def test_excludes_items_without_bb_date(self, inventory_dir):
        result = run_script(inventory_dir, "--all")
        assert result.returncode == 0
        assert "no-date-item" not in result.stdout

    def test_inferred_date_marked(self, inventory_dir):
        result = run_script(inventory_dir)
        assert result.returncode == 0
        assert "sesame-inferred" in result.stdout
        # Inferred dates should be visually flagged
        lines = result.stdout.splitlines()
        inferred_section = "\n".join(
            line for i, ln in enumerate(lines) if "sesame-inferred" in ln for line in lines[i : i + 5]
        )
        assert "EST" in inferred_section or "~" in inferred_section or "inferred" in inferred_section.lower()


class TestFoodFlag:
    """--food: only show food items."""

    def test_shows_food_items(self, inventory_dir):
        result = run_script(inventory_dir, "--food")
        assert result.returncode == 0
        assert "sesame-greek" in result.stdout

    def test_excludes_non_food_items(self, inventory_dir):
        result = run_script(inventory_dir, "--food")
        assert result.returncode == 0, result.stderr
        assert "fender-old" not in result.stdout
        # Verify something was actually output (not trivially empty)
        assert "sesame-greek" in result.stdout


class TestAllFlag:
    """--all: show all items with expiry dates, not just expired ones."""

    def test_shows_non_expired_items(self, inventory_dir):
        inv = json.loads((inventory_dir / "inventory.json").read_text())
        inv["containers"][0]["items"].append(
            {
                "id": "future-item",
                "name": "Future item",
                "metadata": {"id": "future-item", "bb": "2099-01-31", "categories": ["sesame_seed"]},
            }
        )
        (inventory_dir / "inventory.json").write_text(json.dumps(inv))

        result = run_script(inventory_dir, "--all")
        assert result.returncode == 0
        assert "future-item" in result.stdout

    def test_default_excludes_non_expired(self, inventory_dir):
        inv = json.loads((inventory_dir / "inventory.json").read_text())
        inv["containers"][0]["items"].append(
            {
                "id": "future-item",
                "name": "Future item",
                "metadata": {"id": "future-item", "bb": "2099-01-31", "categories": ["sesame_seed"]},
            }
        )
        (inventory_dir / "inventory.json").write_text(json.dumps(inv))

        result = run_script(inventory_dir)
        assert result.returncode == 0
        assert "future-item" not in result.stdout


class TestFoodFlagFlatConceptIds:
    """--food must work when concept IDs are not prefixed with 'food/'."""

    VOCAB = {
        "concepts": {
            "food": {"id": "food", "broader": [], "narrower": ["food/vegetables", "food/staples"]},
            "food/vegetables": {"id": "food/vegetables", "broader": ["food"], "narrower": ["potatoes"]},
            "food/staples": {"id": "food/staples", "broader": ["food"], "narrower": ["potatoes"]},
            "potatoes": {"id": "potatoes", "broader": ["food/vegetables", "food/staples"], "narrower": []},
            "fender": {"id": "fender", "broader": [], "narrower": []},
        }
    }

    def test_flat_food_concept_shown(self, tmp_path):
        """'potatoes' (broader: food/vegetables) must appear with --food even though
        its concept ID does not start with 'food/'."""
        inv = {
            "containers": [
                {
                    "id": "p",
                    "parent": "",
                    "items": [
                        {
                            "id": "pot1",
                            "name": "Potatoes",
                            "metadata": {"bb": "2020-01-31", "categories": ["potatoes"]},
                        }
                    ],
                }
            ]
        }
        (tmp_path / "vocabulary.json").write_text(json.dumps(self.VOCAB))
        (tmp_path / "inventory.json").write_text(json.dumps(inv))
        result = run_script(tmp_path, "--food")
        assert result.returncode == 0
        assert "pot1" in result.stdout

    def test_multi_parent_food_concept_shown(self, tmp_path):
        """'potatoes' with two food parents (food/vegetables AND food/staples) is shown."""
        inv = {
            "containers": [
                {
                    "id": "p",
                    "parent": "",
                    "items": [
                        {
                            "id": "pot1",
                            "name": "Potatoes",
                            "metadata": {"bb": "2020-01-31", "categories": ["potatoes"]},
                        }
                    ],
                }
            ]
        }
        (tmp_path / "vocabulary.json").write_text(json.dumps(self.VOCAB))
        (tmp_path / "inventory.json").write_text(json.dumps(inv))
        result = run_script(tmp_path, "--food")
        assert result.returncode == 0
        assert "pot1" in result.stdout

    def test_non_food_excluded(self, tmp_path):
        """'fender' (no food ancestor) must be excluded with --food."""
        inv = {
            "containers": [
                {
                    "id": "p",
                    "parent": "",
                    "items": [
                        {
                            "id": "fen1",
                            "name": "Old fender",
                            "metadata": {"bb": "2020-01-31", "categories": ["fender"]},
                        }
                    ],
                }
            ]
        }
        (tmp_path / "vocabulary.json").write_text(json.dumps(self.VOCAB))
        (tmp_path / "inventory.json").write_text(json.dumps(inv))
        result = run_script(tmp_path, "--food")
        assert result.returncode == 0
        assert "fen1" not in result.stdout
