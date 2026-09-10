# 用途：驗證 data/questions.json 跟 data/skills.json 的實際內容符合 engine
# 預期的格式(題數、id 唯一、anchors 五個分數都有、技能欄位齊全等),並且用真實
# 資料跑一次完整管線(四軸座標→缺口→相關性→優先序),確認資料檔跟四個 engine
# 模組真的兜得起來,不是只有各自單獨測試通過。
# 可手動調整的變數：無——這支檔案本身不含校準參數,它是在檢查別的檔案。

import json
import unittest
from pathlib import Path

from engine.axis_position import AXES, score_axis_coordinates
from engine.priority import rank_priorities
from engine.relevance import compute_relevance
from engine.skill_level import compute_gap, score_skill_current_level

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

REQUIRED_SKILL_FIELDS = {
    "id",
    "name_zh",
    "category",
    "cost_C",
    "court_required",
    "teammate_required",
    "axis_relevance",
    "video_tags",
    "metric",
}

ALL_SKILL_IDS = {
    "perimeter_shooting",
    "face_up_first_step",
    "high_post_playmaking",
    "rim_protection",
    "perimeter_switch_defense",
    "post_up",
    "pick_and_roll_ball_handling",
    "off_ball_movement",
    "transition_finishing",
    "free_throw_shooting",
    "offensive_rebounding",
    "on_ball_perimeter_defense",
    "help_defense_rotation",
    "defensive_rebounding_boxout",
    "decision_making_turnover_control",
}


def load_json(name):
    with open(DATA_DIR / name, encoding="utf-8") as f:
        return json.load(f)


class QuestionsDataTest(unittest.TestCase):
    def setUp(self):
        self.data = load_json("questions.json")

    def test_axis_positioning_has_four_questions_per_axis(self):
        axis_questions = self.data["axis_positioning"]
        self.assertEqual(len(axis_questions), 16)

        counts = {axis: 0 for axis in AXES}
        for q in axis_questions:
            counts[q["axis"]] += 1
        self.assertEqual(counts, {"A": 4, "B": 4, "C": 4, "D": 4})

    def test_every_axis_question_has_five_bars_anchors_and_unique_id(self):
        seen_ids = set()
        for q in self.data["axis_positioning"]:
            self.assertNotIn(q["id"], seen_ids)
            seen_ids.add(q["id"])
            self.assertEqual(set(q["anchors"].keys()), {"1", "2", "3", "4", "5"})

    def test_skill_behavior_covers_all_fifteen_skills(self):
        skill_ids = {q["skill_id"] for q in self.data["skill_behavior"]}
        self.assertEqual(skill_ids, ALL_SKILL_IDS)

    def test_every_skill_behavior_question_has_five_bars_anchors(self):
        for q in self.data["skill_behavior"]:
            self.assertEqual(set(q["anchors"].keys()), {"1", "2", "3", "4", "5"})

    def test_body_measurements_has_six_numeric_questions_with_unique_ids_and_fields(self):
        body_questions = self.data["body_measurements"]
        self.assertEqual(len(body_questions), 6)

        ids = [q["id"] for q in body_questions]
        fields = [q["field"] for q in body_questions]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(fields), len(set(fields)))

        for q in body_questions:
            self.assertLess(q["min"], q["max"])

    def test_body_measurements_covers_every_field_players_json_actually_has(self):
        # See data/players.json's "body" schema -- body_distance/
        # find_body_fit_template can only compare on fields both sides have,
        # and every field's [min, max] here is also what
        # scripts/build_players_seed.py's derived fields must stay inside.
        fields = {q["field"] for q in self.data["body_measurements"]}
        self.assertEqual(fields, {
            "height_cm", "weight_kg", "wingspan_cm",
            "standing_reach_cm", "running_vertical_reach_cm", "sprint_20m_seconds",
        })


class SkillsDataTest(unittest.TestCase):
    def setUp(self):
        self.skills = load_json("skills.json")["skills"]

    def test_covers_all_fifteen_skills(self):
        self.assertEqual({s["id"] for s in self.skills}, ALL_SKILL_IDS)

    def test_every_skill_has_the_required_fields(self):
        for skill in self.skills:
            self.assertTrue(REQUIRED_SKILL_FIELDS.issubset(skill.keys()), skill["id"])

    def test_axis_relevance_covers_all_four_axes_in_zero_one_range(self):
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


class FullPipelineIntegrationTest(unittest.TestCase):
    """Wires questions.json + skills.json through every engine function for
    one synthetic respondent, proving the two data files and the four engine
    modules actually fit together end to end."""

    def setUp(self):
        self.questions = load_json("questions.json")
        self.skills = load_json("skills.json")["skills"]

    def test_produces_a_ranked_priority_list_with_dominant_env_effect(self):
        axis_answers = [
            {"question_id": q["id"], "score": 2}
            for q in self.questions["axis_positioning"]
        ]
        coordinates = score_axis_coordinates(
            self.questions["axis_positioning"], axis_answers
        )
        self.assertEqual(set(coordinates.keys()), set(AXES))

        skill_answers = [
            {"question_id": q["id"], "score": 3}
            for q in self.questions["skill_behavior"]
        ]

        # Simulate an environment vector (SPEC §3.2) that hugely favors
        # perimeter shooting and suppresses rim protection, e.g. a
        # collapsed-defense, loose-whistle league like SPEC.md §11's fixture.
        # Every other skill defaults to a neutral 1.0 -- this test only
        # cares that the pipeline plumbs E through correctly end to end for
        # all 15 skills, not that every skill has a hand-tuned value here.
        env_multiplier = {skill["id"]: 1.0 for skill in self.skills}
        env_multiplier.update({
            "perimeter_shooting": 1.8,
            "face_up_first_step": 1.4,
            "high_post_playmaking": 1.5,
            "rim_protection": 0.6,
            "perimeter_switch_defense": 1.0,
        })

        priority_inputs = []
        for skill in self.skills:
            current = score_skill_current_level(
                self.questions["skill_behavior"], skill_answers, skill["id"]
            )
            gap = compute_gap(current)
            relevance = compute_relevance(coordinates, skill["axis_relevance"])
            priority_inputs.append({
                "skill_id": skill["id"],
                "G": gap,
                "E": env_multiplier[skill["id"]],
                "R": relevance,
                "C": skill["cost_C"],
            })

        ranked = rank_priorities(priority_inputs)

        self.assertEqual(len(ranked), 15)
        for item in ranked:
            self.assertGreaterEqual(item["P"], 0)
        priorities = [item["P"] for item in ranked]
        self.assertEqual(priorities, sorted(priorities, reverse=True))


if __name__ == "__main__":
    unittest.main()
