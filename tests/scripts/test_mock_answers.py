# 用途：測試 mock_axis_answers(把目標四軸座標反推成一組合理的 1-5 模擬作答)
# 跟 mock_skill_answers(用 axis_relevance 加權跟招牌技能推算技能行為模擬作答)
# 這兩個 v2 球員資料生成用的推導函數。
# 可手動調整的變數：無——這支檔案裡的題目/座標資料都是為了驗證公式而設計的
# 測試案例,不是要調的參數。

import unittest

from scripts.mock_answers import mock_axis_answers, mock_skill_answers

AXIS_QUESTIONS = [
    {"id": "axis_a1", "axis": "A"},
    {"id": "axis_a2", "axis": "A"},
    {"id": "axis_a3", "axis": "A"},
    {"id": "axis_a4", "axis": "A"},
    {"id": "axis_b1", "axis": "B"},
    {"id": "axis_b2", "axis": "B"},
    {"id": "axis_b3", "axis": "B"},
    {"id": "axis_b4", "axis": "B"},
    {"id": "axis_c1", "axis": "C"},
    {"id": "axis_c2", "axis": "C"},
    {"id": "axis_c3", "axis": "C"},
    {"id": "axis_c4", "axis": "C"},
    {"id": "axis_d1", "axis": "D"},
    {"id": "axis_d2", "axis": "D"},
    {"id": "axis_d3", "axis": "D"},
    {"id": "axis_d4", "axis": "D"},
]


class MockAxisAnswersTest(unittest.TestCase):
    def test_coordinate_50_gives_all_middle_scores(self):
        answers = mock_axis_answers(AXIS_QUESTIONS, {"A": 50, "B": 50, "C": 50, "D": 50})
        self.assertTrue(all(a["score"] == 3 for a in answers))

    def test_coordinate_0_gives_all_minimum_scores(self):
        answers = mock_axis_answers(AXIS_QUESTIONS, {"A": 0, "B": 50, "C": 50, "D": 50})
        a_scores = [a["score"] for a in answers if a["question_id"].startswith("axis_a")]
        self.assertEqual(a_scores, [1, 1, 1, 1])

    def test_coordinate_100_gives_all_maximum_scores(self):
        answers = mock_axis_answers(AXIS_QUESTIONS, {"A": 50, "B": 100, "C": 50, "D": 50})
        b_scores = [a["score"] for a in answers if a["question_id"].startswith("axis_b")]
        self.assertEqual(b_scores, [5, 5, 5, 5])

    def test_uneven_coordinate_distributes_remainder_to_first_questions(self):
        # 80 -> target_avg=4.2, sum_target=round(4.2*4)=17, base=4 remainder=1
        # -> first question gets +1, the rest stay at base.
        answers = mock_axis_answers(AXIS_QUESTIONS, {"A": 80, "B": 50, "C": 50, "D": 50})
        a_scores = [a["score"] for a in answers if a["question_id"].startswith("axis_a")]
        self.assertEqual(a_scores, [5, 4, 4, 4])

    def test_every_question_id_appears_exactly_once(self):
        answers = mock_axis_answers(AXIS_QUESTIONS, {"A": 30, "B": 60, "C": 10, "D": 90})
        ids = [a["question_id"] for a in answers]
        self.assertEqual(sorted(ids), sorted(q["id"] for q in AXIS_QUESTIONS))

    def test_all_scores_within_one_to_five(self):
        for coord in (0, 25, 50, 75, 100):
            answers = mock_axis_answers(AXIS_QUESTIONS, {"A": coord, "B": coord, "C": coord, "D": coord})
            for a in answers:
                self.assertGreaterEqual(a["score"], 1)
                self.assertLessEqual(a["score"], 5)

    def test_round_trips_close_to_original_coordinate_via_score_axis_coordinates(self):
        from engine.axis_position import score_axis_coordinates

        target = {"A": 72, "B": 15, "C": 88, "D": 40}
        answers = mock_axis_answers(AXIS_QUESTIONS, target)
        recomputed = score_axis_coordinates(AXIS_QUESTIONS, answers)
        for axis in "ABCD":
            self.assertAlmostEqual(recomputed[axis], target[axis], delta=15)

    def test_reverse_scored_question_gets_an_inverted_raw_score(self):
        # axis_b3 is reverse_scored in the real data/questions.json: its
        # anchor text reads "1 = least, 5 = most" of the literal described
        # behaviour, but that behaviour runs opposite to the axis, so
        # score_axis_coordinates flips it (6-score) before averaging. The
        # mock answer must store the pre-flip raw value, not the target
        # effective score, or a high B target would end up looking like a
        # low raw answer on this question for no reason a human could guess.
        questions = [q.copy() for q in AXIS_QUESTIONS]
        for q in questions:
            if q["id"] == "axis_b3":
                q["reverse_scored"] = True

        answers = mock_axis_answers(questions, {"A": 50, "B": 100, "C": 50, "D": 50})

        b3 = next(a for a in answers if a["question_id"] == "axis_b3")
        self.assertEqual(b3["score"], 1)

    def test_reverse_scored_question_still_round_trips_correctly(self):
        from engine.axis_position import score_axis_coordinates

        questions = [q.copy() for q in AXIS_QUESTIONS]
        for q in questions:
            if q["id"] == "axis_b3":
                q["reverse_scored"] = True

        target = {"A": 50, "B": 70, "C": 50, "D": 50}
        answers = mock_axis_answers(questions, target)
        recomputed = score_axis_coordinates(questions, answers)

        self.assertAlmostEqual(recomputed["B"], target["B"], delta=15)


SKILL_QUESTIONS = [
    {"id": "skill_post_up_1", "skill_id": "post_up"},
    {"id": "skill_perimeter_shooting_1", "skill_id": "perimeter_shooting"},
]

# Single-axis weights (rather than skills.json's real multi-axis mix) so the
# expected compute_relevance() output is exact (relevance == that axis's
# coordinate / 100), not something that needs re-deriving by hand per test.
SKILLS_BY_ID = {
    "post_up": {"axis_relevance": {"A": 0, "B": 1.0, "C": 0, "D": 0}},
    "perimeter_shooting": {"axis_relevance": {"A": 1.0, "B": 0, "C": 0, "D": 0}},
}


class MockSkillAnswersTest(unittest.TestCase):
    def test_low_relevance_axis_profile_gives_a_low_score(self):
        coordinates = {"A": 50, "B": 0, "C": 50, "D": 50}
        answers = mock_skill_answers(SKILL_QUESTIONS, SKILLS_BY_ID, coordinates, signature_skill_id=None)
        post_up = next(a for a in answers if a["question_id"] == "skill_post_up_1")
        self.assertEqual(post_up["score"], 1)

    def test_high_relevance_axis_profile_gives_a_high_score(self):
        coordinates = {"A": 50, "B": 100, "C": 50, "D": 50}
        answers = mock_skill_answers(SKILL_QUESTIONS, SKILLS_BY_ID, coordinates, signature_skill_id=None)
        post_up = next(a for a in answers if a["question_id"] == "skill_post_up_1")
        self.assertEqual(post_up["score"], 5)

    def test_signature_skill_is_forced_to_five_regardless_of_relevance(self):
        # B=0 means post_up's relevance-derived score would be at the
        # bottom, but this player's signature move IS post_up -- the mock
        # answer should reflect their known specialty, not just the
        # axis-relevance guess.
        coordinates = {"A": 0, "B": 0, "C": 50, "D": 50}
        answers = mock_skill_answers(
            SKILL_QUESTIONS, SKILLS_BY_ID, coordinates, signature_skill_id="post_up"
        )
        post_up = next(a for a in answers if a["question_id"] == "skill_post_up_1")
        self.assertEqual(post_up["score"], 5)
        perimeter = next(a for a in answers if a["question_id"] == "skill_perimeter_shooting_1")
        self.assertEqual(perimeter["score"], 1)

    def test_every_question_id_appears_exactly_once(self):
        coordinates = {"A": 50, "B": 50, "C": 50, "D": 50}
        answers = mock_skill_answers(SKILL_QUESTIONS, SKILLS_BY_ID, coordinates, signature_skill_id=None)
        ids = [a["question_id"] for a in answers]
        self.assertEqual(sorted(ids), sorted(q["id"] for q in SKILL_QUESTIONS))


if __name__ == "__main__":
    unittest.main()
