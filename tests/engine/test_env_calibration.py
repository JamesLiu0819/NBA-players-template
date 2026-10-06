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
import sys
import unittest
from pathlib import Path

from engine.priority import rank_priorities

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.run_priority import build_priority_items  # noqa: E402

DATA_DIR = ROOT / "data" / "zh"

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
        self.questions = load_json("題庫.json")
        self.skills = load_json("技能.json")["skills"]

        # "護框接近滿分、外線投射偏高、自主進攻偏低": rim_protection's current
        # level is forced near-max (-> near-zero gap) via axis_c2_2 (its
        # also_measures_skill substitute question, since rim_protection no
        # longer has its own skill_behavior question -- see 2026-10 duplicate
        # removal) -- the rest of the axis-level scores are the broader style
        # self-assessment, unchanged in spirit from the pre-six-axis version:
        # A low, B1 (perimeter shooting style) high, everything else neutral.
        axis_scores = {
            "axis_a_1": 1, "axis_a_2": 2,     # A low
            "axis_b1_1": 4, "axis_b1_2": 5,   # B1 (perimeter) high
            "axis_b2_1": 3, "axis_b2_2": 3,   # B2 (paint) neutral
            "axis_c1_1": 3, "axis_c1_2": 3,   # C1 (perimeter D) neutral
            "axis_c2_1": 3, "axis_c2_2": 5,   # C2 (rim D): c2_2 forces rim_protection near-max
            "axis_d_1": 3, "axis_d_2": 3,     # D neutral
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
            "perimeter_switch_defense": 3,
        })
        self.skill_answers = [
            {"question_id": q["id"], "score": skill_scores[q["skill_id"]]}
            for q in self.questions["skill_behavior"]
        ]

    def _rank_with_env(self, env):
        _, items = build_priority_items(
            self.questions, self.skills, self.axis_answers, self.skill_answers, env
        )
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
