# 用途：測試 rank_similar_players(最近鄰配對)、fit_stars_for_distance(貼合度
# 星級門檻)、skill_dominant_axis(技能的主導相關軸)、matching_skill_id(差異軸
# 是否剛好對到某個技能的主導軸)這四個函數的計算邏輯與邊界情況。
# 可手動調整的變數：無——這支檔案裡的座標/技能數字都是為了驗證公式而設計的
# 測試案例,不是要調的參數。

import unittest

from engine.player_matching import (
    fit_stars_for_distance,
    matching_skill_id,
    rank_similar_players,
    skill_dominant_axis,
)


class RankSimilarPlayersTest(unittest.TestCase):
    def test_computes_distance_and_signed_diff_correctly(self):
        user = {"A": 50, "B": 50, "C": 50, "D": 50}
        players = [
            {"id": "p1", "name": "P1", "coordinates": {"A": 60, "B": 40, "C": 50, "D": 50}},
        ]

        ranked = rank_similar_players(user, players, k=10)

        self.assertEqual(len(ranked), 1)
        result = ranked[0]
        self.assertEqual(result["diff"], {"A": 10, "B": -10, "C": 0, "D": 0})
        self.assertAlmostEqual(result["distance"], 200 ** 0.5)
        self.assertEqual(result["dominant_diff_axis"], "A")
        self.assertEqual(result["fit_stars"], 5)
        # original player fields pass through untouched
        self.assertEqual(result["id"], "p1")
        self.assertEqual(result["name"], "P1")

    def test_sorts_ascending_by_distance_and_truncates_to_k(self):
        user = {"A": 0, "B": 0, "C": 0, "D": 0}
        players = [
            {"id": "far", "name": "Far", "coordinates": {"A": 90, "B": 0, "C": 0, "D": 0}},
            {"id": "near", "name": "Near", "coordinates": {"A": 10, "B": 0, "C": 0, "D": 0}},
            {"id": "mid", "name": "Mid", "coordinates": {"A": 50, "B": 0, "C": 0, "D": 0}},
        ]

        ranked = rank_similar_players(user, players, k=2)

        self.assertEqual([p["id"] for p in ranked], ["near", "mid"])

    def test_returns_all_players_when_fewer_than_k(self):
        user = {"A": 0, "B": 0, "C": 0, "D": 0}
        players = [
            {"id": "only1", "name": "Only1", "coordinates": {"A": 10, "B": 0, "C": 0, "D": 0}},
            {"id": "only2", "name": "Only2", "coordinates": {"A": 20, "B": 0, "C": 0, "D": 0}},
        ]

        ranked = rank_similar_players(user, players, k=10)

        self.assertEqual(len(ranked), 2)

    def test_dominant_diff_axis_when_user_leads_on_every_axis(self):
        # Known edge case (design doc §3.3): when the user out-scores the
        # player on every axis, all diffs are negative. argmax still returns
        # the *least negative* axis -- not a real "direction to grow toward".
        # This test documents that behavior explicitly rather than hiding it.
        user = {"A": 90, "B": 90, "C": 90, "D": 90}
        players = [
            {"id": "weaker", "name": "Weaker", "coordinates": {"A": 10, "B": 20, "C": 30, "D": 40}},
        ]

        ranked = rank_similar_players(user, players, k=10)

        self.assertEqual(ranked[0]["dominant_diff_axis"], "D")
        self.assertEqual(ranked[0]["diff"]["D"], -50)


class FitStarsForDistanceTest(unittest.TestCase):
    def test_boundary_values(self):
        self.assertEqual(fit_stars_for_distance(20), 5)
        self.assertEqual(fit_stars_for_distance(21), 4)
        self.assertEqual(fit_stars_for_distance(40), 4)
        self.assertEqual(fit_stars_for_distance(41), 3)
        self.assertEqual(fit_stars_for_distance(60), 3)
        self.assertEqual(fit_stars_for_distance(61), 2)
        self.assertEqual(fit_stars_for_distance(80), 2)
        self.assertEqual(fit_stars_for_distance(81), 1)


class SkillDominantAxisTest(unittest.TestCase):
    def test_returns_the_axis_with_highest_relevance(self):
        self.assertEqual(
            skill_dominant_axis({"A": 0.1, "B": 0.9, "C": 0.1, "D": 0.2}), "B"
        )


class MatchingSkillIdTest(unittest.TestCase):
    def setUp(self):
        self.skills_by_id = {
            "perimeter_shooting": {"axis_relevance": {"A": 0.3, "B": 0.9, "C": 0.1, "D": 0.2}},
            "rim_protection": {"axis_relevance": {"A": 0.1, "B": 0.1, "C": 0.9, "D": 0.6}},
        }

    def test_returns_skill_id_when_its_dominant_axis_matches(self):
        result = matching_skill_id("B", "perimeter_shooting", self.skills_by_id)
        self.assertEqual(result, "perimeter_shooting")

    def test_returns_none_when_dominant_axis_does_not_match(self):
        result = matching_skill_id("D", "perimeter_shooting", self.skills_by_id)
        self.assertIsNone(result)

    def test_returns_none_when_no_signature_skill(self):
        result = matching_skill_id("B", None, self.skills_by_id)
        self.assertIsNone(result)

    def test_returns_none_when_signature_skill_not_in_skills_by_id(self):
        result = matching_skill_id("B", "does_not_exist", self.skills_by_id)
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
