# 用途：測試 format_dominant_factor_sentence() 的 lang 參數行為——這個函式
# 之前完全沒有專屬單元測試(只靠 server/test_app.py 間接測到)。
# 可手動調整的變數：無。

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from scripts.run_priority import format_dominant_factor_sentence  # noqa: E402


def make_item(skill_id, name_zh, P, G, E, R, C):
    return {"skill_id": skill_id, "name_zh": name_zh, "P": P, "G": G, "E": E, "R": R, "C": C}


class FormatDominantFactorSentenceTest(unittest.TestCase):
    def test_returns_none_when_fewer_than_two_items(self):
        self.assertIsNone(format_dominant_factor_sentence([make_item("a", "技能A", 1, 1, 1, 1, 1)]))

    def test_tie_sentence_in_zh(self):
        ranked = [
            make_item("a", "技能A", 1.0, 1, 1, 1, 1),
            make_item("b", "技能B", 1.0, 1, 1, 1, 1),
        ]

        result = format_dominant_factor_sentence(ranked)

        self.assertIn("技能A", result)
        self.assertIn("技能B", result)
        self.assertIn("打平", result)

    def test_tie_sentence_in_en_differs_from_zh(self):
        ranked = [
            make_item("a", "Skill A", 1.0, 1, 1, 1, 1),
            make_item("b", "Skill B", 1.0, 1, 1, 1, 1),
        ]

        zh_result = format_dominant_factor_sentence(ranked, lang="zh")
        en_result = format_dominant_factor_sentence(ranked, lang="en")

        self.assertNotEqual(zh_result, en_result)
        self.assertIn("Skill A", en_result)
        self.assertIn("Skill B", en_result)

    def test_dominant_factor_sentence_in_en_mentions_ratio(self):
        ranked = [
            make_item("a", "Skill A", 2.0, 3, 1, 1, 1),
            make_item("b", "Skill B", 1.0, 1, 1, 1, 1),
        ]

        result = format_dominant_factor_sentence(ranked, lang="en")

        self.assertIn("Skill A", result)
        self.assertIn("Skill B", result)
        self.assertNotIn("主因是", result)


if __name__ == "__main__":
    unittest.main()
