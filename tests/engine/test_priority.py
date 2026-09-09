# 用途：測試 compute_priority(P = G×E×R/C)、rank_priorities(排序)、
# explain_dominant_factor(哪個因子主導了排名差距)三個函數的計算邏輯。
# 可手動調整的變數：無——這支檔案裡的 G/E/R/C 數字都是為了驗證公式而設計的
# 測試案例,不是要調的參數。

import unittest

from engine.priority import compute_priority, explain_dominant_factor, rank_priorities


class ComputePriorityTest(unittest.TestCase):
    def test_multiplies_gap_env_relevance_and_divides_by_cost(self):
        # G=4, E=1.8, R=0.5, C=2 -> (4*1.8*0.5)/2 = 1.8
        self.assertAlmostEqual(compute_priority(g=4, e=1.8, r=0.5, c=2), 1.8)

    def test_zero_gap_gives_zero_priority_regardless_of_other_factors(self):
        self.assertEqual(compute_priority(g=0, e=2.0, r=1.0, c=1), 0.0)

    def test_zero_cost_raises(self):
        with self.assertRaises(ValueError):
            compute_priority(g=4, e=1.8, r=0.5, c=0)


class RankPrioritiesTest(unittest.TestCase):
    def test_sorts_by_priority_descending_and_attaches_p(self):
        items = [
            {"skill_id": "low", "G": 1, "E": 1.0, "R": 0.5, "C": 5},
            {"skill_id": "high", "G": 4, "E": 1.8, "R": 0.8, "C": 2},
            {"skill_id": "mid", "G": 3, "E": 1.0, "R": 0.5, "C": 3},
        ]

        ranked = rank_priorities(items)

        self.assertEqual([item["skill_id"] for item in ranked], ["high", "mid", "low"])
        # P for "high" = (4*1.8*0.8)/2 = 2.88
        self.assertAlmostEqual(ranked[0]["P"], 2.88)


class ExplainDominantFactorTest(unittest.TestCase):
    def test_identifies_gap_as_the_dominant_factor(self):
        # Everything else equal, only G differs sharply.
        higher = {"skill_id": "a", "G": 4, "E": 1.0, "R": 0.5, "C": 2}
        lower = {"skill_id": "b", "G": 1, "E": 1.0, "R": 0.5, "C": 2}

        result = explain_dominant_factor(higher, lower)

        self.assertEqual(result["factor"], "G")
        self.assertAlmostEqual(result["ratio"], 4.0)

    def test_identifies_environment_multiplier_as_the_dominant_factor(self):
        # This is the case SPEC.md §11 (james.json) hinges on: a skill that
        # looks "already good enough" unweighted jumps to #1 once E is applied.
        higher = {"skill_id": "a", "G": 2, "E": 1.8, "R": 0.5, "C": 2}
        lower = {"skill_id": "b", "G": 2, "E": 0.6, "R": 0.5, "C": 2}

        result = explain_dominant_factor(higher, lower)

        self.assertEqual(result["factor"], "E")
        self.assertAlmostEqual(result["ratio"], 3.0)

    def test_identifies_cost_as_the_dominant_factor(self):
        # Higher-priority item wins because it is *cheaper*, not because its
        # other factors are bigger.
        higher = {"skill_id": "a", "G": 2, "E": 1.0, "R": 0.5, "C": 1}
        lower = {"skill_id": "b", "G": 2, "E": 1.0, "R": 0.5, "C": 4}

        result = explain_dominant_factor(higher, lower)

        self.assertEqual(result["factor"], "C")
        self.assertAlmostEqual(result["ratio"], 4.0)

    def test_ratios_multiply_out_to_the_priority_ratio(self):
        higher = {"skill_id": "a", "G": 4, "E": 1.8, "R": 0.8, "C": 2}
        lower = {"skill_id": "b", "G": 2, "E": 1.2, "R": 0.4, "C": 3}

        result = explain_dominant_factor(higher, lower)

        p_higher = compute_priority(g=4, e=1.8, r=0.8, c=2)
        p_lower = compute_priority(g=2, e=1.2, r=0.4, c=3)
        self.assertAlmostEqual(result["priority_ratio"], p_higher / p_lower)

    def test_raises_if_the_supposed_higher_item_does_not_outrank_the_lower(self):
        higher = {"skill_id": "a", "G": 1, "E": 1.0, "R": 0.5, "C": 5}
        lower = {"skill_id": "b", "G": 4, "E": 1.8, "R": 0.8, "C": 2}

        with self.assertRaises(ValueError):
            explain_dominant_factor(higher, lower)


if __name__ == "__main__":
    unittest.main()
