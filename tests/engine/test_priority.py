# 用途：測試 compute_priority() 跟 rank_priorities()——P = G × E ÷ C 與排序。
# 可手動調整的變數：無——這裡的數字都是為了驗證公式而設計的測試案例。

import unittest

from engine.priority import compute_priority, rank_priorities


class ComputePriorityTest(unittest.TestCase):
    def test_priority_is_g_times_e_over_c(self):
        self.assertAlmostEqual(compute_priority(g=30.0, e=1.5, c=3), 15.0)

    def test_non_positive_cost_raises(self):
        with self.assertRaises(ValueError):
            compute_priority(g=10.0, e=1.0, c=0)


class RankPrioritiesTest(unittest.TestCase):
    def test_sorts_descending_by_priority(self):
        items = [
            {"skill_id": "b", "G": 10.0, "E": 1.0, "C": 2},
            {"skill_id": "a", "G": 30.0, "E": 1.0, "C": 2},
        ]

        ranked = rank_priorities(items)

        self.assertEqual([item["skill_id"] for item in ranked], ["a", "b"])
        self.assertAlmostEqual(ranked[0]["P"], 15.0)

    def test_ties_break_on_ascending_skill_id(self):
        items = [
            {"skill_id": "zeta", "G": 10.0, "E": 1.0, "C": 1},
            {"skill_id": "alpha", "G": 10.0, "E": 1.0, "C": 1},
        ]

        ranked = rank_priorities(items)

        self.assertEqual([item["skill_id"] for item in ranked], ["alpha", "zeta"])

    def test_does_not_mutate_inputs(self):
        items = [{"skill_id": "a", "G": 10.0, "E": 1.0, "C": 1}]

        rank_priorities(items)

        self.assertNotIn("P", items[0])


if __name__ == "__main__":
    unittest.main()
