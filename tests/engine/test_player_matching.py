# 用途：測試 rank_similar_players(最近鄰配對)、fit_stars_for_distance(貼合度
# 星級門檻)、skill_dominant_axis(技能的主導相關軸)、matching_skill_id(差異軸
# 是否剛好對到某個技能的主導軸)這四個函數的計算邏輯與邊界情況。
# 可手動調整的變數：無——這支檔案裡的座標/技能數字都是為了驗證公式而設計的
# 測試案例,不是要調的參數。

import unittest

from engine.player_matching import (
    find_body_fit_template,
    find_ceiling_template,
    find_skill_fit_template,
    fit_stars_for_distance,
    matching_skill_id,
    rank_similar_players,
    rank_similar_players_by_style_and_body,
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


class RankSimilarPlayersByStyleAndBodyTest(unittest.TestCase):
    FIELD_RANGES = {"height_cm": (140, 230)}

    def test_body_distance_can_change_the_ranking_vs_style_alone(self):
        # Style-only ranking would put "close_style_far_body" first (0 style
        # distance beats 40). Once body is folded in, "far_style_close_body"
        # should win instead -- a large body gap should be able to outweigh
        # a moderate style gap, which is the whole point of this function
        # (SPEC change: stop pairing a user with players of a wildly
        # different body type just because their play style matches).
        user_coordinates = {"A": 50, "B": 50, "C": 50, "D": 50}
        user_body = {"height_cm": 188}
        players = [
            {
                "id": "close_style_far_body", "name": "CloseStyleFarBody",
                "coordinates": {"A": 50, "B": 50, "C": 50, "D": 50},
                "body": {"height_cm": 230},
            },
            {
                "id": "far_style_close_body", "name": "FarStyleCloseBody",
                "coordinates": {"A": 90, "B": 50, "C": 50, "D": 50},
                "body": {"height_cm": 190},
            },
        ]

        ranked = rank_similar_players_by_style_and_body(
            user_coordinates, user_body, players, self.FIELD_RANGES, k=10
        )

        self.assertEqual([p["id"] for p in ranked], ["far_style_close_body", "close_style_far_body"])
        # diff/dominant_diff_axis stay style-only (A/B/C/D), since downstream
        # growth-recommendation text is keyed off the style axes, not body.
        self.assertEqual(ranked[0]["diff"], {"A": 40, "B": 0, "C": 0, "D": 0})
        self.assertEqual(ranked[0]["dominant_diff_axis"], "A")

    def test_degrades_to_style_only_distance_when_user_has_no_body_data(self):
        user_coordinates = {"A": 50, "B": 50, "C": 50, "D": 50}
        players = [
            {
                "id": "p1", "name": "P1",
                "coordinates": {"A": 60, "B": 50, "C": 50, "D": 50},
                "body": {"height_cm": 230},
            },
        ]

        ranked = rank_similar_players_by_style_and_body(
            user_coordinates, {}, players, self.FIELD_RANGES, k=10
        )

        self.assertAlmostEqual(ranked[0]["distance"], 10.0)

    def test_sorts_ascending_and_truncates_to_k(self):
        user_coordinates = {"A": 0, "B": 0, "C": 0, "D": 0}
        user_body = {"height_cm": 140}
        players = [
            {
                "id": "far", "name": "Far",
                "coordinates": {"A": 90, "B": 0, "C": 0, "D": 0}, "body": {"height_cm": 140},
            },
            {
                "id": "near", "name": "Near",
                "coordinates": {"A": 10, "B": 0, "C": 0, "D": 0}, "body": {"height_cm": 140},
            },
            {
                "id": "mid", "name": "Mid",
                "coordinates": {"A": 50, "B": 0, "C": 0, "D": 0}, "body": {"height_cm": 140},
            },
        ]

        ranked = rank_similar_players_by_style_and_body(
            user_coordinates, user_body, players, self.FIELD_RANGES, k=2
        )

        self.assertEqual([p["id"] for p in ranked], ["near", "mid"])


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


class FindSkillFitTemplateTest(unittest.TestCase):
    def test_picks_the_closest_on_a_b_c_regardless_of_d(self):
        user = {"A": 50, "B": 50, "C": 50, "D": 50}
        players = [
            {"id": "far_abc_near_d", "name": "Far ABC", "coordinates": {"A": 90, "B": 90, "C": 90, "D": 50}},
            {"id": "near_abc_far_d", "name": "Near ABC", "coordinates": {"A": 52, "B": 48, "C": 51, "D": 5}},
        ]

        result = find_skill_fit_template(user, players)

        self.assertEqual(result["id"], "near_abc_far_d")

    def test_returns_none_when_no_players_given(self):
        user = {"A": 50, "B": 50, "C": 50, "D": 50}

        result = find_skill_fit_template(user, [])

        self.assertIsNone(result)


class FindCeilingTemplateTest(unittest.TestCase):
    # 2026-09-11 redesign: 天花板 used to mean "A/B/C close, D is the
    # dominant gap" -- but that's just someone with different genetics, not
    # an achievable target. It now means the mirror image: a player with
    # roughly the user's own athletic tools (D close) whose game is far
    # more developed (the dominant gap is a skill axis) -- a ceiling you
    # could actually grow into.

    def test_finds_a_skill_dominant_close_d_player(self):
        user = {"A": 50, "B": 50, "C": 50, "D": 50}
        players = [
            {
                "id": "polished_peer", "name": "Polished Peer",
                "coordinates": {"A": 90, "B": 50, "C": 50, "D": 52},
            },
        ]

        result = find_ceiling_template(user, players)

        self.assertEqual(result["id"], "polished_peer")

    def test_excludes_candidates_whose_dominant_gap_is_d(self):
        # This is exactly the OLD ceiling shape -- different athletic
        # tools, not different skill -- so it no longer qualifies.
        user = {"A": 50, "B": 50, "C": 50, "D": 50}
        players = [
            {
                "id": "athletic_outlier", "name": "Athletic Outlier",
                "coordinates": {"A": 52, "B": 48, "C": 51, "D": 95},
            },
        ]

        result = find_ceiling_template(user, players)

        self.assertIsNone(result)

    def test_excludes_candidates_whose_dominant_diff_is_negative(self):
        # Known rank_similar_players edge case: when the user leads on
        # every axis, argmax still returns the *least negative* axis, which
        # can land on A/B/C without representing a real skill lead.
        user = {"A": 50, "B": 50, "C": 50, "D": 50}
        players = [
            {
                "id": "weaker_everywhere", "name": "Weaker Everywhere",
                "coordinates": {"A": 45, "B": 30, "C": 20, "D": 10},
            },
        ]

        result = find_ceiling_template(user, players)

        self.assertIsNone(result)

    def test_returns_none_when_no_candidates(self):
        user = {"A": 50, "B": 50, "C": 50, "D": 50}

        result = find_ceiling_template(user, [])

        self.assertIsNone(result)

    def test_picks_the_closest_on_d_among_multiple_candidates(self):
        user = {"A": 50, "B": 50, "C": 50, "D": 50}
        players = [
            {
                "id": "far_on_d", "name": "Far on D",
                "coordinates": {"A": 90, "B": 50, "C": 50, "D": 90},
            },
            {
                "id": "close_on_d", "name": "Close on D",
                "coordinates": {"A": 90, "B": 50, "C": 50, "D": 52},
            },
        ]

        result = find_ceiling_template(user, players)

        self.assertEqual(result["id"], "close_on_d")


BODY_FIELD_RANGES = {
    "height_cm": (140, 230),
    "wingspan_cm": (140, 250),
}


class FindBodyFitTemplateTest(unittest.TestCase):
    def test_picks_the_closest_player_by_body_distance(self):
        user_body = {"height_cm": 188, "wingspan_cm": 193}
        players = [
            {"id": "far", "name": "Far", "body": {"height_cm": 210, "wingspan_cm": 220}},
            {"id": "near", "name": "Near", "body": {"height_cm": 190, "wingspan_cm": 195}},
        ]

        result = find_body_fit_template(user_body, players, BODY_FIELD_RANGES)

        self.assertEqual(result["id"], "near")

    def test_returns_none_when_no_players_given(self):
        user_body = {"height_cm": 188, "wingspan_cm": 193}

        result = find_body_fit_template(user_body, [], BODY_FIELD_RANGES)

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
