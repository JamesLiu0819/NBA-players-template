# 用途：測試 collect_body_measurements(身材數值題作答 → 身體特徵字典)跟
# body_distance(兩份身體特徵字典的距離,只比對重疊欄位)的計算邏輯與邊界情況。
# 可手動調整的變數：無——這支檔案裡的座標/題目資料都是為了驗證公式而設計的
# 測試案例,不是要調的參數。

import unittest

from engine.body_fit import (
    GENERAL_POPULATION_BODY_STATS,
    _empirical_percentile,
    _normal_cdf_percentile,
    body_distance,
    collect_body_measurements,
    percentile_normalize_body,
)

QUESTIONS = [
    {"id": "q_height", "field": "height_cm", "prompt": "...", "unit": "cm", "min": 140, "max": 230},
    {"id": "q_wingspan", "field": "wingspan_cm", "prompt": "...", "unit": "cm", "min": 140, "max": 250},
    {"id": "q_weight", "field": "weight_kg", "prompt": "...", "unit": "kg", "min": 40, "max": 160},
]


class CollectBodyMeasurementsTest(unittest.TestCase):
    def test_maps_answers_to_field_names(self):
        answers = [
            {"question_id": "q_height", "value": 188},
            {"question_id": "q_wingspan", "value": 193},
        ]

        result = collect_body_measurements(QUESTIONS, answers)

        self.assertEqual(result, {"height_cm": 188, "wingspan_cm": 193})

    def test_omits_unanswered_questions_rather_than_erroring(self):
        answers = [{"question_id": "q_height", "value": 188}]

        result = collect_body_measurements(QUESTIONS, answers)

        self.assertEqual(result, {"height_cm": 188})

    def test_unknown_question_id_raises(self):
        answers = [{"question_id": "does_not_exist", "value": 100}]

        with self.assertRaises(ValueError):
            collect_body_measurements(QUESTIONS, answers)

    def test_value_below_min_raises(self):
        answers = [{"question_id": "q_height", "value": 50}]

        with self.assertRaises(ValueError):
            collect_body_measurements(QUESTIONS, answers)

    def test_value_above_max_raises(self):
        answers = [{"question_id": "q_weight", "value": 999}]

        with self.assertRaises(ValueError):
            collect_body_measurements(QUESTIONS, answers)


FIELD_RANGES = {
    "height_cm": (140, 230),
    "wingspan_cm": (140, 250),
    "weight_kg": (40, 160),
}


class BodyDistanceTest(unittest.TestCase):
    def test_computes_distance_over_common_fields_only(self):
        user = {"height_cm": 188, "wingspan_cm": 193, "weight_kg": 83}
        player = {"height_cm": 198, "wingspan_cm": 203}

        # only height_cm and wingspan_cm overlap; weight_kg is ignored.
        # each field is min-max normalized to 0-100 before the distance is
        # taken, so the offset cancels out and only the raw diff / span
        # ratio matters here.
        result = body_distance(user, player, FIELD_RANGES)

        expected = (
            (10 / 90 * 100) ** 2 + (10 / 110 * 100) ** 2
        ) ** 0.5
        self.assertAlmostEqual(result, expected)

    def test_normalizes_so_a_large_span_field_does_not_dominate(self):
        # weight_kg has a much smaller numeric span (120) than
        # running_vertical_reach_cm (170) in the real question set, but here
        # we use a tiny 2-point span to make the dominance obvious: a 1-unit
        # raw diff on a 2-point-span field should outweigh a 10-unit raw
        # diff on a 90-point-span field once both are normalized to 0-100.
        field_ranges = {"height_cm": (140, 230), "tiny_span_field": (0, 2)}
        user = {"height_cm": 188, "tiny_span_field": 0}
        player = {"height_cm": 198, "tiny_span_field": 1}

        result = body_distance(user, player, field_ranges)

        expected = ((10 / 90 * 100) ** 2 + (1 / 2 * 100) ** 2) ** 0.5
        self.assertAlmostEqual(result, expected)

    def test_raises_when_no_fields_overlap(self):
        user = {"height_cm": 188}
        player = {"weight_kg": 83}

        with self.assertRaises(ValueError):
            body_distance(user, player, FIELD_RANGES)


class NormalCdfPercentileTest(unittest.TestCase):
    def test_value_at_mean_is_the_50th_percentile(self):
        self.assertAlmostEqual(_normal_cdf_percentile(180, 180, 8), 50.0)

    def test_one_sd_above_mean_is_about_the_84th_percentile(self):
        self.assertAlmostEqual(_normal_cdf_percentile(188, 180, 8), 84.13, places=1)

    def test_one_sd_below_mean_is_about_the_16th_percentile(self):
        self.assertAlmostEqual(_normal_cdf_percentile(172, 180, 8), 15.87, places=1)


class EmpiricalPercentileTest(unittest.TestCase):
    def test_matches_value_below_half_the_pool(self):
        # 25 has exactly two values below it (10, 20) and none equal, out of 5.
        self.assertAlmostEqual(_empirical_percentile(25, [10, 20, 30, 40, 50]), 40.0)

    def test_ties_count_as_half_a_rank(self):
        # two values equal 30 (indices 2 and one duplicate); (2 + 0.5*2) / 5 * 100
        self.assertAlmostEqual(_empirical_percentile(30, [10, 20, 30, 30, 50]), 60.0)

    def test_empty_pool_raises(self):
        with self.assertRaises(ValueError):
            _empirical_percentile(30, [])


class PercentileNormalizeBodyTest(unittest.TestCase):
    def test_converts_only_the_fields_with_population_stats_to_percentiles(self):
        # height_cm and weight_kg have GENERAL_POPULATION_BODY_STATS entries;
        # wingspan_cm does not, so it must pass through completely untouched
        # (2026-09-11 body-template-collapses-to-guards fix: matching NBA
        # players on raw cm/kg means almost every self-reporting user is
        # shorter than nearly the whole roster, so height/weight get
        # converted to "percentile among basketball-playing people" first,
        # then compared against each player's percentile within the actual
        # player pool -- wingspan/reach/sprint have no reliable
        # general-population reference, so they stay on the raw scale).
        field_ranges = {
            "height_cm": (140, 230),
            "weight_kg": (40, 160),
            "wingspan_cm": (140, 250),
        }
        user_body = {"height_cm": 188, "weight_kg": 75, "wingspan_cm": 193}
        players = [
            {"id": "p1", "body": {"height_cm": 190, "weight_kg": 80, "wingspan_cm": 195}},
            {"id": "p2", "body": {"height_cm": 210, "weight_kg": 100, "wingspan_cm": 220}},
        ]

        new_user_body, new_players, new_field_ranges = percentile_normalize_body(
            user_body, players, field_ranges
        )

        self.assertEqual(new_field_ranges["height_cm"], (0, 100))
        self.assertEqual(new_field_ranges["weight_kg"], (0, 100))
        self.assertEqual(new_field_ranges["wingspan_cm"], (140, 250))

        height_mean, height_sd = GENERAL_POPULATION_BODY_STATS["height_cm"]
        self.assertAlmostEqual(
            new_user_body["height_cm"], _normal_cdf_percentile(188, height_mean, height_sd)
        )
        self.assertEqual(new_user_body["wingspan_cm"], 193)

        pool = [190, 210]
        self.assertAlmostEqual(new_players[0]["body"]["height_cm"], _empirical_percentile(190, pool))
        self.assertAlmostEqual(new_players[1]["body"]["height_cm"], _empirical_percentile(210, pool))
        self.assertEqual(new_players[0]["body"]["wingspan_cm"], 195)
        self.assertEqual(new_players[0]["id"], "p1")

    def test_returns_inputs_unchanged_when_no_percentile_fields_present(self):
        field_ranges = {"wingspan_cm": (140, 250)}
        user_body = {"wingspan_cm": 193}
        players = [{"id": "p1", "body": {"wingspan_cm": 195}}]

        new_user_body, new_players, new_field_ranges = percentile_normalize_body(
            user_body, players, field_ranges
        )

        self.assertEqual(new_user_body, user_body)
        self.assertEqual(new_players, players)
        self.assertEqual(new_field_ranges, field_ranges)


if __name__ == "__main__":
    unittest.main()
