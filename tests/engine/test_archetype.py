# 用途：測試 classify_archetype(把四軸座標分類到最接近的球場定位原型)的
# 最近鄰計算邏輯與邊界情況,以及 classify_archetype_by_majority(改用比對到
# 的前 N 位球員自己的原型多數決,取代直接拿使用者座標比對原型錨點)。
# 可手動調整的變數：無——這支檔案裡的座標資料都是為了驗證公式而設計的
# 測試案例,不是要調的參數。

import unittest

from engine.archetype import classify_archetype, classify_archetype_by_majority


class ClassifyArchetypeTest(unittest.TestCase):
    def test_returns_the_exact_match(self):
        archetypes = [
            {"id": "a", "coordinates": {"A": 90, "B": 10, "C": 10, "D": 10}},
            {"id": "b", "coordinates": {"A": 10, "B": 90, "C": 10, "D": 10}},
        ]

        result = classify_archetype({"A": 90, "B": 10, "C": 10, "D": 10}, archetypes)

        self.assertEqual(result["id"], "a")

    def test_returns_the_closer_archetype_when_no_exact_match(self):
        archetypes = [
            {"id": "a", "coordinates": {"A": 90, "B": 10, "C": 10, "D": 10}},
            {"id": "b", "coordinates": {"A": 10, "B": 90, "C": 10, "D": 10}},
        ]

        result = classify_archetype({"A": 80, "B": 15, "C": 12, "D": 8}, archetypes)

        self.assertEqual(result["id"], "a")

    def test_other_fields_pass_through_on_the_winning_archetype(self):
        archetypes = [
            {"id": "a", "name_zh": "測試原型", "flavor": "一句話文案", "coordinates": {"A": 50, "B": 50, "C": 50, "D": 50}},
        ]

        result = classify_archetype({"A": 50, "B": 50, "C": 50, "D": 50}, archetypes)

        self.assertEqual(result["name_zh"], "測試原型")
        self.assertEqual(result["flavor"], "一句話文案")

    def test_raises_when_archetypes_is_empty(self):
        with self.assertRaises(ValueError):
            classify_archetype({"A": 50, "B": 50, "C": 50, "D": 50}, [])


class ClassifyArchetypeByMajorityTest(unittest.TestCase):
    def setUp(self):
        self.archetypes = [
            {"id": "a", "name_zh": "原型A", "flavor": "文案A", "coordinates": {"A": 90, "B": 10, "C": 10, "D": 10}},
            {"id": "b", "name_zh": "原型B", "flavor": "文案B", "coordinates": {"A": 10, "B": 90, "C": 10, "D": 10}},
        ]

    def test_returns_the_archetype_shared_by_most_of_the_top_n_players(self):
        ranked_players = [
            {"coordinates": {"A": 88, "B": 12, "C": 10, "D": 10}},  # -> a
            {"coordinates": {"A": 12, "B": 88, "C": 10, "D": 10}},  # -> b
            {"coordinates": {"A": 85, "B": 15, "C": 10, "D": 10}},  # -> a
            {"coordinates": {"A": 15, "B": 85, "C": 10, "D": 10}},  # -> b
            {"coordinates": {"A": 92, "B": 8, "C": 10, "D": 10}},   # -> a
        ]

        result = classify_archetype_by_majority(ranked_players, self.archetypes, top_n=5)

        self.assertEqual(result["id"], "a")

    def test_ties_are_broken_by_the_closest_players_archetype(self):
        # 2-2 tie between "a" and "b"; the #1 (closest / first in the
        # already-ranked list) player belongs to "b", so "b" wins the tie.
        ranked_players = [
            {"coordinates": {"A": 12, "B": 88, "C": 10, "D": 10}},  # -> b, rank 1
            {"coordinates": {"A": 88, "B": 12, "C": 10, "D": 10}},  # -> a
            {"coordinates": {"A": 15, "B": 85, "C": 10, "D": 10}},  # -> b
            {"coordinates": {"A": 85, "B": 15, "C": 10, "D": 10}},  # -> a
        ]

        result = classify_archetype_by_majority(ranked_players, self.archetypes, top_n=4)

        self.assertEqual(result["id"], "b")

    def test_only_considers_the_top_n_players_not_the_full_list(self):
        ranked_players = [
            {"coordinates": {"A": 88, "B": 12, "C": 10, "D": 10}},  # -> a
            {"coordinates": {"A": 85, "B": 15, "C": 10, "D": 10}},  # -> a
            {"coordinates": {"A": 92, "B": 8, "C": 10, "D": 10}},   # -> a
            {"coordinates": {"A": 12, "B": 88, "C": 10, "D": 10}},  # -> b, excluded by top_n=3
        ]

        result = classify_archetype_by_majority(ranked_players, self.archetypes, top_n=3)

        self.assertEqual(result["id"], "a")

    def test_works_with_fewer_players_than_top_n(self):
        ranked_players = [
            {"coordinates": {"A": 88, "B": 12, "C": 10, "D": 10}},
        ]

        result = classify_archetype_by_majority(ranked_players, self.archetypes, top_n=5)

        self.assertEqual(result["id"], "a")

    def test_raises_when_ranked_players_is_empty(self):
        with self.assertRaises(ValueError):
            classify_archetype_by_majority([], self.archetypes, top_n=5)

    def test_default_top_n_is_five(self):
        ranked_players = (
            [{"coordinates": {"A": 88, "B": 12, "C": 10, "D": 10}}] * 3
            + [{"coordinates": {"A": 12, "B": 88, "C": 10, "D": 10}}] * 2
            + [{"coordinates": {"A": 12, "B": 88, "C": 10, "D": 10}}] * 10
        )

        result = classify_archetype_by_majority(ranked_players, self.archetypes)

        self.assertEqual(result["id"], "a")


if __name__ == "__main__":
    unittest.main()
