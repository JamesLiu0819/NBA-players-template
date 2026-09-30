# 用途：驗證 data/archetypes.json 的資料完整性(id 唯一、座標範圍、
# name_zh/flavor 齊全)。
# 可手動調整的變數：無——這支測試檔本身不含校準參數,它是在檢查別的檔案。

import json
import unittest
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
AXES = ("A", "B", "C", "D")


class ArchetypesDataTest(unittest.TestCase):
    def setUp(self):
        with open(DATA_DIR / "zh" / "原型.json", encoding="utf-8") as f:
            self.archetypes = json.load(f)["archetypes"]

    def test_has_at_least_two_archetypes(self):
        self.assertGreaterEqual(len(self.archetypes), 2)

    def test_ids_are_unique(self):
        ids = [a["id"] for a in self.archetypes]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_archetype_has_required_fields(self):
        required = {"id", "name_zh", "coordinates", "flavor"}
        for archetype in self.archetypes:
            self.assertTrue(required.issubset(archetype.keys()), archetype.get("id"))

    def test_coordinates_are_within_zero_to_hundred(self):
        for archetype in self.archetypes:
            for axis in AXES:
                value = archetype["coordinates"][axis]
                self.assertGreaterEqual(value, 0, archetype["id"])
                self.assertLessEqual(value, 100, archetype["id"])

    def test_flavor_is_non_empty(self):
        for archetype in self.archetypes:
            self.assertTrue(archetype["flavor"].strip(), archetype["id"])

    def test_every_archetype_has_a_size_field_within_zero_to_hundred(self):
        # size (height/weight percentile average) is what lets
        # classify_archetype avoid labeling a short player's balanced style
        # as a tall-implying archetype like do_it_all_forward, or a tall
        # player's ball-handling style as floor_general (2026-10 discussion).
        for archetype in self.archetypes:
            self.assertIn("size", archetype, archetype["id"])
            self.assertGreaterEqual(archetype["size"], 0, archetype["id"])
            self.assertLessEqual(archetype["size"], 100, archetype["id"])


if __name__ == "__main__":
    unittest.main()
