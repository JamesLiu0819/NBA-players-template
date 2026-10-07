# 用途：測試 classify_archetype(把六軸座標分類到最接近的球場定位原型)的
# 最近鄰計算邏輯與邊界情況,style_axis_spread(判斷使用者有沒有明顯主打
# 方向)、compute_user_size(對球員池的真實身高體重擬合常態分布,算使用者
# 的身材百分位)、classify_archetype_for_user(2026-10,直接拿使用者自己的
# 六軸座標分類——有明顯主打方向用打法形狀,沒有就用身材分數,取代舊版
# classify_archetype_by_majority 的真人球員多數決設計,見 spec item 5),
# 以及 compute_player_sizes(算每位球員身高體重在整份名單裡的排名百分位
# ——2026-10 發現這個百分位不能跟 body_fit.percentile_normalize_body 給
# 10 人對照表用的百分位共用,見 archetype.py 檔頭;這支函式本身保留給
# 自己的測試用,結果頁已經改用 compute_user_size)。
# 可手動調整的變數：無——這支檔案裡的座標資料都是為了驗證公式而設計的
# 測試案例,不是要調的參數。

import unittest

from engine.archetype import (
    ARCHETYPE_SPREAD_THRESHOLD,
    classify_archetype,
    classify_archetype_for_user,
    compute_player_sizes,
    compute_user_size,
    style_axis_spread,
)


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
        # both archetypes are equidistant on the six style axes alone (dead center);
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


class StyleAxisSpreadTest(unittest.TestCase):
    def test_max_minus_min_over_the_five_style_axes_only(self):
        # D is deliberately excluded -- a huge D-axis gap must not count.
        coords = {"A": 10, "B1": 90, "B2": 50, "C1": 50, "C2": 50, "D": 0}
        self.assertEqual(style_axis_spread(coords), 80)

    def test_flat_answers_give_zero_spread(self):
        coords = {"A": 50, "B1": 50, "B2": 50, "C1": 50, "C2": 50, "D": 50}
        self.assertEqual(style_axis_spread(coords), 0)


class ComputeUserSizeTest(unittest.TestCase):
    # 2026-10 Task 7 checkpoint finding: ranking the user's raw height/weight
    # within the player pool (the same method compute_player_sizes uses for
    # players) collapses almost every simulated user to percentile ~0,
    # because a typical self-reporting user (~175cm) falls below the
    # shortest real NBA player (~185cm) -- see the plan's Task 7 report.
    # compute_user_size instead fits a NORMAL distribution to the pool's own
    # real height_cm/weight_kg (mean/sd from the pool itself) and reads the
    # user's percentile off that curve, so it extrapolates smoothly below
    # the pool's observed floor instead of collapsing everyone there to the
    # same value. This is still the SAME 0-100 scale the archetype "size"
    # anchors in data/zh/原型.json were calibrated on (compute_player_sizes'
    # empirical rank and this normal approximation agree closely for values
    # WITHIN the pool's own range; they diverge only below/above it, which is
    # exactly the case compute_player_sizes couldn't handle).
    POOL = [
        {"id": "a", "body": {"height_cm": 190, "weight_kg": 90}},
        {"id": "b", "body": {"height_cm": 210, "weight_kg": 110}},
    ]
    # height pool mean=200/sd=10, weight pool mean=100/sd=10 (by construction).

    def test_user_at_the_pools_mean_gets_the_50th_percentile(self):
        user_size = compute_user_size({"height_cm": 200, "weight_kg": 100}, self.POOL)

        self.assertAlmostEqual(user_size, 50.0)

    def test_user_below_the_pools_observed_minimum_gets_a_small_but_nonzero_value(self):
        # 180cm is below BOTH pool members (190, 210) -- an empirical rank
        # (compute_player_sizes' method) would give exactly 0 here. The
        # normal-fit extrapolation must NOT collapse to 0.
        user_size = compute_user_size({"height_cm": 180, "weight_kg": 80}, self.POOL)

        self.assertGreater(user_size, 0.0)
        self.assertLess(user_size, 10.0)  # still clearly "small" -- a long way below the mean
        # hand-computed: z = (180-200)/10 = -2.0 for both fields ->
        # 50*(1+erf(-2/sqrt(2))) = 50*(1+erf(-1.41421356)) ~= 2.275
        self.assertAlmostEqual(user_size, 2.275, places=2)

    def test_two_users_below_the_floor_still_get_different_differentiated_values(self):
        # the whole point of the fix: two users BOTH below the pool's
        # observed minimum must still get two DIFFERENT percentiles,
        # ordered the same way their actual height/weight are ordered --
        # not both collapsed to the same floor value.
        higher = compute_user_size({"height_cm": 180, "weight_kg": 80}, self.POOL)
        lower = compute_user_size({"height_cm": 160, "weight_kg": 60}, self.POOL)

        self.assertGreater(higher, lower)
        self.assertGreater(lower, 0.0)

    def test_returns_none_when_user_body_missing_height_or_weight(self):
        self.assertIsNone(compute_user_size({"height_cm": 180}, self.POOL))
        self.assertIsNone(compute_user_size({}, self.POOL))

    def test_returns_none_when_no_player_has_body_data(self):
        players = [{"id": "a"}]
        self.assertIsNone(compute_user_size({"height_cm": 180, "weight_kg": 75}, players))

    def test_returns_none_when_fewer_than_two_players_have_body_data(self):
        players = [{"id": "a", "body": {"height_cm": 190, "weight_kg": 90}}]
        self.assertIsNone(compute_user_size({"height_cm": 180, "weight_kg": 75}, players))

    def test_returns_none_when_pool_has_zero_variance(self):
        # every player in the pool has the exact same height/weight -> sd=0
        # -> a normal-distribution fit is undefined, not a division-by-zero
        # crash.
        players = [
            {"id": "a", "body": {"height_cm": 200, "weight_kg": 100}},
            {"id": "b", "body": {"height_cm": 200, "weight_kg": 100}},
        ]
        self.assertIsNone(compute_user_size({"height_cm": 190, "weight_kg": 90}, players))


class ClassifyArchetypeForUserTest(unittest.TestCase):
    def setUp(self):
        self.archetypes = [
            {"id": "guard_shape", "name_zh": "控球型", "coordinates": {"A": 90, "B1": 50, "B2": 10, "C1": 50, "C2": 10, "D": 50}, "size": 20},
            {"id": "big_shape", "name_zh": "低位型", "coordinates": {"A": 10, "B1": 10, "B2": 90, "C1": 10, "C2": 50, "D": 50}, "size": 80},
        ]

    def test_high_spread_user_classified_by_relative_strength_ignoring_overall_level(self):
        # overall level is very high across the board, but the SHAPE (A is
        # the standout, by 50+ points over every other style axis) matches
        # guard_shape's shape, not big_shape's -- a plain (non-recentered)
        # distance would be dominated by the uniformly-high level instead.
        coordinates = {"A": 95, "B1": 60, "B2": 20, "C1": 60, "C2": 20, "D": 60}
        self.assertGreaterEqual(style_axis_spread(coordinates), ARCHETYPE_SPREAD_THRESHOLD)

        archetype, mode = classify_archetype_for_user(coordinates, self.archetypes, size=25)

        self.assertEqual(archetype["id"], "guard_shape")
        self.assertEqual(mode, "relative_strength")

    def test_low_spread_user_classified_by_size_alone(self):
        # every style axis is close together (spread < 25) -- the shape
        # carries no signal, so only size should decide the outcome.
        coordinates = {"A": 50, "B1": 55, "B2": 52, "C1": 48, "C2": 53, "D": 50}
        self.assertLess(style_axis_spread(coordinates), ARCHETYPE_SPREAD_THRESHOLD)

        archetype, mode = classify_archetype_for_user(coordinates, self.archetypes, size=18)

        self.assertEqual(archetype["id"], "guard_shape")  # size 20 is closer to 18 than 80 is
        self.assertEqual(mode, "body_only")

    def test_spread_exactly_at_threshold_uses_relative_strength(self):
        # spec: >= 25 is relative-strength, so the boundary itself is inclusive.
        coordinates = {"A": 50 + ARCHETYPE_SPREAD_THRESHOLD, "B1": 50, "B2": 50, "C1": 50, "C2": 50, "D": 50}
        self.assertEqual(style_axis_spread(coordinates), ARCHETYPE_SPREAD_THRESHOLD)

        _, mode = classify_archetype_for_user(coordinates, self.archetypes, size=50)

        self.assertEqual(mode, "relative_strength")

    def test_body_only_tie_breaks_on_ascending_archetype_id(self):
        tied_archetypes = [
            {"id": "z_archetype", "coordinates": {"A": 50, "B1": 50, "B2": 50, "C1": 50, "C2": 50, "D": 50}, "size": 40},
            {"id": "a_archetype", "coordinates": {"A": 50, "B1": 50, "B2": 50, "C1": 50, "C2": 50, "D": 50}, "size": 60},
        ]
        coordinates = {"A": 50, "B1": 50, "B2": 50, "C1": 50, "C2": 50, "D": 50}

        archetype, mode = classify_archetype_for_user(coordinates, tied_archetypes, size=50)

        self.assertEqual(archetype["id"], "a_archetype")
        self.assertEqual(mode, "body_only")

    def test_body_only_falls_back_to_relative_strength_when_size_is_none(self):
        coordinates = {"A": 50, "B1": 55, "B2": 52, "C1": 48, "C2": 53, "D": 50}

        archetype, mode = classify_archetype_for_user(coordinates, self.archetypes, size=None)

        self.assertEqual(mode, "relative_strength")

    def test_raises_when_archetypes_is_empty(self):
        with self.assertRaises(ValueError):
            classify_archetype_for_user({"A": 50, "B1": 50, "B2": 50, "C1": 50, "C2": 50, "D": 50}, [])


class ComputePlayerSizesTest(unittest.TestCase):
    def test_ranks_shortest_lightest_player_lowest(self):
        players = [
            {"id": "short", "body": {"height_cm": 180, "weight_kg": 70}},
            {"id": "medium", "body": {"height_cm": 190, "weight_kg": 85}},
            {"id": "tall", "body": {"height_cm": 210, "weight_kg": 110}},
        ]

        sizes = compute_player_sizes(players)

        self.assertLess(sizes["short"], sizes["medium"])
        self.assertLess(sizes["medium"], sizes["tall"])

    def test_omits_players_missing_height_or_weight(self):
        players = [
            {"id": "complete", "body": {"height_cm": 190, "weight_kg": 85}},
            {"id": "no_weight", "body": {"height_cm": 190}},
            {"id": "no_body"},
        ]

        sizes = compute_player_sizes(players)

        self.assertEqual(set(sizes), {"complete"})

    def test_is_relative_to_the_given_pool_not_an_absolute_scale(self):
        # the exact same player (190cm/85kg) gets a different size depending
        # on who else is in the pool -- this is deliberately pool-relative,
        # not a fixed percentile against some universal population (that is
        # body_fit.percentile_normalize_body's job, a different scale --
        # see archetype.py's header for why the two must not be shared).
        same_player = {"id": "p", "body": {"height_cm": 190, "weight_kg": 85}}
        among_bigs = [same_player, {"id": "big", "body": {"height_cm": 220, "weight_kg": 120}}]
        among_guards = [same_player, {"id": "guard", "body": {"height_cm": 175, "weight_kg": 70}}]

        self.assertLess(compute_player_sizes(among_bigs)["p"], compute_player_sizes(among_guards)["p"])


if __name__ == "__main__":
    unittest.main()
