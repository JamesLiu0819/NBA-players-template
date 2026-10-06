# 用途：測試 build_training_plan() 跟 skill_difficulty_level()——挑前五項、
# 難度判定、環境倍率會不會真的改變排序、D 軸不影響結果。
# 可手動調整的變數：無——這裡的技能跟座標都是測試用的人造資料,不是要調的參數。

import unittest

from engine.training_plan import (
    LEVEL_ADVANCED,
    LEVEL_ENTRY,
    LEVEL_MASTERY,
    build_training_plan,
    representative_skill_by_axis,
    skill_difficulty_level,
)

SKILLS = [
    {"id": "shooting", "cost_C": 2,
     "axis_relevance": {"A": 0.0, "B1": 1.0, "B2": 0.0, "C1": 0.0, "C2": 0.0, "D": 0.0}},
    {"id": "creation", "cost_C": 2,
     "axis_relevance": {"A": 1.0, "B1": 0.0, "B2": 0.0, "C1": 0.0, "C2": 0.0, "D": 0.0}},
    {"id": "rim", "cost_C": 4,
     "axis_relevance": {"A": 0.0, "B1": 0.0, "B2": 0.0, "C1": 0.0, "C2": 1.0, "D": 0.0}},
]

USER = {"A": 30.0, "B1": 30.0, "B2": 30.0, "C1": 30.0, "C2": 30.0, "D": 30.0}
TARGET = {"A": 60.0, "B1": 80.0, "B2": 30.0, "C1": 30.0, "C2": 50.0, "D": 30.0}
EVEN_ENV = {"shooting": 1.0, "creation": 1.0, "rim": 1.0}


class SkillDifficultyLevelTest(unittest.TestCase):
    def test_below_forty_is_entry(self):
        self.assertEqual(skill_difficulty_level(39.9), LEVEL_ENTRY)

    def test_forty_through_seventy_is_advanced(self):
        self.assertEqual(skill_difficulty_level(40), LEVEL_ADVANCED)
        self.assertEqual(skill_difficulty_level(70), LEVEL_ADVANCED)

    def test_above_seventy_is_mastery(self):
        self.assertEqual(skill_difficulty_level(70.1), LEVEL_MASTERY)


class BuildTrainingPlanTest(unittest.TestCase):
    def test_skills_without_a_gap_are_excluded(self):
        target = dict(TARGET, B1=20.0, A=20.0)  # shooting and creation now at/below user

        plan = build_training_plan(SKILLS, EVEN_ENV, USER, target)

        self.assertEqual([item["skill_id"] for item in plan], ["rim"])

    def test_all_gaps_zero_returns_empty_list(self):
        target = {axis: 0.0 for axis in USER}

        self.assertEqual(build_training_plan(SKILLS, EVEN_ENV, USER, target), [])

    def test_sorted_by_priority_and_truncated_to_top_n(self):
        plan = build_training_plan(SKILLS, EVEN_ENV, USER, TARGET, top_n=2)

        self.assertEqual([item["skill_id"] for item in plan], ["shooting", "creation"])

    def test_environment_weight_can_flip_the_top_skill(self):
        tight_perimeter = {"shooting": 0.5, "creation": 1.8, "rim": 1.0}

        plan = build_training_plan(SKILLS, tight_perimeter, USER, TARGET)

        self.assertEqual(plan[0]["skill_id"], "creation")

    def test_d_axis_target_does_not_change_the_plan(self):
        bigger_d_gap = dict(TARGET, D=100.0)

        self.assertEqual(
            build_training_plan(SKILLS, EVEN_ENV, USER, TARGET),
            build_training_plan(SKILLS, EVEN_ENV, USER, bigger_d_gap),
        )

    def test_level_comes_from_users_score_on_the_dominant_axis(self):
        user = dict(USER, B1=85.0)
        target = dict(TARGET, B1=100.0)  # keep a gap on B1 even at 85

        plan = build_training_plan(SKILLS, EVEN_ENV, user, target)

        shooting = next(item for item in plan if item["skill_id"] == "shooting")
        self.assertEqual(shooting["dominant_axis"], "B1")
        self.assertEqual(shooting["level"], LEVEL_MASTERY)

    def test_same_input_gives_same_output(self):
        self.assertEqual(
            build_training_plan(SKILLS, EVEN_ENV, USER, TARGET),
            build_training_plan(SKILLS, EVEN_ENV, USER, TARGET),
        )

    def test_missing_environment_weight_raises(self):
        with self.assertRaises(ValueError):
            build_training_plan(SKILLS, {"shooting": 1.0}, USER, TARGET)


def _skill(skill_id, **weights):
    relevance = {axis: 0.0 for axis in ("A", "B1", "B2", "C1", "C2", "D")}
    relevance.update(weights)
    return {"id": skill_id, "cost_C": 2, "axis_relevance": relevance}


class RepresentativeSkillByAxisTest(unittest.TestCase):
    def test_picks_the_skill_with_the_highest_weight_among_those_dominant_on_the_axis(self):
        skills = [_skill("weak_a", A=0.6), _skill("strong_a", A=0.9), _skill("b_only", B1=1.0)]
        self.assertEqual(representative_skill_by_axis(skills)["A"], "strong_a")

    def test_ties_break_on_skill_id(self):
        skills = [_skill("zeta", A=0.9), _skill("alpha", A=0.9)]
        self.assertEqual(representative_skill_by_axis(skills)["A"], "alpha")

    def test_falls_back_to_highest_weight_when_no_skill_is_dominant_on_the_axis(self):
        skills = [_skill("lean_b1", A=0.3, B1=0.5), _skill("lean_a", A=0.9)]
        # lean_b1 is dominant on B1, so for B2 (no dominant skill) the highest B2 weight wins
        skills.append(_skill("some_b2", B2=0.4, A=0.5))
        self.assertEqual(representative_skill_by_axis(skills)["B2"], "some_b2")

    def test_never_returns_d_and_covers_every_trainable_axis(self):
        skills = [_skill("a", A=1.0), _skill("b1", B1=1.0), _skill("b2", B2=1.0),
                  _skill("c1", C1=1.0), _skill("c2", C2=1.0), _skill("d", D=1.0)]
        mapping = representative_skill_by_axis(skills)
        self.assertEqual(set(mapping), {"A", "B1", "B2", "C1", "C2"})


if __name__ == "__main__":
    unittest.main()
