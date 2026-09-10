# 用途：測試 collect_body_measurements(身材數值題作答 → 身體特徵字典)跟
# body_distance(兩份身體特徵字典的距離,只比對重疊欄位)的計算邏輯與邊界情況。
# 可手動調整的變數：無——這支檔案裡的座標/題目資料都是為了驗證公式而設計的
# 測試案例,不是要調的參數。

import unittest

from engine.body_fit import body_distance, collect_body_measurements

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


if __name__ == "__main__":
    unittest.main()
