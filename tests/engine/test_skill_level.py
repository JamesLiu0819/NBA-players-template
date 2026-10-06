# 用途：測試 skill_gap()——技能缺口 G 的計算。
# 可手動調整的變數：無——這裡的座標跟權重都是為了驗證公式而設計的測試數字。

import unittest

from engine.skill_level import skill_gap

ALL_ZERO = {"A": 0.0, "B1": 0.0, "B2": 0.0, "C1": 0.0, "C2": 0.0, "D": 0.0}


class SkillGapTest(unittest.TestCase):
    def test_gap_is_relevance_times_positive_difference_on_one_axis(self):
        relevance = dict(ALL_ZERO, A=1.0)
        user = dict(ALL_ZERO, A=40.0)
        target = dict(ALL_ZERO, A=70.0)

        self.assertAlmostEqual(skill_gap(relevance, user, target), 30.0)

    def test_gap_is_zero_when_user_already_matches_or_exceeds_target(self):
        relevance = dict(ALL_ZERO, A=1.0)
        user = dict(ALL_ZERO, A=80.0)
        target = dict(ALL_ZERO, A=50.0)

        self.assertEqual(skill_gap(relevance, user, target), 0.0)

    def test_gap_is_weighted_sum_across_several_trainable_axes(self):
        relevance = {"A": 0.5, "B1": 1.0, "B2": 0.0, "C1": 0.0, "C2": 0.0, "D": 0.0}
        user = {"A": 50.0, "B1": 20.0, "B2": 0.0, "C1": 0.0, "C2": 0.0, "D": 0.0}
        target = {"A": 60.0, "B1": 50.0, "B2": 0.0, "C1": 0.0, "C2": 0.0, "D": 0.0}

        # 0.5 × (60 − 50) + 1.0 × (50 − 20) = 5 + 30
        self.assertAlmostEqual(skill_gap(relevance, user, target), 35.0)

    def test_d_axis_never_contributes_to_gap(self):
        relevance = dict(ALL_ZERO, D=1.0)
        user = dict(ALL_ZERO, D=0.0)
        target = dict(ALL_ZERO, D=100.0)

        self.assertEqual(skill_gap(relevance, user, target), 0.0)

    def test_target_not_above_user_on_any_trainable_axis_gives_zero_total(self):
        relevance = {"A": 0.3, "B1": 0.9, "B2": 0.1, "C1": 0.1, "C2": 0.1, "D": 0.2}
        user = {"A": 90.0, "B1": 90.0, "B2": 90.0, "C1": 90.0, "C2": 90.0, "D": 10.0}
        target = {"A": 80.0, "B1": 80.0, "B2": 80.0, "C1": 80.0, "C2": 80.0, "D": 100.0}

        self.assertEqual(skill_gap(relevance, user, target), 0.0)

    def test_same_input_gives_same_output(self):
        relevance = {"A": 0.3, "B1": 0.9, "B2": 0.1, "C1": 0.1, "C2": 0.1, "D": 0.2}
        user = {"A": 40.0, "B1": 30.0, "B2": 20.0, "C1": 60.0, "C2": 10.0, "D": 50.0}
        target = {"A": 70.0, "B1": 80.0, "B2": 50.0, "C1": 60.0, "C2": 40.0, "D": 90.0}

        first = skill_gap(relevance, user, target)
        second = skill_gap(relevance, user, target)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
