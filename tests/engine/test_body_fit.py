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


class BodyDistanceTest(unittest.TestCase):
    def test_computes_distance_over_common_fields_only(self):
        user = {"height_cm": 188, "wingspan_cm": 193, "weight_kg": 83}
        player = {"height_cm": 198, "wingspan_cm": 203}

        # only height_cm and wingspan_cm overlap; weight_kg is ignored
        result = body_distance(user, player)

        self.assertAlmostEqual(result, (10 ** 2 + 10 ** 2) ** 0.5)

    def test_raises_when_no_fields_overlap(self):
        user = {"height_cm": 188}
        player = {"weight_kg": 83}

        with self.assertRaises(ValueError):
            body_distance(user, player)


if __name__ == "__main__":
    unittest.main()
