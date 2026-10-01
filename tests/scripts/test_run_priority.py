# 用途：測試 format_dominant_factor_sentence() 的 lang 參數行為——這個函式
# 之前完全沒有專屬單元測試(只靠 server/test_app.py 間接測到)。
# 可手動調整的變數：無。

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from scripts.run_priority import build_priority_items, format_dominant_factor_sentence  # noqa: E402


def make_item(skill_id, name_zh, P, G, E, R, C):
    return {"skill_id": skill_id, "name_zh": name_zh, "P": P, "G": G, "E": E, "R": R, "C": C}


# 最小但真實的題庫/技能 fixture,六個軸都要有題目+作答才能通過
# score_axis_coordinates(),不然會在碰到 env 檢查之前就先因為別的原因
# raise ValueError,測不到我們要測的那一行。
AXIS_QUESTIONS = [
    {"id": "axis_a1", "axis": "A"},
    {"id": "axis_b1_1", "axis": "B1"},
    {"id": "axis_b2_1", "axis": "B2"},
    {"id": "axis_c1_1", "axis": "C1"},
    {"id": "axis_c2_1", "axis": "C2"},
    {"id": "axis_d1", "axis": "D"},
]
SKILL_QUESTIONS = [{"id": "skill_q1", "skill_id": "perimeter_shooting"}]
QUESTIONS = {"axis_positioning": AXIS_QUESTIONS, "skill_behavior": SKILL_QUESTIONS}
AXIS_ANSWERS = [{"question_id": q["id"], "score": 3} for q in AXIS_QUESTIONS]
SKILL_ANSWERS = [{"question_id": "skill_q1", "score": 3}]
SKILLS = [{
    "id": "perimeter_shooting",
    "name_zh": "外線投射",
    "axis_relevance": {"A": 0, "B1": 1, "B2": 0, "C1": 0, "C2": 0, "D": 0},
    "cost_C": 1,
}]


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


class BuildPriorityItemsMissingEnvTest(unittest.TestCase):
    def test_missing_env_weight_raises_value_error_not_system_exit(self):
        with self.assertRaises(ValueError):
            build_priority_items(QUESTIONS, SKILLS, AXIS_ANSWERS, SKILL_ANSWERS, {})


if __name__ == "__main__":
    unittest.main()
