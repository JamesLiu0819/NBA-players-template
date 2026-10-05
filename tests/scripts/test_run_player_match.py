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

from scripts.run_player_match import (  # noqa: E402
    build_scouting_report,
    describe_growth_recommendation,
    describe_training_breakdown,
)

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


SKILLS_BY_ID_MULTI_AXIS = {
    "high_post_playmaking": {
        "id": "high_post_playmaking",
        "axis_relevance": {"A": 1.0, "B1": 0, "B2": 0, "C1": 0, "C2": 0, "D": 0},
        "metric": {"action": "高位傳導視野"},
    },
    "pick_and_roll_ball_handling": {
        "id": "pick_and_roll_ball_handling",
        "axis_relevance": {"A": 0.9, "B1": 0, "B2": 0, "C1": 0, "C2": 0, "D": 0},
        "metric": {"action": "擋拆持球判斷"},
    },
    "perimeter_shooting": {
        "id": "perimeter_shooting",
        "axis_relevance": {"A": 0, "B1": 1.0, "B2": 0, "C1": 0, "C2": 0, "D": 0},
        "metric": {"action": "定點投射三分"},
    },
    "post_up": {
        "id": "post_up",
        "axis_relevance": {"A": 0, "B1": 0, "B2": 1.0, "C1": 0, "C2": 0, "D": 0},
        "metric": {"action": "背框單打腳步"},
    },
    "on_ball_perimeter_defense": {
        "id": "on_ball_perimeter_defense",
        "axis_relevance": {"A": 0, "B1": 0, "B2": 0, "C1": 1.0, "C2": 0, "D": 0},
        "metric": {"action": "一對一外圍單防"},
    },
    "rim_protection": {
        "id": "rim_protection",
        "axis_relevance": {"A": 0, "B1": 0, "B2": 0, "C1": 0, "C2": 1.0, "D": 0},
        "metric": {"action": "護框"},
    },
}


class DescribeTrainingBreakdownTest(unittest.TestCase):
    def test_returns_six_rows_in_fixed_axes_order(self):
        player = {
            "signature_skill_id": None,
            "coordinates": {"A": 80, "B1": 80, "B2": 80, "C1": 80, "C2": 80, "D": 80},
            "diff": {"A": 10, "B1": 10, "B2": 10, "C1": 10, "C2": 10, "D": 10},
        }

        result = describe_training_breakdown(player, SKILLS_BY_ID_MULTI_AXIS)

        self.assertEqual([row["axis"] for row in result], ["A", "B1", "B2", "C1", "C2", "D"])

    def test_your_value_is_derived_from_player_value_minus_diff(self):
        player = {
            "signature_skill_id": None,
            "coordinates": {"A": 80, "B1": 80, "B2": 80, "C1": 80, "C2": 80, "D": 80},
            "diff": {"A": 10, "B1": 10, "B2": 10, "C1": 10, "C2": 10, "D": 10},
        }

        result = describe_training_breakdown(player, SKILLS_BY_ID_MULTI_AXIS)

        row_a = next(row for row in result if row["axis"] == "A")
        self.assertEqual(row_a["player_value"], 80)
        self.assertEqual(row_a["diff"], 10)
        self.assertEqual(row_a["your_value"], 70)

    def test_non_positive_diff_has_no_skill_action(self):
        player = {
            "signature_skill_id": None,
            "coordinates": {"A": 50, "B1": 50, "B2": 50, "C1": 50, "C2": 50, "D": 50},
            # user leads (diff<0) on A, ties (diff==0) on B1
            "diff": {"A": -5, "B1": 0, "B2": 10, "C1": 10, "C2": 10, "D": 10},
        }

        result = describe_training_breakdown(player, SKILLS_BY_ID_MULTI_AXIS)

        by_axis = {row["axis"]: row for row in result}
        self.assertIsNone(by_axis["A"]["skill_action"])
        self.assertIsNone(by_axis["B1"]["skill_action"])

    def test_positive_diff_falls_back_to_representative_skill_for_axis(self):
        player = {
            "signature_skill_id": None,
            "coordinates": {"A": 50, "B1": 80, "B2": 50, "C1": 50, "C2": 50, "D": 50},
            "diff": {"A": 0, "B1": 40, "B2": 0, "C1": 0, "C2": 0, "D": 0},
        }

        result = describe_training_breakdown(player, SKILLS_BY_ID_MULTI_AXIS)

        row_b1 = next(row for row in result if row["axis"] == "B1")
        self.assertEqual(row_b1["skill_action"], "定點投射三分的練習")

    def test_signature_skill_wins_over_representative_when_it_targets_the_axis(self):
        # A 軸有兩個候選技能，relevance 較高的是 high_post_playmaking(1.0)，
        # 但這位球員的招牌技能是 relevance 較低的 pick_and_roll_ball_handling
        # (0.9)——結果應該用招牌技能，不是單純取 relevance 最高的那個，
        # 跟 matching_skill_id() 既有的「招牌技能優先」規則一致。
        player = {
            "signature_skill_id": "pick_and_roll_ball_handling",
            "coordinates": {"A": 80, "B1": 50, "B2": 50, "C1": 50, "C2": 50, "D": 50},
            "diff": {"A": 10, "B1": 0, "B2": 0, "C1": 0, "C2": 0, "D": 0},
        }

        result = describe_training_breakdown(player, SKILLS_BY_ID_MULTI_AXIS)

        row_a = next(row for row in result if row["axis"] == "A")
        self.assertEqual(row_a["skill_action"], "擋拆持球判斷的練習")

    def test_d_axis_positive_diff_uses_the_untrainable_message_not_a_skill(self):
        player = {
            "signature_skill_id": None,
            "coordinates": {"A": 50, "B1": 50, "B2": 50, "C1": 50, "C2": 50, "D": 90},
            "diff": {"A": 0, "B1": 0, "B2": 0, "C1": 0, "C2": 0, "D": 20},
        }

        result = describe_training_breakdown(player, SKILLS_BY_ID_MULTI_AXIS)

        row_d = next(row for row in result if row["axis"] == "D")
        self.assertEqual(row_d["skill_action"], "身體天賦上有落差,不能單靠練習籃球技能")

    def test_lang_en_returns_english_text(self):
        player = {
            "signature_skill_id": None,
            "coordinates": {"A": 50, "B1": 80, "B2": 50, "C1": 50, "C2": 50, "D": 50},
            "diff": {"A": 0, "B1": 40, "B2": 0, "C1": 0, "C2": 0, "D": 0},
        }

        result = describe_training_breakdown(player, SKILLS_BY_ID_MULTI_AXIS, lang="en")

        row_b1 = next(row for row in result if row["axis"] == "B1")
        self.assertNotEqual(row_b1["skill_action"], "定點投射三分的練習")
        self.assertTrue(row_b1["skill_action"].strip())


if __name__ == "__main__":
    unittest.main()
