# 用途：測試 classify_archetype(把六軸座標分類到最接近的球場定位原型)的
# 最近鄰計算邏輯與邊界情況,以及 classify_archetype_by_majority(改用比對到
# 的前 N 位球員自己的原型多數決,取代直接拿使用者座標比對原型錨點)。
# 可手動調整的變數：無——這支檔案裡的座標資料都是為了驗證公式而設計的
# 測試案例,不是要調的參數。

import unittest

from engine.archetype import classify_archetype, classify_archetype_by_majority


class ClassifyArchetypeTest(unittest.TestCase):
    def test_returns_the_exact_match(self):
        archetypes = [
            {"id": "a", "coordinates": {"A": 90, "B1": 10, "B2": 0, "C1": 10, "C2": 0, "D": 10}},
            {"id": "b", "coordinates": {"A": 10, "B1": 90, "B2": 0, "C1": 10, "C2": 0, "D": 10}},
        ]

        result = classify_archetype({"A": 90, "B1": 10, "B2": 0, "C1": 10, "C2": 0, "D": 10}, archetypes)

        self.assertEqual(result["id"], "a")

    def test_returns_the_closer_archetype_when_no_exact_match(self):
        archetypes = [
            {"id": "a", "coordinates": {"A": 90, "B1": 10, "B2": 0, "C1": 10, "C2": 0, "D": 10}},
            {"id": "b", "coordinates": {"A": 10, "B1": 90, "B2": 0, "C1": 10, "C2": 0, "D": 10}},
        ]

        result = classify_archetype({"A": 80, "B1": 15, "B2": 0, "C1": 12, "C2": 0, "D": 8}, archetypes)

        self.assertEqual(result["id"], "a")

    def test_other_fields_pass_through_on_the_winning_archetype(self):
        archetypes = [
            {"id": "a", "name_zh": "測試原型", "flavor": "一句話文案", "coordinates": {"A": 50, "B1": 50, "B2": 0, "C1": 50, "C2": 0, "D": 50}},
        ]

        result = classify_archetype({"A": 50, "B1": 50, "B2": 0, "C1": 50, "C2": 0, "D": 50}, archetypes)

        self.assertEqual(result["name_zh"], "測試原型")
        self.assertEqual(result["flavor"], "一句話文案")

    def test_raises_when_archetypes_is_empty(self):
        with self.assertRaises(ValueError):
            classify_archetype({"A": 50, "B1": 50, "B2": 0, "C1": 50, "C2": 0, "D": 50}, [])

    def test_size_breaks_a_style_tie_toward_the_closer_size_anchor(self):
        # both archetypes are equidistant on A/B/C/D alone (dead center);
        # only the size anchor differs, so size must be the deciding factor.
        archetypes = [
            {"id": "small", "coordinates": {"A": 50, "B1": 50, "B2": 0, "C1": 50, "C2": 0, "D": 50}, "size": 20},
            {"id": "big", "coordinates": {"A": 50, "B1": 50, "B2": 0, "C1": 50, "C2": 0, "D": 50}, "size": 80},
        ]

        result = classify_archetype({"A": 50, "B1": 50, "B2": 0, "C1": 50, "C2": 0, "D": 50}, archetypes, size=15)

        self.assertEqual(result["id"], "small")

    def test_size_is_ignored_when_archetype_has_no_size_field(self):
        archetypes = [
            {"id": "a", "coordinates": {"A": 90, "B1": 10, "B2": 0, "C1": 10, "C2": 0, "D": 10}},
            {"id": "b", "coordinates": {"A": 10, "B1": 90, "B2": 0, "C1": 10, "C2": 0, "D": 10}},
        ]

        # size=1 would favor "b" if it had a size anchor near 1, but neither
        # archetype has one, so the result must match the style-only result.
        result = classify_archetype({"A": 88, "B1": 12, "B2": 0, "C1": 10, "C2": 0, "D": 10}, archetypes, size=1)

        self.assertEqual(result["id"], "a")


class ClassifyArchetypeByMajorityTest(unittest.TestCase):
    def setUp(self):
        self.archetypes = [
            {"id": "a", "name_zh": "原型A", "flavor": "文案A", "coordinates": {"A": 90, "B1": 10, "B2": 0, "C1": 10, "C2": 0, "D": 10}},
            {"id": "b", "name_zh": "原型B", "flavor": "文案B", "coordinates": {"A": 10, "B1": 90, "B2": 0, "C1": 10, "C2": 0, "D": 10}},
        ]

    def test_returns_the_archetype_shared_by_most_of_the_top_n_players(self):
        ranked_players = [
            {"coordinates": {"A": 88, "B1": 12, "B2": 0, "C1": 10, "C2": 0, "D": 10}},  # -> a
            {"coordinates": {"A": 12, "B1": 88, "B2": 0, "C1": 10, "C2": 0, "D": 10}},  # -> b
            {"coordinates": {"A": 85, "B1": 15, "B2": 0, "C1": 10, "C2": 0, "D": 10}},  # -> a
            {"coordinates": {"A": 15, "B1": 85, "B2": 0, "C1": 10, "C2": 0, "D": 10}},  # -> b
            {"coordinates": {"A": 92, "B1": 8, "B2": 0, "C1": 10, "C2": 0, "D": 10}},   # -> a
        ]

        result = classify_archetype_by_majority(ranked_players, self.archetypes, top_n=5)

        self.assertEqual(result["id"], "a")

    def test_ties_are_broken_by_the_closest_players_archetype(self):
        # a genuine weight tie: rank-1 player alone gives "b" weight 4 (top_n),
        # ranks 2+3 give "a" weight 3+2=5 -- not a tie. Use a split that ties
        # under rank-weighting instead: rank1(b)=3, rank2(a)=2, rank3(a)=1 ->
        # a=3, b=3. The #1 (closest) player belongs to "b", so "b" wins.
        ranked_players = [
            {"coordinates": {"A": 12, "B1": 88, "B2": 0, "C1": 10, "C2": 0, "D": 10}},  # -> b, rank 1, weight 3
            {"coordinates": {"A": 88, "B1": 12, "B2": 0, "C1": 10, "C2": 0, "D": 10}},  # -> a, rank 2, weight 2
            {"coordinates": {"A": 85, "B1": 15, "B2": 0, "C1": 10, "C2": 0, "D": 10}},  # -> a, rank 3, weight 1
        ]

        result = classify_archetype_by_majority(ranked_players, self.archetypes, top_n=3)

        self.assertEqual(result["id"], "b")

    def test_closer_players_outweigh_a_larger_count_of_farther_players(self):
        # the top 2 (closest) players both say "a"; the next 3 (farther)
        # all say "b" -- a plain unweighted vote would give "b" 3 votes to
        # 2, but the closer pair's opinion should count for more (2026-10
        # fix: a plurality among distant neighbors used to outvote a clear
        # agreement among the closest, closer-displayed players).
        ranked_players = [
            {"coordinates": {"A": 88, "B1": 12, "B2": 0, "C1": 10, "C2": 0, "D": 10}},  # -> a, rank 1, weight 5
            {"coordinates": {"A": 85, "B1": 15, "B2": 0, "C1": 10, "C2": 0, "D": 10}},  # -> a, rank 2, weight 4
            {"coordinates": {"A": 12, "B1": 88, "B2": 0, "C1": 10, "C2": 0, "D": 10}},  # -> b, rank 3, weight 3
            {"coordinates": {"A": 15, "B1": 85, "B2": 0, "C1": 10, "C2": 0, "D": 10}},  # -> b, rank 4, weight 2
            {"coordinates": {"A": 18, "B1": 82, "B2": 0, "C1": 10, "C2": 0, "D": 10}},  # -> b, rank 5, weight 1
        ]

        result = classify_archetype_by_majority(ranked_players, self.archetypes, top_n=5)

        self.assertEqual(result["id"], "a")

    def test_uses_player_body_size_when_present(self):
        archetypes = [
            {"id": "a", "coordinates": {"A": 50, "B1": 50, "B2": 0, "C1": 50, "C2": 0, "D": 50}, "size": 20},
            {"id": "b", "coordinates": {"A": 50, "B1": 50, "B2": 0, "C1": 50, "C2": 0, "D": 50}, "size": 80},
        ]
        ranked_players = [
            {"coordinates": {"A": 50, "B1": 50, "B2": 0, "C1": 50, "C2": 0, "D": 50}, "body": {"height_cm": 10, "weight_kg": 10}},
        ]

        result = classify_archetype_by_majority(ranked_players, archetypes, top_n=1)

        self.assertEqual(result["id"], "a")

    def test_falls_back_to_style_only_when_player_has_no_body(self):
        archetypes = [
            {"id": "a", "coordinates": {"A": 90, "B1": 10, "B2": 0, "C1": 10, "C2": 0, "D": 10}, "size": 80},
            {"id": "b", "coordinates": {"A": 10, "B1": 90, "B2": 0, "C1": 10, "C2": 0, "D": 10}, "size": 20},
        ]
        ranked_players = [
            {"coordinates": {"A": 88, "B1": 12, "B2": 0, "C1": 10, "C2": 0, "D": 10}},  # no "body" key at all
        ]

        result = classify_archetype_by_majority(ranked_players, archetypes, top_n=1)

        self.assertEqual(result["id"], "a")

    def test_only_considers_the_top_n_players_not_the_full_list(self):
        ranked_players = [
            {"coordinates": {"A": 88, "B1": 12, "B2": 0, "C1": 10, "C2": 0, "D": 10}},  # -> a
            {"coordinates": {"A": 85, "B1": 15, "B2": 0, "C1": 10, "C2": 0, "D": 10}},  # -> a
            {"coordinates": {"A": 92, "B1": 8, "B2": 0, "C1": 10, "C2": 0, "D": 10}},   # -> a
            {"coordinates": {"A": 12, "B1": 88, "B2": 0, "C1": 10, "C2": 0, "D": 10}},  # -> b, excluded by top_n=3
        ]

        result = classify_archetype_by_majority(ranked_players, self.archetypes, top_n=3)

        self.assertEqual(result["id"], "a")

    def test_works_with_fewer_players_than_top_n(self):
        ranked_players = [
            {"coordinates": {"A": 88, "B1": 12, "B2": 0, "C1": 10, "C2": 0, "D": 10}},
        ]

        result = classify_archetype_by_majority(ranked_players, self.archetypes, top_n=5)

        self.assertEqual(result["id"], "a")

    def test_raises_when_ranked_players_is_empty(self):
        with self.assertRaises(ValueError):
            classify_archetype_by_majority([], self.archetypes, top_n=5)

    def test_default_top_n_is_five(self):
        ranked_players = (
            [{"coordinates": {"A": 88, "B1": 12, "B2": 0, "C1": 10, "C2": 0, "D": 10}}] * 3
            + [{"coordinates": {"A": 12, "B1": 88, "B2": 0, "C1": 10, "C2": 0, "D": 10}}] * 2
            + [{"coordinates": {"A": 12, "B1": 88, "B2": 0, "C1": 10, "C2": 0, "D": 10}}] * 10
        )

        result = classify_archetype_by_majority(ranked_players, self.archetypes)

        self.assertEqual(result["id"], "a")


if __name__ == "__main__":
    unittest.main()
