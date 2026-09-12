# 用途：測試 classify_archetype(把四軸座標分類到最接近的球場定位原型)的
# 最近鄰計算邏輯與邊界情況。
# 可手動調整的變數：無——這支檔案裡的座標資料都是為了驗證公式而設計的
# 測試案例,不是要調的參數。

import unittest

from engine.archetype import classify_archetype


class ClassifyArchetypeTest(unittest.TestCase):
    def test_returns_the_exact_match(self):
        archetypes = [
            {"id": "a", "coordinates": {"A": 90, "B": 10, "C": 10, "D": 10}},
            {"id": "b", "coordinates": {"A": 10, "B": 90, "C": 10, "D": 10}},
        ]

        result = classify_archetype({"A": 90, "B": 10, "C": 10, "D": 10}, archetypes)

        self.assertEqual(result["id"], "a")

    def test_returns_the_closer_archetype_when_no_exact_match(self):
        archetypes = [
            {"id": "a", "coordinates": {"A": 90, "B": 10, "C": 10, "D": 10}},
            {"id": "b", "coordinates": {"A": 10, "B": 90, "C": 10, "D": 10}},
        ]

        result = classify_archetype({"A": 80, "B": 15, "C": 12, "D": 8}, archetypes)

        self.assertEqual(result["id"], "a")

    def test_other_fields_pass_through_on_the_winning_archetype(self):
        archetypes = [
            {"id": "a", "name_zh": "測試原型", "flavor": "一句話文案", "coordinates": {"A": 50, "B": 50, "C": 50, "D": 50}},
        ]

        result = classify_archetype({"A": 50, "B": 50, "C": 50, "D": 50}, archetypes)

        self.assertEqual(result["name_zh"], "測試原型")
        self.assertEqual(result["flavor"], "一句話文案")

    def test_raises_when_archetypes_is_empty(self):
        with self.assertRaises(ValueError):
            classify_archetype({"A": 50, "B": 50, "C": 50, "D": 50}, [])


if __name__ == "__main__":
    unittest.main()
