# 用途：測試 score_skill_current_level(BARS 作答→技能現況水準)跟
# compute_gap(現況→缺口 G_i)這兩個函數的計算邏輯與邊界情況。
# 可手動調整的變數：無——QUESTIONS 是固定的測試用假資料,不是要調的參數。

import unittest

from engine.skill_level import compute_gap, score_skill_current_level

QUESTIONS = [
    {"id": "shoot1", "skill_id": "perimeter_shooting", "prompt": "..."},
    {"id": "shoot2", "skill_id": "perimeter_shooting", "prompt": "..."},
    {"id": "rim1", "skill_id": "rim_protection", "prompt": "..."},
]


class ScoreSkillCurrentLevelTest(unittest.TestCase):
    def test_averages_all_answers_for_the_skill(self):
        answers = [
            {"question_id": "shoot1", "score": 4},
            {"question_id": "shoot2", "score": 2},
            {"question_id": "rim1", "score": 5},  # different skill, must be ignored
        ]

        level = score_skill_current_level(QUESTIONS, answers, "perimeter_shooting")

        self.assertEqual(level, 3.0)

    def test_single_question_skill(self):
        answers = [{"question_id": "rim1", "score": 5}]

        level = score_skill_current_level(QUESTIONS, answers, "rim_protection")

        self.assertEqual(level, 5.0)

    def test_unknown_skill_id_raises(self):
        answers = [{"question_id": "shoot1", "score": 4}]

        with self.assertRaises(ValueError):
            score_skill_current_level(QUESTIONS, answers, "does_not_exist")

    def test_no_answers_for_skill_raises(self):
        answers = [{"question_id": "rim1", "score": 5}]

        with self.assertRaises(ValueError):
            score_skill_current_level(QUESTIONS, answers, "perimeter_shooting")

    def test_score_out_of_range_raises(self):
        answers = [{"question_id": "rim1", "score": 0}]

        with self.assertRaises(ValueError):
            score_skill_current_level(QUESTIONS, answers, "rim_protection")


class ComputeGapTest(unittest.TestCase):
    def test_gap_is_target_minus_current(self):
        self.assertEqual(compute_gap(current=2, target=5), 3)

    def test_default_target_is_mastery_level_5(self):
        self.assertEqual(compute_gap(current=2), 3)

    def test_gap_clamped_to_zero_when_current_exceeds_target(self):
        self.assertEqual(compute_gap(current=4, target=3), 0)

    def test_fully_mastered_skill_has_zero_gap(self):
        self.assertEqual(compute_gap(current=5, target=5), 0)


if __name__ == "__main__":
    unittest.main()
