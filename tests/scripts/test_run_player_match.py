# 用途：測試 describe_growth_recommendation()、build_scouting_report() 的
# lang 參數行為——這兩個函式之前完全沒有專屬單元測試(只靠 server/test_app.py
# 間接測到),這次讓它們變成 lang-aware 是補上直接測試的好時機。
# 可手動調整的變數：無——這裡的技能/球員資料都是為了驗證公式而設計的測試
# fixture,不是要調的參數。

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from scripts.run_player_match import build_scouting_report, describe_growth_recommendation  # noqa: E402

SKILLS_BY_ID = {
    "perimeter_shooting": {
        "id": "perimeter_shooting",
        "metric": {"action": "定點投射三分"},
    },
}


class DescribeGrowthRecommendationTest(unittest.TestCase):
    def test_d_axis_returns_zh_template_by_default(self):
        player = {"dominant_diff_axis": "D", "signature_skill_id": None}

        result = describe_growth_recommendation(player, SKILLS_BY_ID)

        self.assertEqual(result, "身體天賦上有落差,不能單靠練習籃球技能")

    def test_d_axis_returns_english_template_when_lang_is_en(self):
        player = {"dominant_diff_axis": "D", "signature_skill_id": None}

        result = describe_growth_recommendation(player, SKILLS_BY_ID, lang="en")

        self.assertNotEqual(result, "身體天賦上有落差,不能單靠練習籃球技能")
        self.assertTrue(result.strip())

    def test_non_d_axis_glues_action_text_in_zh(self):
        player = {
            "dominant_diff_axis": "B1",
            "signature_skill_id": "perimeter_shooting",
        }
        skills_by_id = {
            "perimeter_shooting": {
                "id": "perimeter_shooting",
                "axis_relevance": {"A": 0, "B1": 1, "B2": 0, "C1": 0, "C2": 0, "D": 0},
                "metric": {"action": "定點投射三分"},
            },
        }

        result = describe_growth_recommendation(player, skills_by_id)

        self.assertEqual(result, "定點投射三分的練習")

    def test_non_d_axis_glues_action_text_in_en(self):
        player = {
            "dominant_diff_axis": "B1",
            "signature_skill_id": "perimeter_shooting",
        }
        skills_by_id = {
            "perimeter_shooting": {
                "id": "perimeter_shooting",
                "axis_relevance": {"A": 0, "B1": 1, "B2": 0, "C1": 0, "C2": 0, "D": 0},
                "metric": {"action": "spot-up three-point shooting"},
            },
        }

        result = describe_growth_recommendation(player, skills_by_id, lang="en")

        self.assertIn("spot-up three-point shooting", result)
        self.assertNotIn("的練習", result)


class BuildScoutingReportTest(unittest.TestCase):
    def test_returns_archetype_flavor(self):
        archetype = {"name_zh": "控場指揮官", "flavor": "球在你手上,進攻節奏由你決定。"}

        result = build_scouting_report(archetype)

        self.assertEqual(result, archetype["flavor"])
