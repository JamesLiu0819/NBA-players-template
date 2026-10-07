# 用途：驗證 data/zh/ 的題庫、技能、訓練菜單,以及 data/env_weights.json 的實際內容
# 符合 engine 預期的格式(題數、id 唯一、anchors 五個分數都有、技能欄位齊全、每項技能
# 三個難度都有訓練項目、每個環境都涵蓋全部技能),並且用真實資料跑一次完整的訓練計劃
# 管線,確認資料檔跟 engine 真的兜得起來,不是只有各自單獨測試通過。
# 文案是否為空先不檢查(訓練菜單的文案還沒填)。
# 可手動調整的變數：無——這支檔案本身不含校準參數,它是在檢查別的檔案。

import json
import unittest
from pathlib import Path

from engine.axis_position import AXES, score_axis_coordinates
from engine.training_plan import build_training_plan

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "zh"

REQUIRED_SKILL_FIELDS = {
    "id", "name_zh", "category", "cost_C", "court_required", "teammate_required",
    "axis_relevance", "video_tags", "metric",
}

ALL_SKILL_IDS = {
    "perimeter_shooting", "face_up_first_step", "high_post_playmaking",
    "rim_protection", "perimeter_switch_defense", "post_up",
    "pick_and_roll_ball_handling", "off_ball_movement", "transition_finishing",
    "free_throw_shooting", "offensive_rebounding", "on_ball_perimeter_defense",
    "help_defense_rotation", "defensive_rebounding_boxout",
    "decision_making_turnover_control",
}

LEVELS = ("entry", "advanced", "mastery")


def load_json(name):
    with open(DATA_DIR / name, encoding="utf-8") as f:
        return json.load(f)


class QuestionsDataTest(unittest.TestCase):
    def setUp(self):
        self.data = load_json("題庫.json")

    def test_no_skill_behavior_section_remains(self):
        self.assertNotIn("skill_behavior", self.data)

    def test_total_question_count_is_eighteen(self):
        total = len(self.data["axis_positioning"]) + len(self.data["body_measurements"])
        self.assertEqual(total, 18)

    def test_axis_positioning_has_two_questions_per_axis(self):
        counts = {axis: 0 for axis in AXES}
        for q in self.data["axis_positioning"]:
            counts[q["axis"]] += 1
        self.assertEqual(counts, {axis: 2 for axis in AXES})

    def test_every_axis_question_has_five_bars_anchors_and_unique_id(self):
        seen_ids = set()
        for q in self.data["axis_positioning"]:
            self.assertNotIn(q["id"], seen_ids)
            seen_ids.add(q["id"])
            self.assertEqual(set(q["anchors"].keys()), {"1", "2", "3", "4", "5"})

    def test_body_measurements_has_six_numeric_questions_covering_every_field(self):
        body_questions = self.data["body_measurements"]
        self.assertEqual(len(body_questions), 6)
        for q in body_questions:
            self.assertLess(q["min"], q["max"])
        self.assertEqual({q["field"] for q in body_questions}, {
            "height_cm", "weight_kg", "wingspan_cm",
            "standing_reach_cm", "running_vertical_reach_cm", "sprint_100m_seconds",
        })


class SkillsDataTest(unittest.TestCase):
    def setUp(self):
        self.skills = load_json("技能.json")["skills"]

    def test_covers_all_fifteen_skills(self):
        self.assertEqual({s["id"] for s in self.skills}, ALL_SKILL_IDS)

    def test_every_skill_has_the_required_fields(self):
        for skill in self.skills:
            self.assertTrue(REQUIRED_SKILL_FIELDS.issubset(skill.keys()), skill["id"])

    def test_axis_relevance_covers_all_six_axes_in_zero_one_range(self):
        for skill in self.skills:
            relevance = skill["axis_relevance"]
            self.assertEqual(set(relevance.keys()), set(AXES))
            for value in relevance.values():
                self.assertGreaterEqual(value, 0.0)
                self.assertLessEqual(value, 1.0)

    def test_cost_is_within_spec_range_one_to_five(self):
        for skill in self.skills:
            self.assertGreaterEqual(skill["cost_C"], 1)
            self.assertLessEqual(skill["cost_C"], 5)

    def test_every_metric_has_thresholds_for_all_three_levels(self):
        for skill in self.skills:
            self.assertEqual(set(skill["metric"]["thresholds"]), set(LEVELS), skill["id"])


class DrillsDataTest(unittest.TestCase):
    def setUp(self):
        self.drills = load_json("訓練菜單.json")["drills"]

    def test_every_skill_has_at_least_one_drill_per_level(self):
        seen = {(d["skill_id"], d["level"]) for d in self.drills}
        for skill_id in ALL_SKILL_IDS:
            for level in LEVELS:
                self.assertIn((skill_id, level), seen, f"{skill_id}/{level}")

    def test_every_drill_points_at_a_real_skill_and_level(self):
        for d in self.drills:
            self.assertIn(d["skill_id"], ALL_SKILL_IDS, d["id"])
            self.assertIn(d["level"], LEVELS, d["id"])

    def test_drill_ids_are_unique(self):
        ids = [d["id"] for d in self.drills]
        self.assertEqual(len(ids), len(set(ids)))


class EnvWeightsDataTest(unittest.TestCase):
    def setUp(self):
        with open(ROOT / "data" / "env_weights.json", encoding="utf-8") as f:
            self.env = json.load(f)
        self.codes = [k for k in self.env if not k.startswith("_")]

    def test_has_the_four_environment_options(self):
        self.assertEqual(set(self.codes), {
            "collapsed_no_shooters", "tight_perimeter_opp_shooters", "zone_defense",
            "no_environment",
        })

    def test_no_environment_option_leaves_every_skill_unweighted(self):
        # "無"(不套用任何環境加權)要讓 P 退化成 G/C,每項技能的倍率都必須是 1.0,
        # 不是「隨便填一組接近 1 的數字」。
        self.assertEqual(set(self.env["no_environment"].values()), {1.0})

    def test_every_environment_covers_all_fifteen_skills(self):
        for code in self.codes:
            self.assertEqual(set(self.env[code]), ALL_SKILL_IDS, code)

    def test_every_multiplier_is_within_spec_range(self):
        for code in self.codes:
            for skill_id, value in self.env[code].items():
                self.assertGreaterEqual(value, 0.5, f"{code}.{skill_id}")
                self.assertLessEqual(value, 2.0, f"{code}.{skill_id}")


class FullTrainingPlanIntegrationTest(unittest.TestCase):
    """Wires 題庫.json + 技能.json + env_weights.json + 球員.json through the
    engine for one synthetic respondent and a real template player."""

    def setUp(self):
        self.questions = load_json("題庫.json")
        self.skills = load_json("技能.json")["skills"]
        with open(ROOT / "data" / "env_weights.json", encoding="utf-8") as f:
            self.env = json.load(f)
        self.player = load_json("球員.json")["players"][0]

    def test_every_environment_yields_a_ranked_plan_of_at_most_five_items(self):
        axis_answers = [{"question_id": q["id"], "score": 2} for q in self.questions["axis_positioning"]]
        user = score_axis_coordinates(self.questions["axis_positioning"], axis_answers)

        for code in self.env:
            if code.startswith("_"):
                continue
            plan = build_training_plan(
                self.skills, self.env[code], user, self.player["coordinates"],
                self.player["signature_skill_id"],
            )
            self.assertGreaterEqual(len(plan), 1, code)
            self.assertLessEqual(len(plan), 5, code)
            self.assertTrue(plan[0]["is_signature"], code)
            self.assertEqual(plan[0]["skill_id"], self.player["signature_skill_id"], code)
            other_priorities = [item["P"] for item in plan[1:]]
            self.assertEqual(other_priorities, sorted(other_priorities, reverse=True), code)
            for item in plan[1:]:
                self.assertGreater(item["G"], 0, code)


if __name__ == "__main__":
    unittest.main()
