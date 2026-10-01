# 用途：測試 mock_axis_answers(把目標六軸座標反推成一組合理的 1-5 模擬作答)
# 跟 mock_skill_answers(用 axis_relevance 加權跟招牌技能推算技能行為模擬作答)
# 這兩個 v2 球員資料生成用的推導函數。
# 可手動調整的變數：無——這支檔案裡的題目/座標資料都是為了驗證公式而設計的
# 測試案例,不是要調的參數。

import unittest

from scripts.mock_answers import mock_axis_answers, mock_skill_answers

AXES = ("A", "B1", "B2", "C1", "C2", "D")

AXIS_QUESTIONS = [
    {"id": f"axis_{axis.lower()}_{i}", "axis": axis}
    for axis in AXES
    for i in (1, 2)
]

ALL_50 = {axis: 50 for axis in AXES}


class MockAxisAnswersTest(unittest.TestCase):
    def test_coordinate_50_gives_all_middle_scores(self):
        answers = mock_axis_answers(AXIS_QUESTIONS, ALL_50)
        self.assertTrue(all(a["score"] == 3 for a in answers))

    def test_coordinate_0_gives_all_minimum_scores(self):
        coords = dict(ALL_50, A=0)
        answers = mock_axis_answers(AXIS_QUESTIONS, coords)
        a_scores = [a["score"] for a in answers if a["question_id"].startswith("axis_a_")]
        self.assertEqual(a_scores, [1, 1])

    def test_coordinate_100_gives_all_maximum_scores(self):
        coords = dict(ALL_50, B1=100)
        answers = mock_axis_answers(AXIS_QUESTIONS, coords)
        b1_scores = [a["score"] for a in answers if a["question_id"].startswith("axis_b1_")]
        self.assertEqual(b1_scores, [5, 5])

    def test_uneven_coordinate_distributes_remainder_to_first_questions(self):
        # 80 -> target_avg=4.2, sum_target=round(4.2*2)=8, base=4 remainder=0
        # -> both questions land exactly on base, no remainder to distribute.
        # Use 90 instead: target_avg=4.6, sum_target=round(4.6*2)=9, base=4
        # remainder=1 -> first question gets +1, the other stays at base.
        coords = dict(ALL_50, A=90)
        answers = mock_axis_answers(AXIS_QUESTIONS, coords)
        a_scores = [a["score"] for a in answers if a["question_id"].startswith("axis_a_")]
        self.assertEqual(a_scores, [5, 4])

    def test_every_question_id_appears_exactly_once(self):
        coords = {"A": 30, "B1": 60, "B2": 10, "C1": 90, "C2": 20, "D": 70}
        answers = mock_axis_answers(AXIS_QUESTIONS, coords)
        ids = [a["question_id"] for a in answers]
        self.assertEqual(sorted(ids), sorted(q["id"] for q in AXIS_QUESTIONS))

    def test_all_scores_within_one_to_five(self):
        for coord in (0, 25, 50, 75, 100):
            answers = mock_axis_answers(AXIS_QUESTIONS, {axis: coord for axis in AXES})
            for a in answers:
                self.assertGreaterEqual(a["score"], 1)
                self.assertLessEqual(a["score"], 5)

    def test_round_trips_close_to_original_coordinate_via_score_axis_coordinates(self):
        from engine.axis_position import score_axis_coordinates

        target = {"A": 72, "B1": 15, "B2": 88, "C1": 40, "C2": 60, "D": 25}
        answers = mock_axis_answers(AXIS_QUESTIONS, target)
        recomputed = score_axis_coordinates(AXIS_QUESTIONS, answers)
        for axis in AXES:
            self.assertAlmostEqual(recomputed[axis], target[axis], delta=15)

    def test_reverse_scored_question_gets_an_inverted_raw_score(self):
        # mirrors how a reverse_scored question works in the real
        # data/questions.json: its anchor text reads "1 = least, 5 = most"
        # of the literal described behaviour, but that behaviour runs
        # opposite to the axis, so score_axis_coordinates flips it
        # (6-score) before averaging. The mock answer must store the
        # pre-flip raw value, not the target effective score, or a high
        # target would end up looking like a low raw answer on this
        # question for no reason a human could guess.
        questions = [q.copy() for q in AXIS_QUESTIONS]
        for q in questions:
            if q["id"] == "axis_b1_2":
                q["reverse_scored"] = True

        coords = dict(ALL_50, B1=100)
        answers = mock_axis_answers(questions, coords)

        flipped = next(a for a in answers if a["question_id"] == "axis_b1_2")
        self.assertEqual(flipped["score"], 1)

    def test_reverse_scored_question_still_round_trips_correctly(self):
        from engine.axis_position import score_axis_coordinates

        questions = [q.copy() for q in AXIS_QUESTIONS]
        for q in questions:
            if q["id"] == "axis_b1_2":
                q["reverse_scored"] = True

        target = dict(ALL_50, B1=70)
        answers = mock_axis_answers(questions, target)
        recomputed = score_axis_coordinates(questions, answers)

        self.assertAlmostEqual(recomputed["B1"], target["B1"], delta=15)


SKILL_QUESTIONS = [
    {"id": "skill_post_up_1", "skill_id": "post_up"},
    {"id": "skill_perimeter_shooting_1", "skill_id": "perimeter_shooting"},
]

# Single-axis weights (rather than skills.json's real multi-axis mix) so the
# expected compute_relevance() output is exact (relevance == that axis's
# coordinate / 100), not something that needs re-deriving by hand per test.
ZERO_RELEVANCE = {axis: 0 for axis in AXES}
SKILLS_BY_ID = {
    "post_up": {"axis_relevance": dict(ZERO_RELEVANCE, B2=1.0)},
    "perimeter_shooting": {"axis_relevance": dict(ZERO_RELEVANCE, A=1.0)},
}


class MockSkillAnswersTest(unittest.TestCase):
    def test_low_relevance_axis_profile_gives_a_low_score(self):
        coordinates = dict(ALL_50, B2=0)
        answers = mock_skill_answers(SKILL_QUESTIONS, SKILLS_BY_ID, coordinates, signature_skill_id=None)
        post_up = next(a for a in answers if a["question_id"] == "skill_post_up_1")
        self.assertEqual(post_up["score"], 1)

    def test_high_relevance_axis_profile_gives_a_high_score(self):
        coordinates = dict(ALL_50, B2=100)
        answers = mock_skill_answers(SKILL_QUESTIONS, SKILLS_BY_ID, coordinates, signature_skill_id=None)
        post_up = next(a for a in answers if a["question_id"] == "skill_post_up_1")
        self.assertEqual(post_up["score"], 5)

    def test_signature_skill_is_forced_to_five_regardless_of_relevance(self):
        # B2=0 means post_up's relevance-derived score would be at the
        # bottom, but this player's signature move IS post_up -- the mock
        # answer should reflect their known specialty, not just the
        # axis-relevance guess.
        coordinates = dict(ALL_50, A=0, B2=0)
        answers = mock_skill_answers(
            SKILL_QUESTIONS, SKILLS_BY_ID, coordinates, signature_skill_id="post_up"
        )
        post_up = next(a for a in answers if a["question_id"] == "skill_post_up_1")
        self.assertEqual(post_up["score"], 5)
        perimeter = next(a for a in answers if a["question_id"] == "skill_perimeter_shooting_1")
        self.assertEqual(perimeter["score"], 1)

    def test_every_question_id_appears_exactly_once(self):
        answers = mock_skill_answers(SKILL_QUESTIONS, SKILLS_BY_ID, ALL_50, signature_skill_id=None)
        ids = [a["question_id"] for a in answers]
        self.assertEqual(sorted(ids), sorted(q["id"] for q in SKILL_QUESTIONS))


if __name__ == "__main__":
    unittest.main()
