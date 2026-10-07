# 用途：測試 build_training_plan()——招牌技能固定排第一且不受差距/門檴限制、
# 其餘項目依 P 排序並套用相對門檻、總數上限 5 項、沒有其餘項目時只回傳招牌
# 技能一項——跟 skill_difficulty_level() 的難度判定。
# 可手動調整的變數：無——這裡的技能跟座標都是測試用的人造資料,不是要調的參數。

import unittest

from engine.training_plan import (
    LEVEL_ADVANCED,
    LEVEL_ENTRY,
    LEVEL_MASTERY,
    TRAINING_PLAN_RELATIVE_THRESHOLD,
    build_training_plan,
    skill_difficulty_level,
)

SKILLS = [
    {"id": "shooting", "cost_C": 2,
     "axis_relevance": {"A": 0.0, "B1": 1.0, "B2": 0.0, "C1": 0.0, "C2": 0.0, "D": 0.0}},
    {"id": "creation", "cost_C": 2,
     "axis_relevance": {"A": 1.0, "B1": 0.0, "B2": 0.0, "C1": 0.0, "C2": 0.0, "D": 0.0}},
    {"id": "rim", "cost_C": 4,
     "axis_relevance": {"A": 0.0, "B1": 0.0, "B2": 0.0, "C1": 0.0, "C2": 1.0, "D": 0.0}},
    {"id": "transition", "cost_C": 1,
     "axis_relevance": {"A": 0.0, "B1": 0.0, "B2": 0.0, "C1": 0.0, "C2": 0.0, "D": 1.0}},
]

USER = {"A": 30.0, "B1": 30.0, "B2": 30.0, "C1": 30.0, "C2": 30.0, "D": 30.0}
TARGET = {"A": 60.0, "B1": 80.0, "B2": 30.0, "C1": 30.0, "C2": 50.0, "D": 90.0}
EVEN_ENV = {"shooting": 1.0, "creation": 1.0, "rim": 1.0, "transition": 1.0}


class SkillDifficultyLevelTest(unittest.TestCase):
    def test_below_forty_is_entry(self):
        self.assertEqual(skill_difficulty_level(39.9), LEVEL_ENTRY)

    def test_forty_through_seventy_is_advanced(self):
        self.assertEqual(skill_difficulty_level(40), LEVEL_ADVANCED)
        self.assertEqual(skill_difficulty_level(70), LEVEL_ADVANCED)

    def test_above_seventy_is_mastery(self):
        self.assertEqual(skill_difficulty_level(70.1), LEVEL_MASTERY)


class BuildTrainingPlanTest(unittest.TestCase):
    def test_signature_skill_is_always_first(self):
        plan = build_training_plan(SKILLS, EVEN_ENV, USER, TARGET, signature_skill_id="rim")

        self.assertEqual(plan[0]["skill_id"], "rim")
        self.assertTrue(plan[0]["is_signature"])
        self.assertTrue(all(not item["is_signature"] for item in plan[1:]))

    def test_signature_skill_appears_even_with_zero_or_negative_gap(self):
        # target is at/below the user on every trainable axis -> every
        # OTHER skill would normally be excluded, but the signature skill
        # must still appear, unlike the pre-2026-10 "all gaps zero" behavior.
        target = {axis: 0.0 for axis in USER}

        plan = build_training_plan(SKILLS, EVEN_ENV, USER, target, signature_skill_id="shooting")

        self.assertEqual([item["skill_id"] for item in plan], ["shooting"])
        self.assertTrue(plan[0]["is_signature"])

    def test_signature_skill_on_the_d_axis_is_the_exception_to_d_being_untrainable(self):
        # "transition"'s axis_relevance is 100% on D. skill_gap() ignores D
        # entirely for the GAP calculation (so G is always 0 here), but the
        # item must still be included (as the signature) and still get a
        # real difficulty level off the D axis score.
        plan = build_training_plan(SKILLS, EVEN_ENV, USER, TARGET, signature_skill_id="transition")

        signature = plan[0]
        self.assertEqual(signature["skill_id"], "transition")
        self.assertEqual(signature["dominant_axis"], "D")
        self.assertEqual(signature["G"], 0.0)
        self.assertEqual(signature["level"], skill_difficulty_level(USER["D"]))

    def test_other_items_sorted_by_priority_after_the_signature(self):
        plan = build_training_plan(SKILLS, EVEN_ENV, USER, TARGET, signature_skill_id="rim")

        other_ids = [item["skill_id"] for item in plan[1:]]
        self.assertEqual(other_ids, sorted(other_ids, key=lambda sid: -next(i["P"] for i in plan if i["skill_id"] == sid)))

    def test_items_below_25_percent_of_the_best_other_item_are_dropped(self):
        # shooting: G = 1.0*(80-30) = 50, E=1 -> P = 50/2 = 25
        # creation: G = 1.0*(60-30) = 30, E=1 -> P = 30/2 = 15 (60% of 25, kept)
        # rim:      G = 1.0*(50-30) = 20, E=1 -> P = 20/4 = 5  (20% of 25, dropped)
        plan = build_training_plan(SKILLS, EVEN_ENV, USER, TARGET, signature_skill_id="transition")

        other_ids = {item["skill_id"] for item in plan[1:]}
        self.assertIn("shooting", other_ids)
        self.assertIn("creation", other_ids)
        self.assertNotIn("rim", other_ids)

    def test_relative_threshold_constant_is_twenty_five_percent(self):
        self.assertEqual(TRAINING_PLAN_RELATIVE_THRESHOLD, 0.25)

    def test_total_items_capped_at_top_n_including_the_signature(self):
        many_skills = SKILLS + [
            {"id": f"extra{i}", "cost_C": 1,
             "axis_relevance": {"A": 1.0, "B1": 0.0, "B2": 0.0, "C1": 0.0, "C2": 0.0, "D": 0.0}}
            for i in range(5)
        ]
        many_env = dict(EVEN_ENV, **{f"extra{i}": 1.0 for i in range(5)})

        plan = build_training_plan(many_skills, many_env, USER, TARGET, signature_skill_id="rim", top_n=5)

        self.assertLessEqual(len(plan), 5)
        self.assertEqual(plan[0]["skill_id"], "rim")

    def test_environment_weight_can_change_the_non_signature_order(self):
        tight_perimeter = {"shooting": 0.1, "creation": 1.8, "rim": 1.0, "transition": 1.0}

        plan = build_training_plan(SKILLS, tight_perimeter, USER, TARGET, signature_skill_id="transition")

        self.assertEqual(plan[1]["skill_id"], "creation")

    def test_level_comes_from_users_score_on_the_dominant_axis(self):
        user = dict(USER, B1=85.0)
        target = dict(TARGET, B1=100.0)

        plan = build_training_plan(SKILLS, EVEN_ENV, user, target, signature_skill_id="rim")

        shooting = next(item for item in plan if item["skill_id"] == "shooting")
        self.assertEqual(shooting["dominant_axis"], "B1")
        self.assertEqual(shooting["level"], LEVEL_MASTERY)

    def test_same_input_gives_same_output(self):
        self.assertEqual(
            build_training_plan(SKILLS, EVEN_ENV, USER, TARGET, signature_skill_id="rim"),
            build_training_plan(SKILLS, EVEN_ENV, USER, TARGET, signature_skill_id="rim"),
        )

    def test_missing_environment_weight_for_a_non_signature_skill_raises(self):
        with self.assertRaises(ValueError):
            build_training_plan(SKILLS, {"rim": 1.0}, USER, TARGET, signature_skill_id="rim")

    def test_missing_environment_weight_for_the_signature_skill_itself_raises(self):
        env_missing_signature = {"shooting": 1.0, "creation": 1.0, "transition": 1.0}
        with self.assertRaises(ValueError):
            build_training_plan(SKILLS, env_missing_signature, USER, TARGET, signature_skill_id="rim")

    def test_unknown_signature_skill_id_raises(self):
        with self.assertRaises(ValueError):
            build_training_plan(SKILLS, EVEN_ENV, USER, TARGET, signature_skill_id="does_not_exist")


if __name__ == "__main__":
    unittest.main()
