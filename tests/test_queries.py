"""Tests for the inventory query helpers (queries module).

These cover the logic consolidated from scripts/find_expiring_items.py and
scripts/lookup_items.py into the inventory_md package.
"""

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from inventory_md import queries, vocabulary

# Hierarchy where 'soy-beans' is reachable from 'food' via broader links.
# This is the TODO case: the old find-expired script could not tell that
# soybeans are food.
FOOD_VOCAB = {
    "concepts": {
        "food": {"id": "food", "prefLabel": "Food", "broader": [], "narrower": ["food/legumes"]},
        "food/legumes": {
            "id": "food/legumes",
            "prefLabel": "Legumes",
            "broader": ["food"],
            "narrower": ["food/legumes/soy-beans"],
        },
        "food/legumes/soy-beans": {
            "id": "food/legumes/soy-beans",
            "prefLabel": "Soy beans",
            "broader": ["food/legumes"],
            "narrower": [],
        },
        "fender": {"id": "fender", "prefLabel": "Fender", "broader": [], "narrower": []},
    }
}


def _iso(days_from_today: int) -> str:
    return (date.today() + timedelta(days=days_from_today)).isoformat()


@pytest.fixture
def inventory_dir(tmp_path: Path) -> Path:
    inv = {
        "containers": [
            {
                "id": "pantry",
                "parent": "kitchen",
                "items": [
                    {
                        "id": "soy-old",
                        "name": "Soy beans",
                        "metadata": {"id": "soy-old", "bb": _iso(-100), "categories": ["soy-beans"]},
                    },
                    {
                        "id": "soy-soon",
                        "name": "Soy beans fresh",
                        "metadata": {
                            "id": "soy-soon",
                            "bb": _iso(10),
                            "bb_inferred": True,
                            "categories": ["soy-beans"],
                        },
                    },
                    {
                        "id": "fender-old",
                        "name": "Old fender",
                        "metadata": {"id": "fender-old", "bb": _iso(-50), "categories": ["fender"]},
                    },
                    {
                        "id": "fresh-onion",
                        "name": "Onion",
                        "metadata": {"id": "fresh-onion", "categories": ["soy-beans"]},
                    },
                ],
            }
        ]
    }
    (tmp_path / "inventory.json").write_text(json.dumps(inv))
    (tmp_path / "vocabulary.json").write_text(json.dumps(FOOD_VOCAB))
    return tmp_path


class TestIterItems:
    def test_yields_location_with_parent(self, inventory_dir: Path):
        data = json.loads((inventory_dir / "inventory.json").read_text())
        rows = list(queries.iter_items(data))
        assert len(rows) == 4
        item, container_id, parent_id, location = rows[0]
        assert container_id == "pantry"
        assert parent_id == "kitchen"
        assert location == "pantry, kitchen"

    def test_location_without_parent(self, tmp_path: Path):
        data = {"containers": [{"id": "box", "parent": "", "items": [{"id": "x"}]}]}
        (_item, container_id, parent_id, location) = next(queries.iter_items(data))
        assert location == "box"
        assert parent_id == ""


class TestNormalizeBB:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("2024-01-15", "2024-01-15"),
            ("2024-01", "2024-01-31"),
            ("2024-02", "2024-02-29"),  # leap year
            ("2024", "2024-12-31"),
            ("2024-01-15:EST", "2024-01-15"),
            ("2024:EST", "2024-12-31"),
        ],
    )
    def test_normalize(self, raw: str, expected: str):
        assert queries.normalize_bb(raw) == expected

    def test_malformed_returns_none(self):
        assert queries.normalize_bb("not-a-date") is None
        assert queries.normalize_bb("") is None
        assert queries.normalize_bb(None) is None


class TestFindExpiringItems:
    def test_sorted_oldest_first(self, inventory_dir: Path):
        items = queries.find_expiring_items(inventory_dir / "inventory.json")
        # soy-old (-100) before fender-old (-50) before soy-soon (+10)
        ids = [i["id"] for i in items]
        assert ids == ["soy-old", "fender-old", "soy-soon"]

    def test_skips_items_without_bb(self, inventory_dir: Path):
        items = queries.find_expiring_items(inventory_dir / "inventory.json")
        assert "fresh-onion" not in [i["id"] for i in items]

    def test_expired_and_inferred_flags(self, inventory_dir: Path):
        items = {i["id"]: i for i in queries.find_expiring_items(inventory_dir / "inventory.json")}
        assert items["soy-old"]["expired"] is True
        assert items["soy-soon"]["expired"] is False
        assert items["soy-soon"]["inferred"] is True
        assert items["soy-old"]["inferred"] is False
        assert items["soy-old"]["location"] == "pantry, kitchen"

    def test_food_only_uses_vocabulary_hierarchy(self, inventory_dir: Path):
        """soy-beans must be recognised as food via the food/legumes/soy-beans path."""
        items = queries.find_expiring_items(inventory_dir / "inventory.json", food_only=True)
        ids = [i["id"] for i in items]
        assert "soy-old" in ids
        assert "soy-soon" in ids
        assert "fender-old" not in ids

    def test_malformed_bb_skipped(self, tmp_path: Path):
        inv = {"containers": [{"id": "b", "parent": "", "items": [{"id": "bad", "metadata": {"bb": "13-13-13"}}]}]}
        (tmp_path / "inventory.json").write_text(json.dumps(inv))
        items = queries.find_expiring_items(tmp_path / "inventory.json")
        assert items == []


class TestLookupItems:
    def test_lookup_by_id(self, inventory_dir: Path):
        results = queries.lookup_items(inventory_dir / "inventory.json", ids=["soy-old"], matches=[])
        assert len(results) == 1
        assert results[0]["id"] == "soy-old"
        assert results[0]["location"] == "pantry, kitchen"

    def test_lookup_by_match_includes_items_without_bb(self, inventory_dir: Path):
        results = queries.lookup_items(inventory_dir / "inventory.json", ids=[], matches=["onion"])
        assert [r["id"] for r in results] == ["fresh-onion"]
        assert results[0]["bb"] is None

    def test_match_is_case_insensitive_on_id_and_name(self, inventory_dir: Path):
        results = queries.lookup_items(inventory_dir / "inventory.json", ids=[], matches=["SOY"])
        ids = {r["id"] for r in results}
        assert ids == {"soy-old", "soy-soon"}


@pytest.fixture
def nested_inventory(tmp_path: Path) -> Path:
    inv = {
        "containers": [
            {
                "id": "pantry",
                "parent": "kitchen",
                "items": [{"id": "rice", "name": "Rice", "metadata": {"bb": _iso(100)}}],
            },
            {
                "id": "pantry-fridge",
                "parent": "pantry",
                "items": [{"id": "milk", "name": "Milk", "metadata": {"bb": _iso(5)}}],
            },
            {
                "id": "garage",
                "parent": "",
                "items": [{"id": "oil", "name": "Oil", "metadata": {}}],
            },
        ]
    }
    path = tmp_path / "inventory.json"
    path.write_text(json.dumps(inv))
    return path


class TestContainerItems:
    def test_lists_items_in_named_container(self, nested_inventory: Path):
        results = queries.container_items(nested_inventory, "pantry", include_children=False)
        assert {r["id"] for r in results} == {"rice"}

    def test_includes_direct_children_by_default(self, nested_inventory: Path):
        results = queries.container_items(nested_inventory, "pantry")
        # milk lives in pantry-fridge, whose parent is pantry
        assert {r["id"] for r in results} == {"rice", "milk"}

    def test_unknown_container_is_empty(self, nested_inventory: Path):
        assert queries.container_items(nested_inventory, "nope") == []

    def test_result_fields(self, nested_inventory: Path):
        rice = next(r for r in queries.container_items(nested_inventory, "pantry") if r["id"] == "rice")
        assert rice["name"] == "Rice"
        assert rice["container"] == "pantry"
        assert rice["location"] == "pantry, kitchen"
        assert rice["bb"]


class TestContainerCommand:
    def test_unknown_container_returns_1(self, nested_inventory: Path):
        assert queries.container_command(nested_inventory, "nope") == 1

    def test_known_container_returns_0_and_lists_items(self, nested_inventory: Path, capsys):
        rc = queries.container_command(nested_inventory, "pantry")
        out = capsys.readouterr().out
        assert rc == 0
        assert "rice" in out
        assert "milk" in out  # direct child included


class TestBBStatus:
    def test_no_bb(self):
        assert queries.bb_status(None) == "no bb"

    def test_expired(self):
        assert "EXPIRED" in queries.bb_status(_iso(-5))

    def test_soon(self):
        assert "left" in queries.bb_status(_iso(10))

    def test_malformed(self):
        assert "malformed" in queries.bb_status("nope")


class TestIsDescendantOf:
    def test_self_is_descendant(self):
        concepts = {cid: vocabulary.Concept.from_dict(c) for cid, c in FOOD_VOCAB["concepts"].items()}
        assert vocabulary.is_descendant_of("food", "food", concepts)

    def test_transitive_descendant(self):
        concepts = {cid: vocabulary.Concept.from_dict(c) for cid, c in FOOD_VOCAB["concepts"].items()}
        assert vocabulary.is_descendant_of("food/legumes/soy-beans", "food", concepts)

    def test_not_a_descendant(self):
        concepts = {cid: vocabulary.Concept.from_dict(c) for cid, c in FOOD_VOCAB["concepts"].items()}
        assert not vocabulary.is_descendant_of("fender", "food", concepts)
