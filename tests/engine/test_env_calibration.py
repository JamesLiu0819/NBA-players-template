# 用途：驗證環境權重 E 真的會影響排序結果,不是好看不做事的裝飾參數。
# 可手動調整的變數：ENV_COLLAPSED_NO_SHOOTERS 跟 ENV_TIGHT_PERIMETER_OPP_SHOOTERS
# 這兩組數字,必須跟 tools/survey.html 裡 ENV_PRESETS 常數的對應數值手動保持一致
# (目前沒有自動比對機制,改一邊記得也改另一邊,見 tools/README.md)。

"""Characterization tests proving the environment multiplier E actually
moves the ranking (SPEC.md §3.2 / §11) rather than being cosmetic.

Uses the real data/questions.json + data/skills.json (not synthetic stubs)
because this is specifically about whether the *shipped* five-skill data
produces a sensible, reversible ranking under different league environments.

The env dicts below are the same "provisional" preset values as the
collapsed_no_shooters / tight_perimeter_opp_shooters buttons in
tools/survey.html — keep them in sync by hand if either changes.
"""
import json
import unittest
from pathlib import Path

from engine.axis_position import score_axis_coordinates
from engine.priority import rank_priorities
from engine.relevance import compute_relevance
from engine.skill_level import compute_gap, score_skill_current_level

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

ENV_COLLAPSED_NO_SHOOTERS = {
    "perimeter_shooting": 1.8,
    "face_up_first_step": 1.3,
    "high_post_playmaking": 1.4,
    "rim_protection": 0.6,
    "perimeter_switch_defense": 0.9,
    "post_up": 0.7,
    "pick_and_roll_ball_handling": 1.3,
    "off_ball_movement": 1.1,
    "transition_finishing": 1.0,
    "free_throw_shooting": 1.0,
    "offensive_rebounding": 0.9,
    "on_ball_perimeter_defense": 0.7,
    "help_defense_rotation": 1.5,
    "defensive_rebounding_boxout": 1.1,
    "decision_making_turnover_control": 1.0,
}

ENV_TIGHT_PERIMETER_OPP_SHOOTERS = {
    "perimeter_shooting": 0.8,
    "face_up_first_step": 1.8,
    "high_post_playmaking": 1.1,
    "rim_protection": 1.2,
    "perimeter_switch_defense": 1.6,
    "post_up": 1.3,
    "pick_and_roll_ball_handling": 1.8,
    "off_ball_movement": 1.4,
    "transition_finishing": 1.0,
    "free_throw_shooting": 1.0,
    "offensive_rebounding": 1.3,
    "on_ball_perimeter_defense": 1.7,
    "help_defense_rotation": 1.6,
    "defensive_rebounding_boxout": 1.1,
    "decision_making_turnover_control": 1.0,
}


def load_json(name):
    with open(DATA_DIR / name, encoding="utf-8") as f:
        return json.load(f)


class EnvCalibrationTest(unittest.TestCase):
    def setUp(self):
        self.questions = load_json("questions.json")
        self.skills = load_json("skills.json")["skills"]

        # "護框接近滿分、外線投射中等、自主進攻偏低": high rim-protection
        # current level (-> near-zero gap), mid shooting, low on-ball
        # creation/passing current levels (-> large gaps there).
        axis_scores = {
            "axis_a1": 1, "axis_a2": 2, "axis_a3": 1, "axis_a4": 2,   # A low
            "axis_b1": 4, "axis_b2": 5, "axis_b3": 4, "axis_b4": 5,   # B high
            "axis_c1": 3, "axis_c2": 3, "axis_c3": 3, "axis_c4": 3,   # C mid
            "axis_d1": 3, "axis_d2": 3, "axis_d3": 3, "axis_d4": 3,   # D mid
        }
        self.axis_answers = [{"question_id": qid, "score": s} for qid, s in axis_scores.items()]

        # Every other skill (the 10 added in the 2026-09-10 skill-library
        # expansion) defaults to a neutral score of 3 -- this fixture is
        # specifically about the original 5-skill narrative, not about
        # hand-crafting a behavior for every skill in the library.
        skill_scores = {q["skill_id"]: 3 for q in self.questions["skill_behavior"]}
        skill_scores.update({
            "perimeter_shooting": 3,
            "face_up_first_step": 1,
            "high_post_playmaking": 1,
            "rim_protection": 5,
            "perimeter_switch_defense": 3,
        })
        self.skill_answers = [
            {"question_id": q["id"], "score": skill_scores[q["skill_id"]]}
            for q in self.questions["skill_behavior"]
        ]

    def _rank_with_env(self, env):
        coordinates = score_axis_coordinates(self.questions["axis_positioning"], self.axis_answers)
        items = []
        for skill in self.skills:
            current = score_skill_current_level(self.questions["skill_behavior"], self.skill_answers, skill["id"])
            items.append({
                "skill_id": skill["id"],
                "G": compute_gap(current),
                "E": env[skill["id"]],
                "R": compute_relevance(coordinates, skill["axis_relevance"]),
                "C": skill["cost_C"],
            })
        return rank_priorities(items)

    def test_collapsed_defense_ranks_shooting_first_and_rim_protection_last(self):
        ranked = self._rank_with_env(ENV_COLLAPSED_NO_SHOOTERS)
        skill_order = [item["skill_id"] for item in ranked]

        self.assertEqual(skill_order[0], "perimeter_shooting")
        self.assertEqual(skill_order[-1], "rim_protection")
        # rim_protection's gap is ~0 (near-maxed BARS answer), so P should be ~0
        rim_item = next(item for item in ranked if item["skill_id"] == "rim_protection")
        self.assertAlmostEqual(rim_item["P"], 0.0, places=6)

    def test_switching_to_tight_perimeter_env_flips_the_top_ranked_skill(self):
        collapsed_ranked = self._rank_with_env(ENV_COLLAPSED_NO_SHOOTERS)
        tight_ranked = self._rank_with_env(ENV_TIGHT_PERIMETER_OPP_SHOOTERS)

        top_under_collapsed = collapsed_ranked[0]["skill_id"]
        top_under_tight = tight_ranked[0]["skill_id"]

        # If the top skill doesn't change, E isn't actually driving the
        # ranking -- the environment-calibration mechanism would be inert.
        self.assertNotEqual(
            top_under_collapsed, top_under_tight,
            "top-ranked skill did not change between environments; "
            "E has no effect on the ranking for this input",
        )
        self.assertEqual(top_under_collapsed, "perimeter_shooting")
        self.assertEqual(top_under_tight, "face_up_first_step")


if __name__ == "__main__":
    unittest.main()
