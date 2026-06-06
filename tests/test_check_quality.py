"""Tests for check_quality food best-before enforcement."""

import sys

sys.path.insert(0, str(__file__).rsplit("/tests/", 1)[0] + "/scripts")
from check_quality import _category_is_food, _is_food_concept, check_food_without_bb  # noqa: E402


class TestCategoryIsFood:
    @staticmethod
    def _resolve(leaf):
        return {
            "rice": {"id": "rice", "broader": ["food/grains"]},
            "nuts": {"id": "nuts", "broader": ["food/nuts"]},
        }.get(leaf)

    def test_explicit_food_path(self):
        assert _category_is_food("food/spices", self._resolve)

    def test_explicit_hardware_path_not_food(self):
        # leaf 'nuts' resolves to food, but explicit hardware/ root wins
        assert not _category_is_food("hardware/nuts", self._resolve)

    def test_bare_leaf_resolved(self):
        assert _category_is_food("rice", self._resolve)

    def test_bare_unknown_leaf_not_food(self):
        assert not _category_is_food("widget", self._resolve)


class TestIsFoodConcept:
    def test_id_under_food(self):
        assert _is_food_concept({"id": "food/processed_animal_products/cured_meat"})

    def test_broader_under_food(self):
        assert _is_food_concept({"id": "chickpeas", "broader": ["food/legumes"]})

    def test_non_food(self):
        assert not _is_food_concept({"id": "dishwasher_detergent", "broader": ["product/chemical_product/detergent"]})

    def test_no_broader(self):
        assert not _is_food_concept({"id": "epoxy", "broader": []})

    def test_none(self):
        assert not _is_food_concept(None)


# A simple classifier standing in for the tingbok-backed one.
_FOOD = {"rice", "chickpeas", "lentils", "cured-meat", "tomatoes"}


def _is_food(cat: str) -> bool:
    return cat in _FOOD


def _inv(items):
    return {"containers": [{"id": "c1", "items": items}]}


class TestCheckFoodWithoutBB:
    def test_food_without_bb_flagged(self):
        data = _inv(
            [
                {"id": "rice-x", "metadata": {"categories": ["rice"]}},  # no bb
            ]
        )
        issues = check_food_without_bb(data, _is_food)
        assert issues
        assert "1 items" in issues[0]
        assert "rice-x" in issues[0]

    def test_food_with_bb_ok(self):
        data = _inv(
            [
                {"id": "rice-x", "metadata": {"categories": ["rice"], "bb": "2027-01-05"}},
            ]
        )
        assert check_food_without_bb(data, _is_food) == []

    def test_non_food_without_bb_ignored(self):
        data = _inv(
            [
                {"id": "detergent-x", "metadata": {"categories": ["dishwasher-detergent"]}},
                {"id": "epoxy-x", "metadata": {"categories": ["epoxy"]}},
            ]
        )
        assert check_food_without_bb(data, _is_food) == []

    def test_mixed_counts_only_food(self):
        data = _inv(
            [
                {"id": "rice-x", "metadata": {"categories": ["rice"]}},  # food, no bb -> flag
                {"id": "lentils-x", "metadata": {"categories": ["lentils"]}},  # food, no bb -> flag
                {"id": "soap", "metadata": {"categories": ["dishwasher-detergent"]}},  # not food
                {"id": "milk", "metadata": {"categories": ["rice"], "bb": "2026-07"}},  # has bb
            ]
        )
        issues = check_food_without_bb(data, _is_food)
        assert "2 items" in issues[0]
