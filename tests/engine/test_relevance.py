# 用途：測試 compute_relevance(四軸座標 × 技能相關性 → R_i)的加權平均計算,
# 包含全相關、零相關、混合權重、權重全為零時該報錯等情況。
# 可手動調整的變數：無——這支檔案裡的座標/相關性數字都是為了驗證公式而設計的
# 測試案例,不是要調的參數。

import unittest

from engine.relevance import compute_relevance


class ComputeRelevanceTest(unittest.TestCase):
    def test_full_relevance_on_a_maxed_out_axis_gives_full_score(self):
        coords = {"A": 100, "B": 0, "C": 0, "D": 0}
        relevance = {"A": 1.0, "B": 0.0, "C": 0.0, "D": 0.0}

        self.assertEqual(compute_relevance(coords, relevance), 1.0)

    def test_zero_coordinate_on_the_only_relevant_axis_gives_zero(self):
        coords = {"A": 0, "B": 0, "C": 0, "D": 0}
        relevance = {"A": 0.0, "B": 0.0, "C": 0.9, "D": 0.6}

        self.assertEqual(compute_relevance(coords, relevance), 0.0)

    def test_weighted_average_across_multiple_relevant_axes(self):
        # rim_protection-like profile: mostly C, some D
        coords = {"A": 20, "B": 20, "C": 80, "D": 40}
        relevance = {"A": 0.1, "B": 0.1, "C": 0.9, "D": 0.6}

        # weighted sum = .1*.20 + .1*.20 + .9*.80 + .6*.40 = .02+.02+.72+.24 = 1.00
        # weight total = .1+.1+.9+.6 = 1.7
        # R = 1.00 / 1.7
        self.assertAlmostEqual(compute_relevance(coords, relevance), 1.00 / 1.7)

    def test_all_zero_relevance_weights_raises(self):
        coords = {"A": 50, "B": 50, "C": 50, "D": 50}
        relevance = {"A": 0.0, "B": 0.0, "C": 0.0, "D": 0.0}

        with self.assertRaises(ValueError):
            compute_relevance(coords, relevance)

    def test_result_is_clamped_to_zero_one(self):
        coords = {"A": 100, "B": 100, "C": 100, "D": 100}
        relevance = {"A": 1.0, "B": 1.0, "C": 1.0, "D": 1.0}

        self.assertEqual(compute_relevance(coords, relevance), 1.0)


if __name__ == "__main__":
    unittest.main()
